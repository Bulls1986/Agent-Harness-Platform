"""Real Hatchet retry bound to HC-02 Receipt UNKNOWN, NOT simulated retries.

Pinned Hatchet SDK + actual embedded Engine + three independent PostgreSQL
DBs. First native task attempt dispatches a deliberately NON-IDEMPOTENT
external effect. Its child Tool Executor is SIGKILLed after external commit,
but before Harness Receipt. The Hatchet task then fails, so Hatchet itself
schedules the next native task attempt. The resumed task ONLY reconciles
external evidence; it never calls the external write again.

This demonstrates Hatchet native retry + durable Receipt integration. It
does NOT demonstrate physical Hatchet Worker A process killed, Worker B
acquisition, actual Cube, or lease handoff.
"""
from __future__ import annotations

from datetime import timedelta
import json
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
from uuid import uuid4

from hatchet_sdk import ClientConfig, Context, EmbeddedHatchetConfig, Hatchet
from pydantic import BaseModel

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.tool_receipt import ToolReceiptJournal
from poc.closed_loop.tool_recovery_owner import ToolRecoveryOwner
from poc.closed_loop.external_ledger_demo import ExternalLedger

hatchet = Hatchet.from_embedded(
    ClientConfig(embedded=EmbeddedHatchetConfig(
        database_url=os.environ["HATCHET_POC_DATABASE_URL"],
        run_migrations=True,
    ))
)


class ReceiptInput(BaseModel):
    run_id: str
    execution_id: str


receipt_workflow = hatchet.workflow(
    name="harness-m4-nonidempotent-receipt-hatchet-v1",
    input_validator=ReceiptInput,
)


def _await_native_binding(rid: str, native_id: str):
    db = PgFacts()
    for _ in range(120):
        with db.tx() as c:
            row = c.execute(
                "SELECT provider_workflow_id,plan_version,state "
                "FROM harness_run WHERE id=%s", (rid,),
            ).fetchone()
        if row == (native_id, 1, "RUNNING"):
            return
        time.sleep(0.25)
    raise UnsafeDispatch("Real Hatchet task lacks confirmed PG provider binding")


@receipt_workflow.task(retries=1,backoff_factor=1,
                       execution_timeout=timedelta(minutes=3))
def nonidempotent_receipt_task(input: ReceiptInput, ctx: Context) -> dict:
    _await_native_binding(input.run_id,ctx.workflow_run_id)
    db=PgFacts()
    journal=ToolReceiptJournal(db)
    ledger=ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"])
    # Hatchet dispatch can beat the control-plane's PG Intent insertion.
    # This loop waits for a persisted source-of-truth fact, not a local cache.
    intent=None
    for _ in range(80):
        try:
            intent=journal.inspect(input.execution_id)
            break
        except KeyError:
            time.sleep(0.25)
    if intent is None or intent["run_id"]!=input.run_id:
        raise UnsafeDispatch("Untrusted execution identity")

    if ctx.retry_count == 0:
        if intent["state"]!="RECORDED":
            raise UnsafeDispatch("First Hatchet attempt must own a fresh Intent")
        journal.dispatch(input.execution_id,"worker-A",7)
        # A separate Tool process is physically killed immediately after
        # its external COMMIT. This does not kill the Hatchet Worker itself.
        process=subprocess.run(
            [sys.executable,"-B","-m",
             "poc.closed_loop.nonidempotent_fault_worker",
             "--execution-id",input.execution_id,
             "--phase","after-commit"],
            capture_output=True,text=True,timeout=30,
        )
        if process.returncode!=-signal.SIGKILL:
            raise RuntimeError(
                "Tool process failed to reach real SIGKILL after commit: "
                + str((process.returncode,process.stderr[-800:])))
        if len(ledger.find(input.execution_id))!=1:
            raise RuntimeError("Real ledger did not persist exactly one effect")
        journal.mark_unknown(input.execution_id,"EXECUTOR_CRASH")
        # Let the short test-only trusted lease expire on the PG clock
        # before Hatchet's native retry becomes eligible to reconcile.
        time.sleep(1.3)
        # Must be retried by Hatchet Engine, not a user-space loop or second
        # scheduler. Native retry count is tested on resumed execution.
        raise RuntimeError("FAULT_INJECTED_RECEIPT_UNKNOWN_AFTER_EXTERNAL_COMMIT")

    if ctx.retry_count < 1:
        raise RuntimeError("Native task did not retry")
    if intent["state"]!="UNKNOWN":
        raise UnsafeDispatch("Resumed Hatchet task may not re-dispatch uncertain Tool")
    # Hatchet owns the technical retry; Harness PG owns the permission
    # transfer. This names two logical owners on successive native task
    # attempts, NOT two physically distinct Hatchet worker processes.
    owner=ToolRecoveryOwner(db)
    permit=owner.takeover(input.execution_id,"worker-B",expected_epoch=7)
    if permit.fencing_epoch!=8:
        raise UnsafeDispatch("New native attempt did not fence old Tool owner")
    try:
        owner.admit(input.execution_id,"worker-A",7)
    except UnsafeDispatch:
        pass
    else:
        raise UnsafeDispatch("Old Tool worker retained stale owner authority")
    result=owner.reconcile(input.execution_id,"worker-B",8,ledger.find)
    if result!="CONFIRMED_SUCCESS":
        raise RuntimeError("Receipt not safely reconciled")
    external_ref=journal.require_confirmed(input.execution_id)
    if len(ledger.find(input.execution_id))!=1:
        raise RuntimeError("Native retry duplicated non-idempotent effect")
    return {
        "status":"RECEIPT_RECONCILED_NATIVE_RETRY",
        "execution_id":input.execution_id,
        "external_reference":external_ref,
        "retry_count":ctx.retry_count,
        "recovery_fencing_epoch":8,
        "provider_workflow_id":ctx.workflow_run_id,
    }


