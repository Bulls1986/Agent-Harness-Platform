"""C09 true MAF HarnessAgent ↔ OpenAI Agents SDK runtime swap.

Optional LIVE integration: requires real internal LiteLLM endpoint + private
process-only credential, Temporal OSS+Postgres, independent Harness PG.
Neither key/URL nor actual raw model answer is logged or persisted.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from temporalio.client import Client
from temporalio.worker import Worker

sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime_swap_facts import RuntimeFacts,RuntimeRun
from runtime_swap_workflow import RealRuntimeSwapWorkflow
from verify_local_handoff import connect_retry,stop_worker


async def run_live() -> dict:
    if not all(os.environ.get(n) for n in
               ("POC_C_LITELLM_BASE_URL","POC_C_LITELLM_MODEL",
                "JUSDA_LITELLM_API_KEY","POC_C_PLATFORM_DSN")):
        raise ValueError("Missing live Runtime/Provider process-only configuration")
    store=RuntimeFacts(os.environ["POC_C_PLATFORM_DSN"])
    store.initialize()
    run=RuntimeRun.build()
    store.prepare(run)
    queue="poc-c09-"+uuid4().hex[:12]
    env=os.environ.copy()
    env["POC_C_TASK_QUEUE"]=queue
    env["POC_C_REAL_SWAP"]="1"
    env["POC_C_TEMPORAL_ADDRESS"]=os.environ.get("POC_C_TEMPORAL_ADDRESS",
                                                 "127.0.0.1:17234")
    worker=subprocess.Popen(
        [sys.executable,str(Path(__file__).parent/"worker.py")],
        env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL)
    try:
        client=await Client.connect(env["POC_C_TEMPORAL_ADDRESS"])
        handle=await client.start_workflow(
            RealRuntimeSwapWorkflow.run,run.request(),
            id=run.native_workflow_id,task_queue=queue)
        result=await asyncio.wait_for(handle.result(),timeout=205)
        if (result["state"]!="COMPLETED" or
                result["runtime_swap_verified"] is not True or
                len(result["attempts"])!=2 or
                [a["adapter"] for a in result["attempts"]]!=
                ["maf-harness","openai-agents"] or
                any(not a["passed"] for a in result["attempts"])):
            raise AssertionError("One or both actual Agent SDKs did not Verify PASS")
        snap=RuntimeFacts(store.dsn).snapshot(run.run_id)
        if (snap["run"]["state"]!="COMPLETED" or
                [s["state"] for s in snap["stages"]]!=["SUCCEEDED","SUCCEEDED"] or
                [s["attempt_id"] for s in snap["stages"]]!=
                [x.attempt_id for x in run.stages]):
            raise AssertionError("Harness PG Run/Attempt state or frozen IDs changed")
        names=[event["event_type"] for event in snap["events"]]
        if names!=["run.started","activity.completed","verification.passed",
                  "activity.completed","verification.passed","run.terminal"]:
            raise AssertionError("Both SDKs must produce same immutable Harness event types")
        if [event["seq"] for event in snap["events"]]!=list(range(1,7)):
            raise AssertionError("Harness PG event sequence invalid")
        if any("native_workflow_id" in event["payload"] for event in snap["events"]):
            raise AssertionError("Private Temporal ID leaked into platform events")
        history=[e async for e in handle.fetch_history_events()]
        completed=sum(1 for e in history if e.HasField("activity_task_completed_event_attributes"))
        if completed!=5:
            raise AssertionError("Expected exactly 2 real agents + 2 verify + finalize Activity completions")
        return {
            "status":"PASS_C09_TWO_REAL_AGENT_RUNTIME_SDKS_ONE_TEMPORAL_WORKFLOW",
            "agent_runtimes":["maf-harness","openai-agents"],
            "same_model_gateway":True,
            "both_real_model_requests":True,
            "model_response_contents_persisted":False,
            "platform_run_state":snap["run"]["state"],
            "platform_attempt_count":len(snap["stages"]),
            "platform_verification_passed":2,
            "platform_event_sequence":names,
            "native_workflow_count":1,
            "native_activity_completions":completed,
            "native_history_event_count":len(history),
            "runtime_version_frozen_in_postgres":True,
            "distinct_model_provider_swap_proven":False,
            "sandbox_or_external_tool_swap_proven":False,
        }
    finally:
        stop_worker(worker)


def main() -> int:
    try:
        print(json.dumps(asyncio.run(run_live()),sort_keys=True))
        return 0
    except Exception as exc:
        # Never echo provider exceptions containing URLs, request headers or
        # raw model responses. Error category is sufficient for CI/GAP triage.
        print(json.dumps({"status":"C09_LIVE_GAP",
                          "exception_type":type(exc).__name__},sort_keys=True))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
