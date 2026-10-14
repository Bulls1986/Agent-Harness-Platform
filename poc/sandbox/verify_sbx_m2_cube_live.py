"""Opt-in DEV-SBX M2 real Cube + real PG + HTTP Session Attach acceptance.

Synthetic in-process Gateway/Policy assertions apply only to this local smoke.
NOT production authentication. Only this smoke's newly created Cube VM is killed.
"""
from __future__ import annotations

import os
from time import time
from types import SimpleNamespace
from uuid import uuid4
from fastapi.testclient import TestClient
from poc.closed_loop.facts import PgFacts
from poc.sandbox.sbx_management import (
    PgSandboxCreateStore, CubeNativeCreateTransport, SandboxCreateService)
from poc.sandbox.sbx_attach import (
    PgSessionBindingStore, SessionAttachService, InitializationPermit)
from poc.sandbox.sbx_template import CubeTemplateGateway
from poc.sandbox.sbx_api import create_sbx_m1_app


def main():
    required=("HARNESS_POC_DATABASE_URL","CUBE_API_URL","CUBE_PROXY_NODE_IP",
              "SBX_M1_CUBE_TEST_TEMPLATE_ID")
    if any(not os.getenv(x) for x in required):
        raise RuntimeError("Actual Cube/PG configuration required")
    from cubesandbox import Sandbox,Template
    scope="m2-live-"+uuid4().hex
    principal="m2-local-test"
    session="synthetic-session-"+uuid4().hex
    second="second-session-"+uuid4().hex
    allowed={session,second}
    def auth(s,p,action,payload):
        if (s,p)!=(scope,principal):return False
        if action=="initialize":
            return InitializationPermit(scope=s,principal=p,
                session_ref=payload["sessionRef"],sandbox_id=payload["sandboxId"],
                operation_digest=payload["operationDigest"],expires_at=time()+180)
        return action in ("create","attach")
    def session_authority(s,p,ref):
        return s==scope and p==principal and ref in allowed

    facts=PgFacts()
    create_store=PgSandboxCreateStore(facts)
    create_service=SandboxCreateService(
        create_store,CubeNativeCreateTransport(sdk=Sandbox),
        authorize=auth,
        template_resolver=CubeTemplateGateway(sdk=Template,authorize=auth).resolve)
    attach_service=SessionAttachService(
        store=PgSessionBindingStore(facts),create_store=create_store,
        native=Sandbox,authorize=auth,authorize_session=session_authority)
    http=TestClient(create_sbx_m1_app(
        resolve_context=lambda _r:SimpleNamespace(
            project_scope=scope,principal_id=principal),
        service=create_service,attach_service=attach_service))
    native_id=None
    try:
        # All effects are in Cube guest, never host. Native git local origin
        # contains a real commit; no external provider credentials required.
        steps=[
            "git init -b main /workspace/seed",
            "git -C /workspace/seed config user.email sandbox@example.invalid",
            "git -C /workspace/seed config user.name SandboxSmoke",
            "sh -c 'echo first-commit > /workspace/seed/README.txt'",
            "git -C /workspace/seed add README.txt",
            "git -C /workspace/seed commit -m initial",
            "git clone --bare /workspace/seed /workspace/remote.git",
        ]
        created=http.post("/api/v1/sandboxes",json={
            "cube":{"template":os.environ["SBX_M1_CUBE_TEST_TEMPLATE_ID"],
                    "timeout":300},
            "onCreate":{"commands":[{"command":cmd,"cwd":"/workspace",
                     "timeoutSeconds":60} for cmd in steps]}},
            headers={"Idempotency-Key":"m2-create-"+uuid4().hex})
        assert created.status_code==202,created.text[:300]
        info=created.json()
        native_id=info["sandboxRef"]
        assert info["state"]=="READY",info
        commands=[
            {"command":"git clone /workspace/remote.git /workspace/app",
             "cwd":"/workspace","timeoutSeconds":60},
            {"command":"git -C /workspace/app fetch origin",
             "cwd":"/workspace","timeoutSeconds":60},
            {"command":"git -C /workspace/app rev-parse HEAD",
             "cwd":"/workspace","timeoutSeconds":30},
        ]
        attach_body={"createOperationId":info["operationId"],
                     "sessionRef":session,"onAttach":{"commands":commands}}
        key="attach-"+uuid4().hex
        response=http.post("/api/v1/sandbox-bindings",json=attach_body,
                           headers={"Idempotency-Key":key})
        assert response.status_code==202,response.text[:500]
        binding=response.json()
        assert binding["state"]=="ACTIVE",binding
        check=Sandbox.connect(native_id).commands.run(
            "cat /workspace/app/README.txt",cwd="/workspace",timeout=20)
        assert check.exit_code==0 and "first-commit" in check.stdout,check
        Sandbox.connect(native_id).commands.run(
            "sh -c 'echo retained > /workspace/app/session-note'",
            cwd="/workspace",timeout=20)
        identical=http.post("/api/v1/sandbox-bindings",json=attach_body,
                            headers={"Idempotency-Key":key})
        assert identical.json()["bindingId"]==binding["bindingId"]
        reconnected=http.post(
            f"/api/v1/sandbox-bindings/{binding['bindingId']}/reconnect",
            json={"sessionRef":session})
        assert reconnected.status_code==200,reconnected.text[:300]
        retained=Sandbox.connect(native_id).commands.run(
            "cat /workspace/app/session-note",cwd="/workspace",timeout=20)
        assert retained.exit_code==0 and "retained" in retained.stdout
        attack=http.post("/api/v1/sandbox-bindings",json={
            **attach_body,"sessionRef":second,"onAttach":{"commands":[]}},
            headers={"Idempotency-Key":"attacker-"+uuid4().hex})
        assert attack.status_code==409,attack.text[:300]
        unknown=http.post("/api/v1/sandbox-bindings",json={
            **attach_body,"sessionRef":"unknown"},
            headers={"Idempotency-Key":"unknown-"+uuid4().hex})
        assert unknown.status_code==403
        print("SBX_M2_REAL_CUBE_PG_HTTP_PASS",{
            "sandbox_id":native_id,"create_operation_id":info["operationId"],
            "binding_id":binding["bindingId"],"git_clone_fetch_commit":True,
            "reconnect_no_replay":True,"workspace_file_retained":True,
            "cross_session_rejected":True,"invalid_session_rejected":True,
        },flush=True)
    finally:
        if native_id:
            Sandbox.connect(native_id).kill()
            print("SBX_M2_TEST_SANDBOX_CLEANED",native_id,flush=True)


if __name__=="__main__":
    main()