def verify():
    db=PgFacts()
    ledger=ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"])
    journal=ToolReceiptJournal(db)
    rid="m4-native-"+uuid4().hex
    execution="exec-"+rid
    command=db.create(rid,prompt="synthetic non-idempotent native retry")
    db.dispatch(command)
    # A real running Hatchet workflow is necessary: no mocked Task or
    # mocked Context is allowed as proof of provider-native retry.
    ref=receipt_workflow.run(ReceiptInput(run_id=rid,execution_id=execution),
                             wait_for_result=False)
    db.bind(command,ref.workflow_run_id)
    journal.register_intent(
        rid,1,"ledger-step","attempt-1",execution,
        "worker-A",7,"ledger.debit","synthetic-account",
        "ledger-key-"+rid,
    )
    ToolRecoveryOwner(db).initialize(
        execution,"worker-A",7,lease_seconds=1)
    result=hatchet.runs.get_run_ref(ref.workflow_run_id).result()
    if not isinstance(result,dict):
        raise RuntimeError("No real native Hatchet result mapping")
    values=list(result.values())
    if len(values)!=1 or not isinstance(values[0],dict):
        raise RuntimeError("Unexpected Hatchet task output "+repr(result))
    out=values[0]
    if (out.get("status")!="RECEIPT_RECONCILED_NATIVE_RETRY"
            or out.get("retry_count",0)<1
            or out.get("recovery_fencing_epoch")!=8
            or out.get("provider_workflow_id")!=ref.workflow_run_id
            or out.get("execution_id")!=execution):
        raise RuntimeError("Native retry/Receipt proof is incomplete "+repr(out))
    events=db.snapshot(rid)["events"]
    if sum(e["type"]=="tool.dispatched" for e in events)!=1:
        raise RuntimeError("Tool dispatch repeated despite uncertain Receipt")
    if sum(e["type"]=="tool.outcome.unknown" for e in events)!=1:
        raise RuntimeError("Missing UNKNOWN fact")
    if sum(e["type"]=="tool.receipt.confirmed" for e in events)!=1:
        raise RuntimeError("Duplicate/missing durable Receipt")
    if len(ledger.find(execution))!=1:
        raise RuntimeError("Non-idempotent external effect duplicated")
    try:
        journal.dispatch(execution,"worker-A",7)
    except UnsafeDispatch:
        pass
    else:
        raise RuntimeError("Stale worker could replay external effect")
    return {
        "outcome":"PASS_HATCHET_NATIVE_RECEIPT_RETRY",
        "run_id":rid,"execution_id":execution,
        "native_provider_workflow_id":ref.workflow_run_id,
        "hatchet_native_retry_count":out["retry_count"],
        "external_effect_count":1,
        "receipt_state":journal.inspect(execution)["state"],
        "tool_dispatch_events":1,
        "recovery_fencing_epoch":8,
        "logical_owner_transition":"worker-A/7 → worker-B/8",
        "physical_worker_A_SIGKILL":"NOT_TESTED",
        "worker_B_takeover":"NOT_TESTED",
        "cube_fencing":"NOT_TESTED",
    }


def main():
    worker=hatchet.worker("harness-m4-receipt-native-retry-worker",
                         workflows=[receipt_workflow])
    threading.Thread(target=worker.start,daemon=True).start()
    time.sleep(5)
    exit_code=0
    try:
        print(json.dumps(verify(),sort_keys=True),flush=True)
    except Exception:
        exit_code=1
        traceback.print_exc()
    finally:
        hatchet.stop_embedded()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)


if __name__=="__main__":
    main()
