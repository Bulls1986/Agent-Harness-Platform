"""G2/G6 actual socket ACK loss with a controlled, non-MAF native HTTP stub.

Official MAF Functions MSSQL /run is tested separately in A34; this test
injects a genuine socket drop *after* an external SQLite start commit,
and exercises the actual Harness PG NativeStartAckCoordinator (no test SQL).
"""
from __future__ import annotations

import json
import os
import socket
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.request
from contextlib import closing
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import psycopg

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from durable_approval_binding import DurableBindingMismatch
from durable_launch_intent import DurableLaunchIntentStore,NativeLaunchIntent
from native_start_ack import NativeStartAckCoordinator
from task_ledger import TaskLedger
from workflow_probe import VerificationFact


class NativeStartStub(BaseHTTPRequestHandler):
    def log_message(self,*_args):pass

    def do_POST(self):
        if self.path!="/run":
            self.send_error(404)
            return
        instance_id=uuid4().hex
        with closing(sqlite3.connect(self.server.sqlite_path)) as conn:
            conn.execute("INSERT INTO native_instances(instance_id) VALUES (?)",
                         (instance_id,))
            conn.commit()
        if self.server.drop_next_ack:
            self.connection.shutdown(socket.SHUT_RDWR)
            self.close_connection=True
            return
        payload=json.dumps({"instanceId":instance_id}).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class NativeServer:
    def __init__(self,sqlite_path):
        self.sqlite_path=sqlite_path
        with closing(sqlite3.connect(sqlite_path)) as conn:
            conn.execute("CREATE TABLE native_instances(instance_id text PRIMARY KEY)")
            conn.commit()
        self.server=None

    def start(self,drop_next_ack):
        self.server=ThreadingHTTPServer(("127.0.0.1",0),NativeStartStub)
        self.server.sqlite_path=self.sqlite_path
        self.server.drop_next_ack=drop_next_ack
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f"http://127.0.0.1:{self.server.server_port}/run"

    def count(self):
        with closing(sqlite3.connect(self.sqlite_path)) as conn:
            return conn.execute("SELECT COUNT(*) FROM native_instances").fetchone()[0]

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=4)
            self.server=None

    def post_once(self):
        with urllib.request.urlopen(urllib.request.Request(
            self.url,data=b"{}",method="POST",headers={"Content-Type":"application/json"}),
            timeout=8) as result:
            return json.load(result)["instanceId"]


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"),"real PostgreSQL required")
class NativeAckGapPGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_POSTGRES_DSN"]
        cls.ledger=TaskLedger(cls.dsn)
        cls.ledger.initialize()
        cls.coordinator=NativeStartAckCoordinator(cls.dsn)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="native-ack-")
        self.native=NativeServer(str(Path(self.temp.name)/"native.sqlite"))

    def tearDown(self):
        self.native.stop()
        self.temp.cleanup()

    def fixture(self):
        fact=VerificationFact.example(passed=False,evidence_ref=None)
        eid=self.ledger.start(fact)
        intent=NativeLaunchIntent(
            run_id=fact.run_id,step_id=fact.step_id,
            attempt_id=fact.attempt_id,execution_id=eid,
            native_workflow_name="maf_mssql_poc_hitl",
            frozen_workflow_version="fixture-v1",
            frozen_runtime_version="maf-sdk-v1")
        return fact,intent

    def test_socket_ack_dropped_after_native_commit_no_repost(self):
        fact,intent=self.fixture()
        self.native.start(drop_next_ack=True)
        outcome=self.coordinator.start_once(intent,native_start=self.native.post_once)
        self.assertEqual(outcome.state,"UNKNOWN_RECONCILIATION_PENDING")
        self.assertEqual(self.native.count(),1)  # actual external commit
        self.native.stop()
        self.native.start(drop_next_ack=False)
        self.assertEqual(self.native.count(),1)  # survived external server restart
        self.assertEqual(DurableLaunchIntentStore(self.dsn).inspect(intent).state,
                         "RECONCILIATION_PENDING")
        with self.assertRaises(DurableBindingMismatch):
            self.coordinator.start_once(intent,native_start=self.native.post_once)
        self.assertEqual(self.native.count(),1)  # prepare rejects before POST
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                """SELECT a.state,e.state,rc.state
                   FROM poc_attempts a JOIN poc_executions e
                   ON e.attempt_id=a.attempt_id
                   JOIN poc_reconciliations rc ON rc.execution_id=e.execution_id
                   WHERE a.attempt_id=%s""",(fact.attempt_id,)).fetchone(),
                ("UNKNOWN","UNKNOWN","PENDING"))

    def test_normal_ack_binds_single_native_instance(self):
        fact,intent=self.fixture()
        self.native.start(drop_next_ack=False)
        outcome=self.coordinator.start_once(intent,native_start=self.native.post_once)
        self.assertEqual(outcome.state,"BOUND")
        self.assertEqual(self.native.count(),1)
        self.assertEqual(len(outcome.native_instance_id),32)
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                """SELECT native_instance_id FROM poc_maf_durable_running_bindings
                   WHERE execution_id=%s""",(intent.execution_id,)).fetchone()[0],
                             outcome.native_instance_id)
        with self.assertRaises(DurableBindingMismatch):
            self.coordinator.start_once(intent,native_start=self.native.post_once)
        self.assertEqual(self.native.count(),1)

    def test_unusable_ack_quarantines_without_new_attempt(self):
        fact,intent=self.fixture()
        outcome=self.coordinator.start_once(intent,native_start=lambda:"not-an-instance")
        self.assertEqual(outcome.state,"UNKNOWN_RECONCILIATION_PENDING")
        task=self.ledger.read(fact.run_id)
        self.assertEqual(len(task["attempts"]),1)
        self.assertEqual(task["attempts"][0]["state"],"UNKNOWN")


if __name__=="__main__":
    unittest.main()
