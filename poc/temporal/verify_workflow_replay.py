"""C12 genuine Temporal OSS Workflow History deterministic replay gate.

Capture a real Native History from OSS Temporal+PostgreSQL, replay it against
the original Workflow code, then replay that same History against a deliberate
incompatible V2 workflow with a new TIMER command before the original ACTIVITY.
Reject V2 before any deployment; Replayer has no Activity implementations and
therefore cannot dispatch Tool/Model/Sandbox effects.

This is a *predeployment replay check*, NOT a real incompatible Worker B image
takeover. The version attestation, Build ID rollout and patch migration remain
separate production gates.
"""
from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from uuid import uuid4

from temporalio.worker import Replayer
from workflow import DocumentReviewWorkflow
from incompatible_workflow_v2 import IncompatibleDocumentReviewWorkflow
from verify_local_handoff import connect_retry, start_worker, stop_worker, wait_phase


async def main() -> None:
    client=await connect_retry()
    queue="poc-c12-"+uuid4().hex[:12]
    run_id="run-"+uuid4().hex
    native_id="temporal-c12-"+uuid4().hex
    attempts=["attempt-"+uuid4().hex,"attempt-"+uuid4().hex]
    worker=None
    try:
        worker=start_worker(queue)
        handle=await client.start_workflow(
            DocumentReviewWorkflow.run,
            {"run_id":run_id,"attempt_ids":attempts},
            id=native_id,task_queue=queue,
            execution_timeout=timedelta(minutes=3),
        )
        await wait_phase(handle,"WAITING_APPROVAL",timeout=35)
        await handle.signal(DocumentReviewWorkflow.decide,"APPROVED")
        completed=await asyncio.wait_for(handle.result(),timeout=35)
        if completed["state"]!="COMPLETED" or completed["plan_version"]!=2:
            raise AssertionError("Real native v1 fixture did not complete")
        history=await handle.fetch_history()
        native_events=len(history.events)
        if native_events < 20:
            raise AssertionError("Incomplete Temporal history")
    finally:
        stop_worker(worker)

    # Tests now run with NO worker running; neither Replayer may call a real
    # Activity, external Tool, HTTP sink, file Sandbox or model provider.
    same=await Replayer(workflows=[DocumentReviewWorkflow]).replay_workflow(
        history,raise_on_replay_failure=False)
    if same.replay_failure is not None:
        raise AssertionError("Unmodified v1 native Workflow failed history replay") from same.replay_failure
    mismatch=await Replayer(
        workflows=[IncompatibleDocumentReviewWorkflow]
    ).replay_workflow(history,raise_on_replay_failure=False)
    if mismatch.replay_failure is None:
        raise AssertionError("INCOMPATIBLE_WORKFLOW_REPLAY_WAS_NOT_REJECTED")
    failure=type(mismatch.replay_failure).__name__
    detail=str(mismatch.replay_failure).lower()
    if "nondetermin" not in (detail+" "+failure.lower()) and "mismatch" not in detail:
        raise AssertionError("Replay failure was not a native command-mismatch/nondeterminism")
    print(json.dumps({
        "status":"PASS_C12_TEMPORAL_NATIVE_HISTORY_REPLAY_COMPATIBILITY",
        "provider":"OSS_Temporal_1.31_Postgres",
        "sdk":"temporalio_1.34.0",
        "native_history_events":native_events,
        "original_workflow_same_version_replayed":True,
        "incompatible_v2_replay_rejected":True,
        "incompatible_native_error_type":failure,
        "incompatible_first_command":"TIMER_BEFORE_OLD_ACTIVITY",
        "same_native_history_for_both_replays":True,
        "replayer_executes_external_activities":False,
        "incompatible_worker_image_takeover_proven":False,
        "production_version_rollout_proven":False,
        "exactly_once_proven":False,
    },sort_keys=True),flush=True)


if __name__=="__main__":
    asyncio.run(main())
