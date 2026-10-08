"""C16 real non-idempotent durable external Tool + Native Worker kill + receipt.

Business Tool uses a separate SQLite WAL store and intentionally applies
EVERY POST; no fake effect, no idempotent/deduplicated service shortcut.
"""
from __future__ import annotations
import asyncio
from dataclasses import asdict,replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import socket
import subprocess
import sys
from urllib.error import HTTPError,URLError
from urllib.request import urlopen,Request
from uuid import uuid4

from temporalio.client import Client

from platform_facts import FrozenTemporal,TemporalTaskFacts
from guarded_workflow import GuardedNonRetryableWorkflow
from c16_receipt_reconcile import ReceiptReconciler
from verify_c06_c07 import worker
from verify_local_handoff import stop_worker


def open_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1",0))
        return s.getsockname()[1]

def sink_proc(port,file):
    return subprocess.Popen(
        [sys.executable,str(Path(__file__).parent/"c16_receipt_sink.py"),
         "--port",str(port),"--sqlite",str(file)],
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)

def restartable_stop(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)

async def receipt(port,execution):
    url=f"http://127.0.0.1:{port}/receipt/{execution}"
    for _ in range(120):
        try:
            with urlopen(url,timeout=2) as resp:
                return json.loads(resp.read())
        except (URLError,HTTPError,ConnectionError):
            await asyncio.sleep(.15)
    raise AssertionError("Real external Tool Receipt never appeared")

async def smoke():
    store=TemporalTaskFacts(os.environ["POC_C_PLATFORM_DSN"])
    store.initialize()
    reconciler=ReceiptReconciler(store.dsn)
    reconciler.initialize()
    binding=FrozenTemporal(
        run_id="run-"+uuid4().hex,plan_id="plan-"+uuid4().hex,
        step_id="step-"+uuid4().hex,attempt_id="attempt-"+uuid4().hex,
        execution_id="execution-"+uuid4().hex,
        native_workflow_id="temporal-c16-"+uuid4().hex)
    store.prepare(binding)
    with TemporaryDirectory(prefix="poc-c16-external-ledger-",ignore_cleanup_errors=True) as tmp:
        port=open_port()
        db=Path(tmp)/"business-ledger.sqlite"
        sink=sink_proc(port,db)
        a=b=None
        try:
            q="poc-c16-"+uuid4().hex[:12]
            client=await Client.connect(os.environ.get("POC_C_TEMPORAL_ADDRESS",
                                                       "127.0.0.1:17234"))
            a=worker(q,"worker-A")
            handle=await client.start_workflow(
                GuardedNonRetryableWorkflow.run,
                {"binding":asdict(binding),
                 "tool_url":f"http://127.0.0.1:{port}/receipt"},
                id=binding.native_workflow_id,task_queue=q)
            response=await receipt(port,binding.execution_id)
            if (response["effect_count"]!=1 or len(response["receipts"])!=1 or
                    response["receipts"][0]["attempt_id"]!=binding.attempt_id):
                raise AssertionError("Side-effect ledger did not commit exactly one receipt")
            for _ in range(140):
                if a.poll() is not None:break
                await asyncio.sleep(.1)
            if a.poll()!=74:
                raise AssertionError("Native Worker A did not crash after true external COMMIT")
            a=None
            b=worker(q,"worker-B")
            outcome=await asyncio.wait_for(handle.result(),timeout=48)
            if outcome["outcome"]!="UNKNOWN" or outcome["activity_retry_attempt"]!=2:
                raise AssertionError("Native Activity retry ignored side effect fencing")
            snapshot=store.snapshot(binding)
            if (snapshot["attempt_state"]!="UNKNOWN" or
                    snapshot["execution_state"]!="UNKNOWN" or
                    snapshot["reconciliation_state"]!="PENDING"):
                raise AssertionError("UNKNOWN quarantine not durable")
            # Restart the BUSINESS service; its actual receipt survives by WAL.
            restartable_stop(sink);sink=None
            sink=sink_proc(port,db)
            other=await receipt(port,binding.execution_id)
            if other["effect_count"]!=1 or other!=response:
                raise AssertionError("External durable Receipt not readable after business process restart")
            try:
                reconciler.reconcile(replace(binding,attempt_id="forged"),f"http://127.0.0.1:{port}")
                raise AssertionError("C16 forged Attempt unexpectedly reconciled")
            except ValueError:
                pass
            proof=await asyncio.to_thread(reconciler.reconcile,binding,
                                          f"http://127.0.0.1:{port}")
            if proof["state"]!="RESOLVED" or proof["external_effect_count"]!=1:
                raise AssertionError("C16 trustworthy receipt did not resolve UNKNOWN")
            repeated=await asyncio.to_thread(reconciler.reconcile,binding,
                                              f"http://127.0.0.1:{port}")
            if not repeated["idempotent"] or repeated["receipt_id"]!=proof["receipt_id"]:
                raise AssertionError("Repeat reconciliation must be idempotent")
            final=store.snapshot(binding)
            if (final["reconciliation_state"]!="RESOLVED" or
                final["attempt_state"]!="UNKNOWN" or final["execution_state"]!="UNKNOWN" or
                final["run_state"]!="RUNNING"):
                raise AssertionError("Immutable historical UNKNOWN was improperly rewritten")
            after=await receipt(port,binding.execution_id)
            if after["effect_count"]!=1:
                raise AssertionError("Reconciliation re-dispatched non-idempotent effect")
            import psycopg
            with psycopg.connect(store.dsn) as pg:
                events=pg.execute("SELECT seq,event_type FROM poc_events WHERE run_id=%s ORDER BY seq",
                                  (binding.run_id,)).fetchall()
                receipt_rows=pg.execute("SELECT count(*) FROM poc_c16_reconciled_receipts WHERE execution_id=%s",
                                       (binding.execution_id,)).fetchone()[0]
            if [x[1] for x in events]!=["run.started","execution.unknown","execution.reconciled"] or receipt_rows!=1:
                raise AssertionError("Trusted reconciled platform event/receipt missing")
            return {
                "status":"PASS_C16_REAL_NONIDEMPOTENT_TOOL_DURABLE_RECEIPT_RECONCILIATION",
                "external_business_effect_commits":1,
                "external_business_service_restarted":True,
                "actual_worker_A_exit_code":74,
                "native_activity_retry_blocked":True,
                "attempt_execution_unknown_immutable":True,
                "trusted_external_get_receipt":True,
                "platform_reconciliation":"RESOLVED",
                "duplicate_reconciler_idempotent":True,
                "platform_typed_events":3,
                "platform_run_terminal":False,
                "enterprise_mcp_signed_receipt_proven":False,
                "business_replan_or_terminal_decision_proven":False,
            }
        finally:
            stop_worker(a);stop_worker(b);restartable_stop(sink)

if __name__=="__main__":
    try:print(json.dumps(asyncio.run(smoke()),sort_keys=True))
    except Exception as exc:
        print(json.dumps({"status":"G6_RECEIPT_GAP","category":type(exc).__name__}))
        raise
