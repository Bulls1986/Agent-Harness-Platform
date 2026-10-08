"""Actual MAF Durable Functions/MSSQL /run ACK-loss via a loopback TCP proxy.

The proxy sends exactly one real Native /run, receives its provider ID, then
closes the downstream HTTP socket before the Harness adapter receives the ACK.
We verify the official read-only /status endpoint and reject the pending HITL
request to avoid leaving a live orphan fixture. Real PostgreSQL uses the
production NativeStartAckCoordinator, not a test SQL transition.

DOES NOT crash the Functions Worker or establish enterprise HA. Explicitly
requires POC_OFFICIAL_NATIVE_BASE_URL set to a trusted local MAF/MSSQL server;
not run implicitly during generic CI PostgreSQL test discovery.
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import psycopg

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"functions-mssql"))
import verify_handoff as official

from durable_approval_binding import DurableBindingMismatch
from durable_launch_intent import DurableLaunchIntentStore,NativeLaunchIntent
from native_start_ack import NativeStartAckCoordinator
from task_ledger import TaskLedger
from workflow_probe import VerificationFact

OFFICIAL_URL=os.environ.get("POC_OFFICIAL_NATIVE_BASE_URL","")
ROUTE="/api/workflow/maf_mssql_poc_hitl"


class AckDropProxy(BaseHTTPRequestHandler):
    def log_message(self,*args):pass

    def do_POST(self):
        if self.path!="/run":
            self.send_error(404)
            return
        body=self.rfile.read(int(self.headers["Content-Length"]))
        self.server.post_count+=1
        req=urllib.request.Request(
            OFFICIAL_URL+ROUTE+"/run",data=body,method="POST",
            headers={"Content-Type":"application/json"},
        )
        with urllib.request.urlopen(req,timeout=18) as response:
            result=json.load(response)
        self.server.native_instance=result.get("instanceId")
        # A real TCP ACK loss at the adapter-side proxy boundary. The
        # upstream MAF Functions Durable /run has already committed.
        self.connection.shutdown(socket.SHUT_RDWR)
        self.close_connection=True


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN") and
                     os.environ.get("POC_OFFICIAL_NATIVE_BASE_URL"),
                     "explicit official MAF MSSQL endpoint + isolated PostgreSQL required")
class OfficialNativeStartAckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_POSTGRES_DSN"]
        TaskLedger(cls.dsn).initialize()
        cls.coordinator=NativeStartAckCoordinator(cls.dsn)
        cls.ledger=TaskLedger(cls.dsn)

    def test_real_native_instance_committed_but_tcp_ack_dropped(self):
        official.BASE=OFFICIAL_URL
        with urllib.request.urlopen(OFFICIAL_URL+"/api/health",timeout=6) as response:
            self.assertEqual(response.status,200)
        fact=VerificationFact.example(passed=False,evidence_ref=None)
        eid=self.ledger.start(fact)
        intent=NativeLaunchIntent(
            run_id=fact.run_id,step_id=fact.step_id,
            attempt_id=fact.attempt_id,execution_id=eid,
            native_workflow_name="maf_mssql_poc_hitl",
            frozen_workflow_version="poc-ack-test-v1",
            frozen_runtime_version="maf-functions-mssql-fixture-v1",
        )
        case="rejected-fixture-"+uuid4().hex[:12]
        proxy=ThreadingHTTPServer(("127.0.0.1",0),AckDropProxy)
        proxy.post_count=0
        proxy.native_instance=None
        thread=threading.Thread(target=proxy.serve_forever,daemon=True)
        thread.start()
        instance=None
        try:
            def provider_call():
                req=urllib.request.Request(
                    f"http://127.0.0.1:{proxy.server_port}/run",
                    data=json.dumps(case).encode(),method="POST",
                    headers={"Content-Type":"application/json"},
                )
                with urllib.request.urlopen(req,timeout=22) as response:
                    return json.load(response)["instanceId"]

            outcome=self.coordinator.start_once(intent,native_start=provider_call)
            self.assertEqual(outcome.state,"UNKNOWN_RECONCILIATION_PENDING")
            self.assertEqual(proxy.post_count,1)
            instance=proxy.native_instance
            self.assertIsNotNone(instance,"Native upstream returned no official ID")
            self.assertRegex(instance,r"^[0-9a-f]{32}$")
            request_id=official.pending(instance,60)
            self.assertTrue(request_id)
            self.assertEqual(
                DurableLaunchIntentStore(self.dsn).inspect(intent).state,
                "RECONCILIATION_PENDING",
            )
            with self.assertRaises(DurableBindingMismatch):
                self.coordinator.start_once(intent,native_start=provider_call)
            self.assertEqual(proxy.post_count,1)
            with psycopg.connect(self.dsn) as conn:
                got=conn.execute(
                    """SELECT a.state,e.state,r.state,
                              (SELECT count(*) FROM poc_maf_durable_running_bindings
                               WHERE execution_id=e.execution_id)
                       FROM poc_attempts a
                       JOIN poc_executions e ON e.attempt_id=a.attempt_id
                       JOIN poc_reconciliations r ON r.execution_id=e.execution_id
                       WHERE a.attempt_id=%s""",(fact.attempt_id,)).fetchone()
            self.assertEqual(got,("UNKNOWN","UNKNOWN","PENDING",0))
            print(json.dumps({
                "result":"PASS_OFFICIAL_NATIVE_TCP_ACK_LOSS",
                "backend":"MAF_AzureFunctions_MSSQL",
                "official_instance_observed":True,
                "real_socket_ack_lost":True,
                "native_start_dispatch_count":proxy.post_count,
                "platform_binding_count":got[-1],
                "reconciliation_state":got[2],
            },sort_keys=True))
        finally:
            proxy.shutdown()
            proxy.server_close()
            thread.join(timeout=5)
            # Complete only our randomly created pending native test case,
            # using the DENIED branch (zero simulated sensitive executions).
            if instance:
                try:
                    request_id=official.pending(instance,20)
                    official.invoke("POST",f"{ROUTE}/respond/{instance}/{request_id}","REJECTED")
                    deadline=time.monotonic()+65
                    while time.monotonic()<deadline:
                        status=official.invoke("GET",f"{ROUTE}/status/{instance}")
                        if status.get("runtimeStatus")=="Completed":
                            if status.get("output")!=["DENIED_NO_EXECUTION"]:
                                raise AssertionError("Unexpected native denied output")
                            break
                        time.sleep(1)
                    else:
                        raise TimeoutError("Native cleanup request did not complete")
                except Exception as exc:
                    raise RuntimeError("Official Native fixture cleanup failed; inspect test instance") from exc


if __name__=="__main__":
    unittest.main()
