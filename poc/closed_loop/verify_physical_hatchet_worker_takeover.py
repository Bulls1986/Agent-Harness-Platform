"""DEV-M4/5 physical Hatchet Worker A SIGKILL -> independent Worker B, real PG.

Actual process groups (not a fake callback or in-process restart). Each
process joins one Hatchet embedded fleet by the same external Engine PG;
control plane owns Harness PG and unrelated non-idempotent Ledger PG.

First task commits external effect and waits for A to be physically killed.
Hatchet must dispatch a native retry to separately launched Worker B,
which reconciles the original UNKNOWN Tool Receipt under an incremented
PG fencing epoch. No Cube and no external business application involved.
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

ROLE=os.environ.get("HARNESS_M4_FLEET_ROLE","controller")
hatchet=Hatchet.from_embedded(ClientConfig(
    embedded=EmbeddedHatchetConfig(
        database_url=os.environ["HATCHET_POC_DATABASE_URL"],
        run_migrations=(ROLE=="controller"),
    ),
))


class Input(BaseModel):
    run_id: str
    execution_id: str


workflow=hatchet.workflow(
    name="harness-m4-physical-worker-crash-receipt-v1",
    input_validator=Input,
)


@workflow.task(retries=2,backoff_factor=1,execution_timeout=timedelta(seconds=25))
def physical_tool_task(input: Input, ctx: Context) -> dict:
    db=PgFacts()
    journal=ToolReceiptJournal(db)
    ledger=ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"])
    for _ in range(100):
        try:
            intent=journal.inspect(input.execution_id)
            with db.tx() as c:
                run=c.execute(
                    "SELECT state,plan_version,provider_workflow_id "
                    "FROM harness_run WHERE id=%s",(input.run_id,),
                ).fetchone()
                owner=c.execute(
                    "SELECT owner_id,fencing_epoch FROM harness_tool_recovery_authority "
                    "WHERE execution_id=%s",(input.execution_id,),
                ).fetchone()
            if (run==("RUNNING",1,ctx.workflow_run_id) and owner):
                break
        except KeyError:
            # Concurrent controller initialization has not registered its
            # durable Intent yet. Never retry a Tool write from this loop.
            pass
        time.sleep(0.1)
    else:
        raise UnsafeDispatch("Native task failed to obtain bound PG execution facts")

    if ROLE=="worker-A":
        if ctx.retry_count != 0 or intent["state"]!="RECORDED":
            raise UnsafeDispatch("Physical worker A may only execute initial Intent")
        journal.dispatch(input.execution_id,"worker-A",7)
        ledger.debit(input.execution_id,intent["operation"],intent["target"],
                     intent["idempotency_key"])
        # External COMMIT is real and durable, but the Harness Receipt is
        # still DISPATCHED. Control process kills A's entire OS process
        # group, including this task process, before it can store Receipt.
        while True:
            time.sleep(1)

    if ROLE!="worker-B":
        raise UnsafeDispatch("Unexpected worker role")
    if ctx.retry_count < 1:
        raise UnsafeDispatch("B did not receive a true Hatchet native retry")
    if intent["state"] not in ("DISPATCHED","UNKNOWN"):
        raise UnsafeDispatch("Worker B must not re-run a fresh or resolved Tool")
    if intent["state"]=="DISPATCHED":
        # A's OS group was killed and the Engine made a new attempt; do not
        # infer non-execution, transition explicitly to UNKNOWN.
        journal.mark_unknown(input.execution_id,"EXECUTOR_CRASH")
    owner=ToolRecoveryOwner(db)
    permit=owner.takeover(input.execution_id,"worker-B",expected_epoch=7,
                          lease_seconds=90)
    if permit.fencing_epoch != 8:
        raise UnsafeDispatch("B failed to fence A's recovery authority")
    try:
        owner.reconcile(input.execution_id,"worker-A",7,ledger.find)
    except UnsafeDispatch:
        pass
    else:
        raise UnsafeDispatch("Fenced owner A could reconcile after takeover")
    result=owner.reconcile(input.execution_id,"worker-B",8,ledger.find)
    if result!="CONFIRMED_SUCCESS" or len(ledger.find(input.execution_id))!=1:
        raise UnsafeDispatch("B did not reconcile exactly one external effect")
    return {
        "status":"NATIVE_PHYSICAL_B_TAKEOVER_CONFIRMED",
        "run_id":input.run_id,"execution_id":input.execution_id,
        "provider_workflow_id":ctx.workflow_run_id,
        "native_retry_count":ctx.retry_count,
        "actual_worker_role":ROLE,
        "recovery_fencing_epoch":permit.fencing_epoch,
    }


def launch_worker(role: str) -> subprocess.Popen:
    env=dict(os.environ)
    env["HARNESS_M4_FLEET_ROLE"]=role
    return subprocess.Popen(
        [sys.executable,"-B","-m",
         "poc.closed_loop.verify_physical_hatchet_worker_takeover","worker"],
        env=env,stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def wait_for_effect(journal:ToolReceiptJournal,ledger:ExternalLedger,
                    execution_id:str, a:subprocess.Popen):
    until=time.monotonic()+80
    while time.monotonic()<until:
        if a.poll() is not None:
            raise RuntimeError("Physical Worker A exited before fault injection")
        if (journal.inspect(execution_id)["state"]=="DISPATCHED"
                and len(ledger.find(execution_id))==1):
            return
        time.sleep(0.35)
    raise RuntimeError("Worker A did not execute external effect")


def verify():
    db=PgFacts()
    ledger=ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"])
    journal=ToolReceiptJournal(db)
    owner=ToolRecoveryOwner(db)
    rid="m4-physical-"+uuid4().hex
    eid="exec-"+rid
    command=db.create(rid,prompt="synthetic physical failover")
    db.dispatch(command)
    a=launch_worker("worker-A")
    b=None
    try:
        time.sleep(6)
        if a.poll() is not None:
            raise RuntimeError("Physical Worker A failed startup")
        ref=workflow.run(Input(run_id=rid,execution_id=eid),
                         wait_for_result=False)
        db.bind(command,ref.workflow_run_id)
        journal.register_intent(
            rid,1,"nonidempotent-step","attempt-A",eid,
            "worker-A",7,"ledger.debit","synthetic-account","ledger-"+rid,
        )
        # A's short database permit is not the Engine worker lease. It must
        # expire before B may acquire a new application execution permit.
        owner.initialize(eid,"worker-A",7,lease_seconds=2)
        wait_for_effect(journal,ledger,eid,a)
        # Kill the REAL Worker A OS process group, not merely its Tool
        # subprocess. Remaining controller Engine still owns the queue.
        os.killpg(a.pid,signal.SIGKILL)
        a.wait(timeout=12)
        if a.returncode != -signal.SIGKILL:
            raise RuntimeError("Whole Worker A process was not SIGKILLed")
        print("PHYSICAL_WORKER_A_SIGKILL_CONFIRMED",a.pid,flush=True)
        time.sleep(2.5)
        b=launch_worker("worker-B")
        if b.poll() is not None:
            raise RuntimeError("Independent Worker B failed startup")
        out=hatchet.runs.get_run_ref(ref.workflow_run_id).result()
        if not isinstance(out,dict) or len(out)!=1:
            raise RuntimeError("Hatchet did not complete single native task")
        proof=next(iter(out.values()))
        if not isinstance(proof,dict) or proof.get("status")!="NATIVE_PHYSICAL_B_TAKEOVER_CONFIRMED":
            raise RuntimeError("No real B execution proof "+repr(out))
        if (proof.get("provider_workflow_id")!=ref.workflow_run_id
                or proof.get("native_retry_count",0)<1
                or proof.get("actual_worker_role")!="worker-B"
                or proof.get("recovery_fencing_epoch")!=8):
            raise RuntimeError("Hatchet did not genuinely reassign the task")
        if len(ledger.find(eid))!=1:
            raise RuntimeError("Non-idempotent effect duplicated")
        events=db.snapshot(rid)["events"]
        required={"tool.dispatched":1,"tool.outcome.unknown":1,
                  "tool.recovery.owner.transferred":1,
                  "tool.receipt.confirmed":1}
        for name,count in required.items():
            if sum(e["type"]==name for e in events)!=count:
                raise RuntimeError("Incorrect durable event "+name)
        return {
            "outcome":"PASS_PHYSICAL_HATCHET_WORKER_A_B",
            "run_id":rid,"execution_id":eid,
            "provider_workflow_run_id":ref.workflow_run_id,
            "worker_A_pid":a.pid,"worker_A_exit_code":a.returncode,
            "worker_B_pid":b.pid,"native_retry_count":proof["native_retry_count"],
            "external_effect_count":1,"receipt_state":journal.inspect(eid)["state"],
            "recovery_fencing_epoch":8,
            "cube_workspace_reconnect":"NOT_TESTED",
            "business_tool_adapter":"NOT_TESTED",
        }
    finally:
        for proc in (a,b):
            if proc is not None and proc.poll() is None:
                try: os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: pass


def main():
    if len(sys.argv)==2 and sys.argv[1]=="worker":
        worker=hatchet.worker("harness-m4-physical-"+ROLE,
                              workflows=[workflow])
        worker.start()
        return
    if len(sys.argv)!=2 or sys.argv[1]!="controller":
        raise ValueError("Use 'controller' or 'worker'")
    code=0
    try:
        print(json.dumps(verify(),sort_keys=True),flush=True)
    except Exception:
        code=1
        traceback.print_exc()
    finally:
        hatchet.stop_embedded()
        sys.stdout.flush();sys.stderr.flush()
        os._exit(code)


if __name__=="__main__":
    main()
