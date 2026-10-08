"""C06/C07 integrated fault chain: 2 PostgreSQL DBs + true Temporal retry.

1. Platform PG commits frozen identity before Temporal start.
2. Worker A admits external dispatch under PG fencing, HTTP sink gets 1 receipt.
3. Worker A is SIGKILL-equivalent via os._exit BEFORE Activity result ACK.
4. Temporal OSS/Postgres starts automatic same Activity retry on Worker B.
5. Platform PG denies second dispatch and quarantines Attempt/Execution UNKNOWN.
6. Native Temporal completed Activity with UNKNOWN task outcome; independent
   read from platform PG proves original Attempt and pending Reconciliation.
"""
from __future__ import annotations
import asyncio
from dataclasses import asdict,replace
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from uuid import uuid4

from temporalio.client import Client

sys.path.insert(0,str(Path(__file__).resolve().parent))
from platform_facts import FrozenTemporal, TemporalTaskFacts, FrozenTemporalMismatch
from guarded_workflow import GuardedNonRetryableWorkflow
from verify_local_handoff import ADDRESS,connect_retry,stop_worker


class ToolSink(BaseHTTPRequestHandler):
    requests=[]
    event=threading.Event()
    def do_POST(self):
        if self.path!="/receipt":
            self.send_error(404)
            return
        n=int(self.headers.get("Content-Length","0"))
        body=json.loads(self.rfile.read(n))
        if set(body)!={"execution_id","attempt_id"}:
            self.send_error(422)
            return
        self.__class__.requests.append(body)
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.end_headers()
        self.wfile.write(b'{"accepted":true}')
        self.wfile.flush()
        self.__class__.event.set()

    def log_message(self,*args):
        pass


