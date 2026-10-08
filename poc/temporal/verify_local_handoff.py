"""C00-C03 real Temporal self-host dev-server + worker-process SIGKILL.

Important: Developer Server (persistent SQLite) is NOT production server/HA.
No cloud or provider model invoked. Same platform Run is *not* Temporal ID.
Two distinct runtime adapter fixtures are Activities; independent verifier
is identical to MAF POC-A trusted document baseline.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from temporalio.client import Client

sys.path.insert(0,str(Path(__file__).resolve().parent))
from workflow import DocumentReviewWorkflow

ROOT=Path(__file__).resolve().parent
ADDRESS=os.environ.get("POC_C_TEMPORAL_ADDRESS","127.0.0.1:17233")


def start_worker(queue: str) -> subprocess.Popen:
    env=os.environ.copy()
    env["POC_C_TASK_QUEUE"]=queue
    env["POC_C_TEMPORAL_ADDRESS"]=ADDRESS
    return subprocess.Popen(
        [sys.executable,str(ROOT/"worker.py")],
        cwd=str(ROOT),env=env,stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
    )


def stop_worker(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        proc.kill()  # real crash, not graceful Worker.shutdown()
        proc.wait(timeout=8)


async def connect_retry(*, timeout: float = 45) -> Client:
    """Temporal container first boot is asynchronous, not a readiness claim."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            return await Client.connect(ADDRESS)
        except Exception as exc:
            last = type(exc).__name__
            await asyncio.sleep(0.5)
    raise RuntimeError(f"Temporal API unavailable: {last}")


async def wait_phase(handle, phase: str, *, timeout: float = 25) -> dict:
    limit=time.monotonic()+timeout
    last=None
    while time.monotonic()<limit:
        try:
            last=await handle.query(DocumentReviewWorkflow.snapshot)
            if last["phase"]==phase:
                return last
        except Exception:
            pass  # worker may not have started polling yet
        await asyncio.sleep(0.35)
    raise TimeoutError("Native Workflow never reached "+phase+"; last="+repr(last))


async def run_case(client: Client, queue: str, decision: str, *,
                   kill_worker_a: bool) -> dict:
    platform_run_id="run-"+uuid4().hex
    native_id="temporal-poc-c-"+uuid4().hex
    attempts=["attempt-"+uuid4().hex,"attempt-"+uuid4().hex]
    handle=await client.start_workflow(
        DocumentReviewWorkflow.run,
        {"run_id":platform_run_id,"attempt_ids":attempts},
        id=native_id,task_queue=queue,
        execution_timeout=__import__("datetime").timedelta(minutes=3),
    )
    if kill_worker_a:
        before=await wait_phase(handle,"WAITING_APPROVAL")
        if len(before["attempts"])!=1 or before["plan_version"]!=1:
            raise AssertionError("Did not pause between failed Verify and Replan")
        return {"handle":handle,"run_id":platform_run_id,"native_id":native_id,
                "attempts":attempts,"before":before}
    await wait_phase(handle,"WAITING_APPROVAL")
    await handle.signal(DocumentReviewWorkflow.decide, decision)
    final=await handle.result()
    return {"handle":handle,"result":final}


async def main() -> None:
    client=await connect_retry()
    queue="poc-c-isolated-"+uuid4().hex[:12]
    worker_a=worker_b=None
    try:
        worker_a=start_worker(queue)
        positive=await run_case(client,queue,"APPROVED",kill_worker_a=True)
        stop_worker(worker_a)
        worker_a=None
        # Native workflow is WAITING on Temporal server, without any Worker.
        # An independent Worker B is created under a different OS PID.
        worker_b=start_worker(queue)
        fresh=await connect_retry()
        recovered=fresh.get_workflow_handle(positive["native_id"])
        await wait_phase(recovered,"WAITING_APPROVAL")
        await recovered.signal(DocumentReviewWorkflow.decide,"APPROVED")
        completed=await recovered.result()
        if completed["state"]!="COMPLETED" or completed["plan_version"]!=2:
            raise AssertionError("Workflow did not deterministically replan")
        if completed["run_id"]!=positive["run_id"] or positive["native_id"]==positive["run_id"]:
            raise AssertionError("Vendor-owned WorkflowId incorrectly became RunId")
        if [a["verification"] for a in completed["attempts"]] != ["FAILED","PASSED"]:
            raise AssertionError("Independent verification/replan contract mismatch")
        if [a["attempt_id"] for a in completed["attempts"]]!=positive["attempts"]:
            raise AssertionError("Task attempt identity changed on failover")
        # SDK public history: count committed native Activity completions.
        hist=[]
        async for evt in recovered.fetch_history_events():
            hist.append(evt)
        completed_activities=sum(1 for evt in hist
                                 if evt.HasField("activity_task_completed_event_attributes"))
        if completed_activities!=4:
            raise AssertionError(f"Expected exactly 4 completed Activities, observed {completed_activities}")
        negative=await run_case(fresh,queue,"REJECTED",kill_worker_a=False)
        rejected=negative["result"]
        if rejected["state"]!="FAILED" or rejected["plan_version"]!=1 or len(rejected["attempts"])!=1:
            raise AssertionError("Approval rejection should stop before replan")
        print(json.dumps({
            "scenario":"C00-C03-TEMPORAL-NATIVE-WORKER-KILL-HITL-REPLAN",
            "status":"PASS",
            "self_hosted_dev_server":ADDRESS.endswith(":17233"),
            "native_address":ADDRESS,
            "production_g1_g6_proven":False,
            "first_worker_sigkill":True,
            "independent_worker_b_continued_same_native_instance":True,
            "native_workflow_id_distinct_from_platform_run_id":True,
            "completed_activity_count":completed_activities,
            "plan_versions":[1,2],
            "attempt_count":2,
            "result_after_approval":"COMPLETED",
            "rejected_case":"FAILED_BEFORE_REPLAN",
            "runtime_adapter_names":["fixture-a","fixture-b"],
            "real_model_or_sandbox_executed":False,
            "event_history_count":len(hist),
        },sort_keys=True),flush=True)
    finally:
        stop_worker(worker_a)
        stop_worker(worker_b)


if __name__=="__main__":
    asyncio.run(main())
