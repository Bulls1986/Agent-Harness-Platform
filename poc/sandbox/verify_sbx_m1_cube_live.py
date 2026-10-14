"""Real DEV-SBX M1 API -> PG -> native Cube Template -> MicroVM -> Guest -> kill.

OPT-IN only. Requires local actual Cube and PostgreSQL; never reports skipped
as PASS. Temporary synthetic identity is injected in-process, NOT production IAM.
"""
from __future__ import annotations
import json
import os
import sys
from uuid import uuid4
from types import SimpleNamespace

from fastapi.testclient import TestClient
from poc.closed_loop.facts import PgFacts
from poc.sandbox.sbx_management import (
    PgSandboxCreateStore, CubeNativeCreateTransport, SandboxCreateService)
from poc.sandbox.sbx_api import create_sbx_m1_app
from poc.sandbox.sbx_template import CubeTemplateGateway


def main():
    required=("CUBE_API_URL","CUBE_PROXY_NODE_IP","HARNESS_POC_DATABASE_URL","SBX_M1_CUBE_TEST_TEMPLATE_ID")
    missing=[x for x in required if not os.getenv(x)]
    if missing:
        raise RuntimeError("Real Cube/PG configuration required: "+",".join(missing))
    from cubesandbox import Sandbox, Template
    template_id=os.environ["SBX_M1_CUBE_TEST_TEMPLATE_ID"]
    scope="sbx-m1-live-"+uuid4().hex
    principal="sbx-m1-live-local"
    policy=lambda s,p,a,body: s==scope and p==principal
    templates=CubeTemplateGateway(sdk=Template,authorize=policy)
    service=SandboxCreateService(
        PgSandboxCreateStore(PgFacts()),
        CubeNativeCreateTransport(sdk=Sandbox),
        authorize=policy,template_resolver=templates.resolve)
    app=create_sbx_m1_app(
        resolve_context=lambda _r:SimpleNamespace(
            project_scope=scope,principal_id=principal),
        service=service,template_gateway=templates)
    client=TestClient(app)
    sbid=None
    try:
        listed=client.get("/api/v1/cube/templates")
        assert listed.status_code==200,listed.text[:300]
        detail=client.get("/api/v1/cube/templates/"+template_id)
        assert detail.status_code==200,detail.text[:300]
        assert detail.json()["status"]=="READY"
        key="smoke-"+uuid4().hex
        payload={"cube":{"template":template_id,"timeout":180},
                 "onCreate":{"commands":[{
                     "command":"git --version","cwd":"/workspace",
                     "timeoutSeconds":30}]}}
        response=client.post("/api/v1/sandboxes",json=payload,
                             headers={"Idempotency-Key":key})
        assert response.status_code==202,response.text[:300]
        body=response.json()
        sbid=body["sandboxRef"]
        assert body["state"]=="READY",body
        assert body["nativeTemplateId"]==template_id
        again=client.post("/api/v1/sandboxes",json=payload,
                          headers={"Idempotency-Key":key})
        assert again.status_code==202 and again.json()==body
        op=client.get("/api/v1/sandbox-operations/"+body["operationId"])
        assert op.status_code==200 and op.json()==body
        sandbox=Sandbox.connect(sbid)
        check=sandbox.commands.run("git --version",cwd="/workspace",timeout=30)
        assert check.exit_code==0,check.stderr
        info=sandbox.get_info()
        native_template=getattr(info,"template_id",None)
        print(json.dumps({
            "result":"PASS","real_cube":True,"postgres":True,
            "sdk_template_count":len(listed.json()),
            "template_id":template_id,
            "sandbox_id":sbid,
            "operation_id":body["operationId"],
            "create_state":body["state"],
            "idempotent_retry_same_operation":True,
            "guest_git_exit_code":check.exit_code,
            "guest_git_version":check.stdout.strip(),
            "native_info_template":native_template,
        },indent=2),flush=True)
    finally:
        if sbid:
            try:
                Sandbox.connect(sbid).kill()
                print("CLEANUP_NATIVE_CUBE_KILLED",sbid,flush=True)
            except Exception as e:
                print("CLEANUP_NEEDS_RECONCILIATION",sbid,type(e).__name__,flush=True)
                raise


if __name__=="__main__":
    main()