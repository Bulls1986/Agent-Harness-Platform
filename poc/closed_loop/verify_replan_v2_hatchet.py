"""Real Hatchet Engine + PG M3 v1→v2 Workflow Segment proof (PURE only).

Two different actual Hatchet WorkflowRun IDs, same Platform Run and
versioned frozen Plans. Only native provider COMPLETED releases v2; no
cancellation, tools, approval, non-idempotent Receipt or Cube supported.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import os
import threading
import time
from uuid import uuid4

from hatchet_sdk import Hatchet, ClientConfig, Context, EmbeddedHatchetConfig
from pydantic import BaseModel

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.plan_guard import PlanGuard
from poc.closed_loop.replan_v2 import ReplanV2


hatchet = Hatchet.from_embedded(ClientConfig(embedded=EmbeddedHatchetConfig(
    database_url=os.environ["HATCHET_POC_DATABASE_URL"], run_migrations=True,
)))


class SegmentInput(BaseModel):
    run_id: str
    plan_version: int


first = hatchet.workflow(name="harness-m3-pure-v1-verifier", input_validator=SegmentInput)
second = hatchet.workflow(name="harness-m3-pure-v2-segment", input_validator=SegmentInput)


@first.task(execution_timeout=timedelta(minutes=2))
async def verify_v1(input: SegmentInput, ctx: Context) -> dict:
    if input.plan_version != 1:
        raise RuntimeError("Unexpected initial Plan version")
    # A deterministic PURE verifier asks for a new plan; no external tool call.
    return {"verifier": "REPLAN_REQUIRED", "plan_version": 1}


@second.task(execution_timeout=timedelta(minutes=2))
async def execute_v2(input: SegmentInput, ctx: Context) -> dict:
    if input.plan_version != 2:
        raise RuntimeError("Unexpected next Plan version")
    # A task may be claimed before the trigger call returns the real provider
    # workflow ID. It does no work until the trusted PG binding is confirmed.
    for _ in range(80):
        try:
            ReplanV2(PgFacts()).admit(input.run_id, 2, ctx.workflow_run_id)
            break
        except UnsafeDispatch:
            await asyncio.sleep(0.25)
    else:
        raise UnsafeDispatch("v2 task has no confirmed PG Provider binding")
    return {"segment": "v2", "admission": "PG_CONFIRMED",
            "provider_workflow_id": ctx.workflow_run_id}


def execute() -> dict:
    db = PgFacts()
    run_id = "m3-hatchet-" + uuid4().hex
    command = db.create(run_id, prompt="pure synthetic verifier")
    db.dispatch(command)
    ref1 = first.run(SegmentInput(run_id=run_id, plan_version=1),
                     wait_for_result=False)
    db.bind(command, ref1.workflow_run_id)
    guard = PlanGuard(db)
    guard.freeze_initial(run_id, "sha256:pure-m3-v1")
    r1 = hatchet.runs.get_run_ref(ref1.workflow_run_id).result()
    if not isinstance(r1, dict) or not any(
        isinstance(x, dict) and x.get("verifier") == "REPLAN_REQUIRED"
        for x in r1.values()
    ):
        raise RuntimeError("True v1 Provider did not return replan verdict")
    guard.request_replan(run_id, 1, "sha256:pure-m3-v2", "verified replan needed")
    replan = ReplanV2(db)
    native = hatchet.runs.get_status(ref1.workflow_run_id)
    key = replan.promote(run_id, hatchet.runs.get_status)
    if db.snapshot(run_id)["plan_version"] != 2:
        raise RuntimeError("PG did not atomically promote to Plan v2")
    replan.claim(key)
    try:
        ref2 = second.run(SegmentInput(run_id=run_id, plan_version=2),
                          wait_for_result=False)
    except Exception:
        replan.unknown(key)
        raise
    replan.bind(key, ref2.workflow_run_id)
    r2 = hatchet.runs.get_run_ref(ref2.workflow_run_id).result()
    if not isinstance(r2, dict) or not any(
        isinstance(x, dict) and x.get("admission") == "PG_CONFIRMED"
        for x in r2.values()
    ):
        raise RuntimeError("Actual second Hatchet Workflow did not pass PG v2 admission")
    if ref1.workflow_run_id == ref2.workflow_run_id:
        raise RuntimeError("Replan reused the old Provider WorkflowRun")
    snap = db.snapshot(run_id)
    with_v2 = replan.segment(run_id)
    if not with_v2 or with_v2["state"] != "CONFIRMED":
        raise RuntimeError("Second Segment Provider binding not confirmed")
    if not any(e["type"] == "plan.replan.committed" for e in snap["events"]):
        raise RuntimeError("Missing persisted Replan decision")
    try:
        guard.admit(run_id, 1, ref1.workflow_run_id)
    except UnsafeDispatch:
        pass
    else:
        raise RuntimeError("Old Plan v1 still has admission after v2")
    return {
        "outcome": "PASS_LIMITED_PURE_M3", "run_id": run_id,
        "old_provider_workflow_id": ref1.workflow_run_id,
        "new_provider_workflow_id": ref2.workflow_run_id,
        "native_old_provider_status": str(getattr(native, "value", native)),
        "active_plan_version": snap["plan_version"], "segment_state": with_v2["state"],
        "events": len(snap["events"]), "tools_or_receipts": "NOT_TESTED",
        "old_worker_cancel_ack": "NOT_TESTED", "side_effect_recovery": "NOT_TESTED",
    }


def main():
    worker = hatchet.worker("harness-m3-replan-v2-verification",
                            workflows=[first, second])
    threading.Thread(target=worker.start, daemon=True).start()
    time.sleep(5)
    code = 0
    try:
        print(json.dumps(execute(), sort_keys=True), flush=True)
    except Exception:
        code = 1
        import traceback
        traceback.print_exc()
    finally:
        hatchet.stop_embedded()
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


if __name__ == "__main__":
    main()
