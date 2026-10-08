"""G6: real HTTP non-idempotent SQLite sink receipt -> PostgreSQL reconciliation.

This is an isolated local external tool, NOT enterprise MCP or a production
receipt provider. It intentionally has no idempotency/deduplication: a repeated
POST causes a second actual external database mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import replace
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recovery_boundary import RecoveryCoordinator
from task_ledger import TaskFactConflict, TaskLedger
from tool_receipt_reconciliation import (
    ExternalToolReceipt, ToolDispatchIntent, ToolReceiptReconciler,
)
from workflow_probe import VerificationFact


class NonIdempotentSink(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        if self.path != "/effects":
            self.send_error(404)
            return
        obj = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        receipt_id = uuid4().hex
        op = obj["operation_id"]
        payload = obj["payload"]
        digest = hashlib.sha256(payload.encode()).hexdigest()
        with closing(sqlite3.connect(self.server.sqlite_path)) as conn:
            conn.execute(
                """INSERT INTO external_effects(receipt_id,operation_id,result_sha256)
                   VALUES (?,?,?)""", (receipt_id,op,digest),
            )
            conn.commit()
        self._json(201, {
            "operation_id": op, "external_receipt_id": receipt_id,
            "result_sha256": digest, "result_kind": "COMMITTED",
        })

    def do_GET(self):
        if not self.path.startswith("/receipts/"):
            self.send_error(404)
            return
        op = self.path[len("/receipts/"):]
        with closing(sqlite3.connect(self.server.sqlite_path)) as conn:
            items = conn.execute(
                """SELECT receipt_id,result_sha256 FROM external_effects
                   WHERE operation_id=? ORDER BY rowid""", (op,),
            ).fetchall()
        if len(items) != 1:
            self._json(404 if not items else 409, {"state": "NOT_UNAMBIGUOUS"})
            return
        self._json(200, {"operation_id": op,
                         "external_receipt_id": items[0][0],
                         "result_sha256": items[0][1],
                         "result_kind": "COMMITTED"})

    def _json(self, code, value):
        raw = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class ExternalSink:
    def __init__(self, db):
        self.db = db
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("""CREATE TABLE external_effects(
                receipt_id text PRIMARY KEY, operation_id text NOT NULL,
                result_sha256 text NOT NULL)""")
            conn.commit()
        self.server = None
        self.thread = None

    def start(self):
        self.server = ThreadingHTTPServer(("127.0.0.1",0),NonIdempotentSink)
        self.server.sqlite_path = self.db
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=5)
            self.server = None

    def post(self, op, payload):
        req = urllib.request.Request(self.base + "/effects",
                                     data=json.dumps({"operation_id":op,"payload":payload}).encode(),
                                     headers={"Content-Type":"application/json"},
                                     method="POST")
        with urllib.request.urlopen(req,timeout=10) as response:
            return json.load(response)

    def read(self, op):
        try:
            with urllib.request.urlopen(self.base + "/receipts/" + op,timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise

    def count(self, op):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM external_effects WHERE operation_id=?", (op,),
            ).fetchone()[0]


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"), "real PostgreSQL required")
class ToolReceiptPGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["POC_POSTGRES_DSN"]
        cls.ledger = TaskLedger(cls.dsn)
        cls.ledger.initialize()
        cls.recovery = RecoveryCoordinator(cls.dsn)
        cls.receipts = ToolReceiptReconciler(cls.dsn)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="g6-external-tool-")
        self.sink = ExternalSink(str(Path(self.temp.name) / "external-effects.sqlite"))
        self.sink.start()

    def tearDown(self):
        self.sink.stop()
        self.temp.cleanup()

    def fixture(self):
        fact = VerificationFact.example(passed=False,evidence_ref=None)
        execution_id = self.ledger.start(fact)
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """UPDATE poc_executions SET side_effect_class='NON_RETRYABLE'
                   WHERE execution_id=%s""", (execution_id,),
            )
        op = "tool-op-" + uuid4().hex
        intent = ToolDispatchIntent(
            run_id=fact.run_id,attempt_id=fact.attempt_id,
            execution_id=execution_id,adapter_id="local-test-http-sink",
            operation_id=op,request_sha256=hashlib.sha256(b"irreversible-write").hexdigest(),
        )
        return fact,intent

    def evidence(self,intent,payload):
        return ExternalToolReceipt(
            execution_id=intent.execution_id,
            adapter_id=intent.adapter_id,
            operation_id=payload["operation_id"],
            external_receipt_id=payload["external_receipt_id"],
            result_sha256=payload["result_sha256"],
            result_kind=payload["result_kind"],
        )

    def test_http_side_effect_committed_then_worker_loses_ack_reconciles_without_post(self):
        fact,intent=self.fixture()
        self.receipts.prepare(intent)
        with self.assertRaises(TaskFactConflict):
            self.receipts.prepare(intent)  # no second dispatch admission
        # Actual HTTP POST commits one SQLite transaction, not a mocked callback.
        posted=self.sink.post(intent.operation_id,"irreversible-write")
        self.assertEqual(self.sink.count(intent.operation_id),1)
        # Original dispatcher is now gone; receipt is reconstructed from
        # restarted external Tool service's independent SQLite database.
        self.sink.stop()
        self.sink.start()
        self.assertEqual(self.recovery.recover(
            fact.run_id,interrupted_attempt_id=fact.attempt_id).outcome,"RECONCILIATION")
        self.assertEqual(self.receipts.inspect(intent.execution_id),
                         "UNKNOWN_NEEDS_EXTERNAL_RECEIPT")
        fetched=self.sink.read(intent.operation_id)
        self.assertEqual(fetched,posted)
        receipt=self.evidence(intent,fetched)
        self.assertEqual(
            self.receipts.observe(fact.run_id,receipt,execution_id=intent.execution_id),
            "RECEIPT_CONFIRMED_NO_REDISPATCH")
        self.assertEqual(
            self.receipts.observe(fact.run_id,receipt,execution_id=intent.execution_id),
            "ALREADY_RECONCILED")
        self.assertEqual(self.receipts.inspect(intent.execution_id),"RECEIPT_RECORDED")
        self.assertEqual(self.sink.count(intent.operation_id),1)
        task=self.ledger.read(fact.run_id)
        self.assertEqual(task["attempts"][0]["state"],"UNKNOWN")
        self.assertEqual(len(task["attempts"]),1)
        self.assertEqual(task["run"]["state"],"RUNNING")
        self.assertEqual(task["events"][-1]["event_type"],"execution.receipt.confirmed")
        with psycopg.connect(self.dsn) as conn:
            row=conn.execute(
                """SELECT rc.state,sr.external_receipt_id,sr.result_sha256
                   FROM poc_reconciliations rc JOIN poc_side_effect_receipts sr
                   ON sr.execution_id=rc.execution_id
                   WHERE rc.execution_id=%s""", (intent.execution_id,),
            ).fetchone()
        self.assertEqual(row,("RESOLVED",receipt.external_receipt_id,receipt.result_sha256))
        # PG receipt is immutable; no accounting rewrite allowed.
        with psycopg.connect(self.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute("DELETE FROM poc_side_effect_receipts WHERE execution_id=%s",
                             (intent.execution_id,))

    def test_no_external_receipt_is_not_permission_to_replay(self):
        fact,intent=self.fixture()
        self.receipts.prepare(intent)
        self.assertIsNone(self.sink.read(intent.operation_id))
        self.recovery.recover(fact.run_id,interrupted_attempt_id=fact.attempt_id)
        self.assertEqual(
            self.receipts.observe(fact.run_id,None,execution_id=intent.execution_id),
            "RECEIPT_NOT_FOUND_REMAINS_UNKNOWN")
        self.assertEqual(self.receipts.inspect(intent.execution_id),
                         "UNKNOWN_NEEDS_EXTERNAL_RECEIPT")
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT state FROM poc_reconciliations WHERE execution_id=%s",
                (intent.execution_id,)).fetchone()[0], "PENDING")
        self.assertEqual(self.sink.count(intent.operation_id),0)

    def test_mismatch_or_premature_receipt_cannot_resolve(self):
        fact,intent=self.fixture()
        self.receipts.prepare(intent)
        payload=self.sink.post(intent.operation_id,"irreversible-write")
        receipt=self.evidence(intent,payload)
        with self.assertRaises(TaskFactConflict):
            self.receipts.observe(fact.run_id,receipt,execution_id=intent.execution_id)
        self.recovery.recover(fact.run_id,interrupted_attempt_id=fact.attempt_id)
        for fake in (
            replace(receipt,adapter_id="forged"),
            replace(receipt,operation_id="different"),
            replace(receipt,execution_id="different"),
            replace(receipt,result_kind="REJECTED"),
        ):
            with self.subTest(fake=fake):
                with self.assertRaises(TaskFactConflict):
                    self.receipts.observe(fact.run_id,fake,execution_id=intent.execution_id)
        self.receipts.observe(fact.run_id,receipt,execution_id=intent.execution_id)
        with self.assertRaises(TaskFactConflict):
            self.receipts.observe(
                fact.run_id,replace(receipt,result_sha256="f"*64),
                execution_id=intent.execution_id)
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM poc_side_effect_receipts WHERE execution_id=%s",
                (intent.execution_id,)).fetchone()[0],1)


    def test_concurrent_reconcile_has_only_one_persisted_receipt_and_event(self):
        from concurrent.futures import ThreadPoolExecutor

        fact,intent=self.fixture()
        self.receipts.prepare(intent)
        payload=self.sink.post(intent.operation_id,"irreversible-write")
        self.recovery.recover(fact.run_id,interrupted_attempt_id=fact.attempt_id)
        receipt=self.evidence(intent,payload)
        def reconcile(_):
            return ToolReceiptReconciler(self.dsn).observe(
                fact.run_id,receipt,execution_id=intent.execution_id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(reconcile,range(2)))
        self.assertCountEqual(results,[
            "RECEIPT_CONFIRMED_NO_REDISPATCH","ALREADY_RECONCILED"])
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM poc_side_effect_receipts WHERE execution_id=%s",
                (intent.execution_id,)).fetchone()[0],1)
            self.assertEqual(conn.execute(
                """SELECT COUNT(*) FROM poc_events
                   WHERE run_id=%s AND event_type='execution.receipt.confirmed'""",
                (fact.run_id,)).fetchone()[0],1)
        self.assertEqual(self.sink.count(intent.operation_id),1)

    def test_ambiguous_external_duplicate_write_remains_pending(self):
        fact,intent=self.fixture()
        self.receipts.prepare(intent)
        self.sink.post(intent.operation_id,"irreversible-write")
        self.sink.post(intent.operation_id,"irreversible-write")
        self.assertEqual(self.sink.count(intent.operation_id),2)
        self.recovery.recover(fact.run_id,interrupted_attempt_id=fact.attempt_id)
        # Trusted adapter refuses to convert HTTP 409 duplicate records into
        # a single fabricated authoritative receipt.
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.sink.read(intent.operation_id)
        self.assertEqual(err.exception.code,409)
        self.assertEqual(
            self.receipts.observe(fact.run_id,None,execution_id=intent.execution_id),
            "RECEIPT_NOT_FOUND_REMAINS_UNKNOWN")
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT state FROM poc_reconciliations WHERE execution_id=%s",
                (intent.execution_id,)).fetchone()[0],"PENDING")

if __name__=="__main__":
    unittest.main()