def worker(queue: str, actor: str) -> subprocess.Popen:
    env=os.environ.copy()
    env["POC_C_TASK_QUEUE"]=queue
    env["POC_C_TEMPORAL_ADDRESS"]=ADDRESS
    env["POC_C_GUARDED"]="1"
    env["POC_C_WORKER_ACTOR"]=actor
    return subprocess.Popen([sys.executable,str(Path(__file__).parent/"worker.py")],
                            env=env,stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


async def main() -> None:
    store=TemporalTaskFacts(os.environ["POC_C_PLATFORM_DSN"])
    store.initialize()
    queue="poc-c06-"+uuid4().hex[:12]
    binding=FrozenTemporal(
        run_id="run-"+uuid4().hex,plan_id="plan-"+uuid4().hex,
        step_id="step-"+uuid4().hex,attempt_id="attempt-"+uuid4().hex,
        execution_id="execution-"+uuid4().hex,
        native_workflow_id="temporal-c06-"+uuid4().hex)
    store.prepare(binding)
    # Fresh PG connection proves the platform can see the binding without a
    # Temporal Client or Worker running.
    store.require_frozen(binding)
    try:
        store.require_frozen(replace(binding,frozen_workflow_version="v2-forged"))
        raise AssertionError("Incompatible Worker version admitted")
    except FrozenTemporalMismatch:
        pass
    server=ThreadingHTTPServer(("127.0.0.1",0),ToolSink)
    server_thread=threading.Thread(target=server.serve_forever,daemon=True)
    server_thread.start()
    first=second=None
    try:
        client=await connect_retry()
        first=worker(queue,"worker-A")
        handle=await client.start_workflow(
            GuardedNonRetryableWorkflow.run,
            {"binding":asdict(binding),
             "tool_url":f"http://127.0.0.1:{server.server_port}/receipt"},
            id=binding.native_workflow_id,task_queue=queue)
        # The receipt is an actual HTTP request sent from Worker A.
        got=await asyncio.to_thread(ToolSink.event.wait,28)
        if not got or len(ToolSink.requests)!=1:
            raise AssertionError("Native first attempt did not reach external HTTP sink once")
        until=time.monotonic()+9
        while first.poll() is None and time.monotonic()<until:
            await asyncio.sleep(.1)
        if first.poll()!=74:
            raise AssertionError("Worker A did not exit at post-dispatch ACK gap")
        first=None
        second=worker(queue,"worker-B")
        result=await asyncio.wait_for(handle.result(),timeout=48)
        if result["outcome"]!="UNKNOWN" or result["reconciliation"]!="RECONCILIATION_PENDING":
            raise AssertionError("Temporal retried nonretryable Tool as safe success")
        if result["activity_retry_attempt"]!=2:
            raise AssertionError("Temporal did not actually retry Activity")
        if result["pure_retry_attempt"]!=2:
            raise AssertionError("PURE transient failure did not auto-retry")
        if len(ToolSink.requests)!=1:
            raise AssertionError("Duplicate external side effect detected")
        if result["attempt_id"]!=binding.attempt_id:
            raise AssertionError("Native retry forged a new platform Attempt")
        # Query again from a newly constructed PG adapter; no in-memory dict.
        frozen=TemporalTaskFacts(os.environ["POC_C_PLATFORM_DSN"]).snapshot(binding)
        required={"run_state":"RUNNING","attempt_state":"UNKNOWN",
                  "execution_state":"UNKNOWN",
                  "reconciliation_state":"PENDING","dispatch_claimed":True,
                  "fencing_token":2,"native_workflow_id":binding.native_workflow_id}
        for key,value in required.items():
            if frozen.get(key)!=value:
                raise AssertionError("Wrong durable Harness fact "+key+"="+repr(frozen.get(key)))
        history=[event async for event in handle.fetch_history_events()]
        activity_started=sum(e.HasField("activity_task_started_event_attributes") for e in history)
        activity_done=sum(e.HasField("activity_task_completed_event_attributes") for e in history)
        activity_timeout=sum(e.HasField("activity_task_timed_out_event_attributes") for e in history)
        if activity_done!=2:
            raise AssertionError("Expected PURE recovery + 1 classified Tool Activity completion")
        # Typed platform facts remain queryable without Native Temporal API.
        import psycopg
        with psycopg.connect(store.dsn) as platform:
            events=platform.execute(
                "SELECT seq,event_type,payload FROM poc_events WHERE run_id=%s ORDER BY seq",
                (binding.run_id,)).fetchall()
        if [(r[0],r[1]) for r in events] != [(1,"run.started"),(2,"execution.unknown")]:
            raise AssertionError("Immutable Harness typed event sequence lost")
        if events[1][2].get("execution_id") != binding.execution_id:
            raise AssertionError("UNKNOWN event omitted Execution identity")
        print(json.dumps({
            "status":"PASS_C06_C07_TEMPORAL_PG_ACTIVITY_CRASH_FENCE",
            "native_history_events":len(history),
            "native_activity_starts":activity_started,
            "native_activity_completions":activity_done,
            "native_activity_timeout_events":activity_timeout,
            "native_activity_retry_attempt":result["activity_retry_attempt"],
            "pure_activity_retry_attempt":result["pure_retry_attempt"],
            "external_http_sink_receipts":len(ToolSink.requests),
            "worker_a_exit_code":74,
            "worker_b_retried_and_blocked":True,
            "harness_run_state":frozen["run_state"],
            "harness_attempt_state":frozen["attempt_state"],
            "harness_execution_state":frozen["execution_state"],
            "reconciliation_state":frozen["reconciliation_state"],
            "fencing_token":frozen["fencing_token"],
            "one_harness_attempt":True,
            "harness_typed_events":2,
            "native_binding_immutable":True,
            "provider":"OSS_Temporal_1.31_Postgres",
            "exactly_once_external_side_effect_proven":False
        },sort_keys=True),flush=True)
    finally:
        stop_worker(first)
        stop_worker(second)
        server.shutdown()
        server.server_close()


if __name__=="__main__":
    asyncio.run(main())
