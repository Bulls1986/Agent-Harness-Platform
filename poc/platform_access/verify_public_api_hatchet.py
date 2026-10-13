"""DEV-M7 real LIVE-ENGINE gate: public versioned HTTP -> Hatchet -> 2 SDKs -> PG.

No fake workflow success: Hatchet Embedded runs against a *separate* actual
PostgreSQL engine database and PgFacts stores business history in harness_poc.
The external gateway identity/policy callback here is SYNTHETIC trusted
adapter, explicitly NOT an enterprise IdP integration test.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
import threading
import time
from uuid import uuid4

from fastapi.testclient import TestClient

from poc.closed_loop.facts import PgFacts
from poc.closed_loop.hatchet_pg_live import hatchet,workflow,execute
from poc.closed_loop.real_model import ModelConfiguration
from poc.platform_access.authorized_reads import SecurityContext
from poc.platform_access.pg_reader import PgRunReader
from poc.platform_access.conversation_pg import PgConversationStore
from poc.platform_access.platform_api import create_platform_app


def verify():
    if not os.getenv("HARNESS_POC_DATABASE_URL") or not os.getenv("HATCHET_POC_DATABASE_URL"):
        raise RuntimeError("Actual separate PostgreSQL Harness/Hatchet databases required")
    cfg=ModelConfiguration.from_env()
    if cfg.mode != "deterministic_local_model":
        raise RuntimeError("Deterministic dual-SDK Native CI must not use external model creds")
    executor=ThreadPoolExecutor(max_workers=2,thread_name_prefix="m7-hatchet-submit")
    calls=[]
    def native_submit(rid,prompt,key):
        calls.append((rid,key))
        return executor.submit(execute,rid,prompt,command=key)

    worker=hatchet.worker("harness-m7-public-api-native-worker",workflows=[workflow])
    t=threading.Thread(target=worker.start,daemon=True)
    t.start()
    time.sleep(5) # identical approved actual Hatchet POC worker readiness baseline
    try:
        facts=PgFacts()
        store=PgConversationStore(facts)
        ctx=SecurityContext("synthetic-initiator","USER","synthetic-project")
        current=[ctx]
        active=[True]
        app=create_platform_app(
            resolve_context=lambda _: current[0],
            reader=PgRunReader(PgFacts()),store=store,
            authorize=lambda *_: active[0],
            authorize_create=lambda *_: active[0],
            admit_recipe=lambda agent,recipe: (
                agent=="dual-sdk-requirements-review@v1"
                and recipe=="requirements-review@v1"
            ),
            start_run=native_submit,
            model_binding=lambda:(cfg.mode,cfg.model_id),
            sse_max_polls=1,
            cancel_run=PgFacts().request_cancel,
        )
        client=TestClient(app)
        cid=client.post("/api/v1/conversations",json={
            "title":"Synthetic Requirements Validation"
        })
        assert cid.status_code==201,cid.text
        cid=cid.json()["conversation_id"]
        turn=client.post(f"/api/v1/conversations/{cid}/turns",json={
            "message":"Validate an example approval screen",
            "agent_ref":"dual-sdk-requirements-review@v1",
            "recipe_ref":"requirements-review@v1",
        })
        assert turn.status_code==201,turn.text
        tid=turn.json()["turn_id"]
        key="native-"+uuid4().hex
        path=f"/api/v1/turns/{tid}/runs"
        created=client.post(path,headers={"Idempotency-Key":key})
        assert created.status_code==202,created.text
        rid=created.json()["run_id"]
        again=client.post(path,headers={"Idempotency-Key":key})
        assert again.status_code==202,again.text
        assert again.json()["run_id"]==rid and again.json()["replayed"]
        assert len(calls)==1,"HTTP retries must not duplicate Native workflow dispatch"
        deadline=time.monotonic()+175
        while time.monotonic()<deadline:
            snap=client.get(f"/api/v1/runs/{rid}")
            assert snap.status_code==200,snap.text
            data=snap.json()
            if data["state"]=="COMPLETED":
                break
            time.sleep(0.4)
        else:
            raise TimeoutError("Native Hatchet Provider did not complete Platform Run")
        assert data["provider_workflow_run_id"],"Need actual Hatchet WorkflowRun ID"
        assert data["outbox"]=="CONFIRMED"
        assert data["result"]["result_source_step"]=="openai"
        assert data["result"]["final_output"]=="openai-sdk-real-run"
        assert data["steps"]["pydantic"]["output"]=="pydantic-sdk-real-run"
        assert data["steps"]["openai"]["output"]=="openai-sdk-real-run"
        assert [e["seq"] for e in data["events"]]==list(range(1,len(data["events"])+1))
        e=client.get(f"/api/v1/runs/{rid}/events?after=0&limit=250")
        assert e.status_code==200 and e.json()["cursor"]==data["events"][-1]["seq"]
        stream=client.get(f"/api/v1/runs/{rid}/stream")
        assert stream.status_code==200 and f"id: {rid}:" in stream.text
        resume=client.get(f"/api/v1/runs/{rid}/stream",headers={
            "Last-Event-ID":f"{rid}:{e.json()['cursor']}"
        })
        assert resume.status_code==200 and f"id: {rid}:" not in resume.text
        view=client.get(f"/api/v1/conversations/{cid}")
        assert view.status_code==200 and view.json()["turns"][0]["run_ids"]==[rid]
        html=client.get(f"/ui/conversations/{cid}")
        assert html.status_code==200
        current[0]=SecurityContext("synthetic-other","USER","synthetic-project")
        for endpoint in (
            f"/api/v1/runs/{rid}",f"/api/v1/runs/{rid}/events",
            f"/api/v1/runs/{rid}/stream",f"/api/v1/conversations/{cid}",
        ):
            denied=client.get(endpoint)
            assert denied.status_code==404,(endpoint,denied.status_code)
        current[0]=ctx;active[0]=False
        assert client.get(f"/api/v1/runs/{rid}/events").status_code==404
        return {
            "status":"PASS","gate":"DEV-M7_NATIVE_HATCHET_TWO_SDK_V1",
            "platform_run_id":rid,
            "hatchet_workflow_run_id":data["provider_workflow_run_id"],
            "conversation_id":cid,"turn_id":tid,
            "business_state":data["state"],
            "native_dispatch_count":len(calls),
            "event_count":len(data["events"]),
            "auth":"SYNTHETIC_TRUSTED_GATEWAY_CALLBACK_NOT_ENTERPRISE_IDP",
            "provider":"REAL_HATCHET_EMBEDDED_EXTERNAL_POSTGRESQL",
            "sdk_a":"REAL_PYDANTIC_AI_LOCAL_FUNCTION_MODEL",
            "sdk_b":"REAL_OPENAI_AGENTS_LOCAL_MODEL",
            "live_remote_llm":"NOT_TESTED",
            "actual_enterprise_gateway":"NOT_TESTED",
        }
    finally:
        executor.shutdown(wait=False,cancel_futures=True)
        hatchet.stop_embedded()


def main():
    import traceback
    status=1
    try:
        evidence=verify()
        print(json.dumps(evidence,sort_keys=True),flush=True)
        status=0
    except Exception:
        traceback.print_exc()
    finally:
        # Embedded Hatchet process lifecycle must not hold CI after shutdown.
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(status)


if __name__=="__main__":
    main()
