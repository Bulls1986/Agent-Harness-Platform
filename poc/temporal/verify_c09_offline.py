"""C09 offline native Temporal Workflow + real Harness PG contract.

Adapter Activity here is an EXPLICIT STUB. This CI test cannot establish real
Agent SDK swap. Real remote SDK evidence is only verify_c09_real_runtime.py.
"""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker
from runtime_swap_facts import RuntimeFacts,RuntimeRun
from runtime_swap_workflow import RealRuntimeSwapWorkflow


@activity.defn(name="c09_real_agent_runtime")
async def fake_agent(request:dict) -> dict:
    return {"run_id":request["run_id"],"attempt_id":request["stage"]["attempt_id"],
            "adapter":request["stage"]["adapter"],
            "observed_marker":request["expected_marker"],"output_chars":12,
            "real_model_called":False} # explicitly not a real model


@activity.defn(name="c09_independent_verify")
async def verify_stub_runtime(request:dict) -> dict:
    if request["model_result"]["real_model_called"] is not False:
        raise AssertionError("C09 offline test must never pretend to be live")
    store=RuntimeFacts(os.environ["POC_C_PLATFORM_DSN"])
    return store.verify(request["run_id"],request["stage"],
                        request["model_result"]["observed_marker"],12)


@activity.defn(name="c09_finalize_platform_run")
async def finish_stub_runtime(request:dict) -> dict:
    store=RuntimeFacts(os.environ["POC_C_PLATFORM_DSN"])
    return (store.fail(request["run_id"]) if request.get("failed") else
            store.complete(request["run_id"]))


async def main():
    store=RuntimeFacts(os.environ["POC_C_PLATFORM_DSN"])
    store.initialize()
    run=RuntimeRun.build()
    store.prepare(run)
    addr=os.environ.get("POC_C_TEMPORAL_ADDRESS","127.0.0.1:17234")
    client=await Client.connect(addr)
    queue="poc-c09-offline-"+uuid4().hex[:12]
    worker=Worker(client,task_queue=queue,workflows=[RealRuntimeSwapWorkflow],
                  activities=[fake_agent,verify_stub_runtime,finish_stub_runtime])
    async with worker:
        result=await client.execute_workflow(
            RealRuntimeSwapWorkflow.run,run.request(),
            id=run.native_workflow_id,task_queue=queue)
    snap=RuntimeFacts(store.dsn).snapshot(run.run_id)
    names=[e["event_type"] for e in snap["events"]]
    if (result["state"]!="COMPLETED" or
            snap["run"]["state"]!="COMPLETED" or
            [x["state"] for x in snap["stages"]]!=["SUCCEEDED","SUCCEEDED"] or
            names!=["run.started","activity.completed","verification.passed",
                    "activity.completed","verification.passed","run.terminal"]):
        raise AssertionError("C09 native Workflow / PG event contract mismatch")
    print(json.dumps({"status":"PASS_C09_OFFLINE_WORKFLOW_CONTRACT",
                      "real_model_invoked":False,"adapter_activity_stub":True,
                      "native_workflows":1,"platform_attempts":2,
                      "platform_typed_events":len(names)},sort_keys=True))


if __name__=="__main__":
    asyncio.run(main())
