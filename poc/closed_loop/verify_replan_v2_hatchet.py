"""Real Hatchet/PG M3 Plan v1→v2 native execution and terminal proof.

Tests PURE, a lost PURE completion callback, and a real synthetic external
non-idempotent ledger effect reconciled before safe Replan continuation.
No production Approval/Cube/real IAM or worker termination ACK is implied.
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
from poc.closed_loop.segment_reconcile import SegmentReconciler
from poc.closed_loop.hatchet_segment_lookup import HatchetSegmentLookup


hatchet = Hatchet.from_embedded(ClientConfig(embedded=EmbeddedHatchetConfig(
    database_url=os.environ["HATCHET_POC_DATABASE_URL"], run_migrations=True,
)))


class SegmentInput(BaseModel):
    run_id: str
    plan_version: int
    with_effect: bool = False
    with_orphan_pure: bool = False


first = hatchet.workflow(name="harness-m3-v1-replan-verifier-v2", input_validator=SegmentInput)
second = hatchet.workflow(name="harness-m3-v2-verified-segment-v2", input_validator=SegmentInput)


@first.task(execution_timeout=timedelta(minutes=2))
async def verify_v1(input: SegmentInput, ctx: Context) -> dict:
    if input.plan_version != 1:
        raise RuntimeError("Unexpected initial Plan version")
    if input.with_effect or input.with_orphan_pure:
        if input.with_effect and input.with_orphan_pure:
            raise UnsafeDispatch('Non-PURE orphan recovery is unsupported')
        # This real Native v1 Task, not the control process, executes the
        # synthetic NON-IDEMPOTENT external effect. Its ACK is then lost.
        from poc.closed_loop.tool_receipt import ToolReceiptJournal
        from poc.closed_loop.external_ledger_demo import ExternalLedger
        db = PgFacts()
        for _ in range(240):
            with db.tx() as c:
                run = c.execute(
                    "SELECT state,provider_workflow_id FROM harness_run WHERE id=%s",
                    (input.run_id,),
                ).fetchone()
                frozen = c.execute(
                    "SELECT provider_workflow_id FROM harness_plan_snapshot "
                    "WHERE run_id=%s AND version=1", (input.run_id,),
                ).fetchone()
            if run == ("RUNNING",ctx.workflow_run_id) and frozen == (ctx.workflow_run_id,):
                break
            await asyncio.sleep(0.25)
        else:
            raise UnsafeDispatch("Native v1 effect did not obtain frozen PG binding")
        if input.with_orphan_pure:
            db.start_step(input.run_id, "pydantic", "pure synthetic verifier",
                          attempt_id="orphan-"+input.run_id)
            # Simulate PG Step completion callback loss while the actual
            # native Hatchet Task returns successfully and becomes terminal.
            return {"verifier":"REPLAN_REQUIRED","plan_version":1,
                    "old_step_state":"RUNNING","lost_step_callback":True}
        journal = ToolReceiptJournal(db)
        execution = "m3-native-effect-" + input.run_id
        journal.register_intent(
            input.run_id,1,"effect-step","v1-effect-attempt",
            execution,"trusted-v1-worker",1,
            "external.write","synthetic-ledger","effect-key-"+input.run_id,
        )
        journal.dispatch(execution,"trusted-v1-worker",1)
        ledger = ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"])
        ledger.debit(execution,"external.write","synthetic-ledger",
                     "effect-key-"+input.run_id)
        journal.mark_unknown(execution,"LOST_ACK")
        return {"verifier":"REPLAN_REQUIRED","plan_version":1,
                "tool_execution_id":execution,"receipt_state":"UNKNOWN"}
    # A deterministic PURE verifier asks for a new plan; no external tool call.
    return {"verifier": "REPLAN_REQUIRED", "plan_version": 1}


@second.task(execution_timeout=timedelta(minutes=2))
async def execute_v2(input: SegmentInput, ctx: Context) -> dict:
    if input.plan_version != 2:
        raise RuntimeError("Unexpected next Plan version")
    # A task may be claimed before the trigger call returns the real provider
    # workflow ID. It does no work until the trusted PG binding is confirmed.
    # Prepare the schema projection once; retry only the read-only admission.
    replan = ReplanV2(PgFacts())
    for _ in range(240):
        try:
            replan.admit(input.run_id, 2, ctx.workflow_run_id)
            break
        except UnsafeDispatch:
            await asyncio.sleep(0.25)
    else:
        raise UnsafeDispatch("v2 task has no confirmed PG Provider binding")
    attempt_id = "native-v2-" + uuid4().hex
    cached = replan.start_step(input.run_id, 2, ctx.workflow_run_id,
                               "verifier", "synthetic-v2-input", attempt_id)
    if cached is None:
        replan.finish_step(input.run_id, 2, ctx.workflow_run_id,
                           "verifier", attempt_id, "VERIFIED_PASS_V2")
    elif cached != "VERIFIED_PASS_V2":
        raise UnsafeDispatch("Cached native verifier result drift")
    return {"segment": "v2", "admission": "PG_CONFIRMED",
            "step_output": "VERIFIED_PASS_V2",
            "provider_workflow_id": ctx.workflow_run_id}


def execute(*, simulate_ack_loss: bool = False, with_effect: bool = False,
            with_orphan_pure: bool = False) -> dict:
    db = PgFacts()
    run_id = "m3-hatchet-" + uuid4().hex
    command = db.create(run_id, prompt="pure synthetic verifier")
    db.dispatch(command)
    ref1 = first.run(SegmentInput(run_id=run_id, plan_version=1,
                                   with_effect=with_effect,
                                   with_orphan_pure=with_orphan_pure),
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
    receipt_count = 0
    if with_effect:
        from poc.closed_loop.tool_receipt import ToolReceiptJournal
        from poc.closed_loop.external_ledger_demo import ExternalLedger
        execution = "m3-native-effect-" + run_id
        journal = ToolReceiptJournal(db)
        ledger = ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"])
        if journal.inspect(execution)["state"]!="UNKNOWN":
            raise RuntimeError("Lost Tool ACK must produce UNKNOWN before promotion")
        if len(ledger.find(execution))!=1:
            raise RuntimeError("External irreversible effect did not occur exactly once")
        try:
            replan.promote(run_id,hatchet.runs.get_status,
                           effect_policy="CONFIRMED_RECEIPTS_ONLY")
        except UnsafeDispatch:
            pass
        else:
            raise RuntimeError("UNKNOWN receipt incorrectly released new Plan")
        if journal.reconcile(execution,ledger.find)!="CONFIRMED_SUCCESS":
            raise RuntimeError("External evidence did not reconcile original Tool")
        receipt_count = len(ledger.find(execution))
    effect_policy = ("CONFIRMED_RECEIPTS_ONLY" if with_effect else "PURE_ONLY")
    key = replan.promote(run_id,hatchet.runs.get_status,
                         effect_policy=effect_policy,
                         resolve_inflight_pure=with_orphan_pure)
    if with_orphan_pure and db.snapshot(run_id)["steps"]["pydantic"]["state"]!="SUPERSEDED":
        raise RuntimeError("Provider completed but old PURE Attempt not superseded")
    if db.snapshot(run_id)["plan_version"] != 2:
        raise RuntimeError("PG did not atomically promote to Plan v2")
    replan.claim(key)
    try:
        ref2 = second.run(SegmentInput(run_id=run_id, plan_version=2),
                          wait_for_result=False,
                          additional_metadata={
                              "harness_command_key": key,
                              "harness_run_id": run_id,
                              "harness_plan_version": "2",
                          })
    except Exception:
        replan.unknown(key)
        raise
    if simulate_ack_loss:
        # Engine has accepted the run, but the platform never receives its
        # returned WorkflowRun ID; durable Outbox remains BLOCKED_UNKNOWN.
        replan.unknown(key)
        if replan.segment(run_id)["state"] != "BLOCKED_UNKNOWN":
            raise RuntimeError("Simulated ACK loss did not block dispatch")
        lookup = HatchetSegmentLookup(second.list_runs)
        recovered = SegmentReconciler(PgFacts()).reconcile_unknown(
            key, lambda command_key: lookup.find(command_key, run_id, 2))
        if recovered != ref2.workflow_run_id:
            raise RuntimeError("Native recovered WorkflowRun does not match actual created workflow")
    else:
        replan.bind(key, ref2.workflow_run_id)
    r2 = hatchet.runs.get_run_ref(ref2.workflow_run_id).result()
    if not isinstance(r2, dict) or not any(
        isinstance(x, dict) and x.get("admission") == "PG_CONFIRMED"
        for x in r2.values()
    ):
        raise RuntimeError("Actual second Hatchet Workflow did not pass PG v2 admission")
    if not any(isinstance(x,dict) and x.get("step_output")=="VERIFIED_PASS_V2"
               for x in r2.values()):
        raise RuntimeError("Native v2 Step has no verified persisted result")
    native2 = hatchet.runs.get_status(ref2.workflow_run_id)
    if getattr(native2, "value", None) != "COMPLETED":
        raise RuntimeError("v2 Provider is not actually completed")
    terminal = replan.complete(run_id, 2, ref2.workflow_run_id,
                               verified_outputs={"verifier":"VERIFIED_PASS_V2"})
    if terminal["plan_version"]!=2 or terminal["final_output"]!="VERIFIED_PASS_V2":
        raise RuntimeError("v2 business terminal result mismatch")
    if with_effect and (
        terminal["side_effect_policy"] != "CONFIRMED_RECEIPTS_ONLY"
        or len(terminal["reconciled_receipts"])!=1
        or len(ledger.find(execution))!=receipt_count
    ):
        raise RuntimeError("v2 business receipt lineage or non-duplication mismatch")
    if ref1.workflow_run_id == ref2.workflow_run_id:
        raise RuntimeError("Replan reused the old Provider WorkflowRun")
    snap = db.snapshot(run_id)
    with_v2 = replan.segment(run_id)
    if snap["state"]!="COMPLETED" or replan.step_facts(run_id,2)["verifier"]["state"]!="COMPLETED":
        raise RuntimeError("v2 Platform Run/Step/Attempt not terminal")
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
        "outcome": "PASS_VERIFIED_M3_V2", "run_id": run_id,
        "old_provider_workflow_id": ref1.workflow_run_id,
        "new_provider_workflow_id": ref2.workflow_run_id,
        "native_old_provider_status": str(getattr(native, "value", native)),
        "active_plan_version": snap["plan_version"], "segment_state": with_v2["state"],
        "business_terminal":snap["state"], "v2_step_state":"COMPLETED",
        "native_new_provider_status":native2.value,
        "events": len(snap["events"]),
        "tool_receipts": "CONFIRMED_SUCCESS" if with_effect else "NONE_PURE",
        "old_pure_attempt_superseded":with_orphan_pure,
        "simulated_creation_ack_loss": simulate_ack_loss,
        "non_pure_external_effect": with_effect,
        "external_effect_count": receipt_count,
        "old_worker_cancel_ack": "NOT_TESTED",
        "side_effect_recovery": "EXTERNAL_LEDGER_CONFIRMED" if with_effect else "NOT_APPLICABLE",
    }


def main():
    worker = hatchet.worker("harness-m3-replan-v2-verification",
                            workflows=[first, second])
    threading.Thread(target=worker.start, daemon=True).start()
    time.sleep(5)
    code = 0
    try:
        print(json.dumps(execute(), sort_keys=True), flush=True)
        print(json.dumps(execute(simulate_ack_loss=True), sort_keys=True), flush=True)
        print(json.dumps(execute(simulate_ack_loss=True, with_effect=True), sort_keys=True), flush=True)
        print(json.dumps(execute(with_orphan_pure=True), sort_keys=True), flush=True)
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