"""C10 ASGI + real Harness PostgreSQL fixture cases; no Native API reads."""
from __future__ import annotations

from dataclasses import replace
import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import psycopg
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    from fastapi.testclient import TestClient
    from protocol_bridge import app
except ImportError:
    TestClient=None
    app=None
from platform_facts import FrozenTemporal,TemporalTaskFacts


@unittest.skipUnless(os.environ.get("POC_C_PLATFORM_DSN") and TestClient,
                     "real Harness PG + protocol dependencies required")
class TemporalProtocolBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=TemporalTaskFacts(os.environ["POC_C_PLATFORM_DSN"])
        cls.store.initialize()
        cls.http=TestClient(app)

    def fixture(self,*,unknown=False):
        suffix=uuid4().hex
        b=FrozenTemporal(
            run_id="run-"+suffix,plan_id="plan-"+suffix,
            step_id="step-"+suffix,attempt_id="attempt-"+suffix,
            execution_id="execution-"+suffix,native_workflow_id="temporal-"+suffix)
        self.store.prepare(b)
        if unknown:
            owner=self.store.owner.claim(b.execution_id,owner_id="dead-fixture",ttl_seconds=3)
            self.store.owner.dispatch(owner)
            with psycopg.connect(self.store.dsn) as pg:
                pg.execute("UPDATE poc_execution_ownership "
                           "SET lease_expires_at=now()-interval '1 second' "
                           "WHERE execution_id=%s",(b.execution_id,))
            self.assertEqual(self.store.quarantine_after_dispatch(b),
                             "RECONCILIATION_PENDING")
        return b

    def test_running_snapshot_does_not_leak_native_workflow_id(self):
        b=self.fixture()
        res=self.http.get("/v1/responses/"+b.run_id)
        self.assertEqual(res.status_code,200,res.text)
        d=res.json()
        self.assertEqual(d["status"],"in_progress")
        self.assertEqual(d["output"],[])
        self.assertFalse(d["harness"]["attention_required"])
        self.assertEqual(d["harness"]["event_cursor"],1)
        self.assertNotIn("native_workflow_id",res.text)
        self.assertNotIn(b.native_workflow_id,res.text)
        stream=self.http.get(f"/v1/runs/{b.run_id}/events")
        self.assertEqual(stream.text.count("event: "),1)
        self.assertIn('"schema_version":"1"',stream.text)
        self.assertIn('"conversation_id":"conversation-',stream.text)
        self.assertNotIn(b.native_workflow_id,stream.text)

    def test_unknown_snapshots_and_last_event_id_reconnect_after_new_asgi_client(self):
        b=self.fixture(unknown=True)
        res=self.http.get("/v1/responses/"+b.run_id)
        self.assertEqual(res.status_code,200,res.text)
        d=res.json()
        self.assertEqual(d["status"],"in_progress") # NOT falsely completed
        self.assertEqual(d["harness"]["execution_outcome"],"UNKNOWN")
        self.assertEqual(d["harness"]["reconciliation_status"],"PENDING")
        self.assertTrue(d["harness"]["attention_required"])
        self.assertEqual(d["harness"]["event_cursor"],2)
        self.assertNotIn(b.native_workflow_id,res.text)
        first=self.http.get(f"/v1/runs/{b.run_id}/events")
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.text.count("event: "),2)
        self.assertIn("event: execution.unknown",first.text)
        self.assertNotIn(b.native_workflow_id,first.text)
        # No per-process history/cache. Another client gets the same database.
        reconnect=TestClient(app).get(f"/v1/runs/{b.run_id}/events",
                                      headers={"Last-Event-ID":b.run_id+":1"})
        self.assertEqual(reconnect.status_code,200)
        self.assertEqual(reconnect.text.count("event: "),1)
        self.assertIn("event: execution.unknown",reconnect.text)
        self.assertIn("id: "+b.run_id+":2",reconnect.text)
        self.assertEqual(reconnect.headers["x-harness-event-cursor"],"2")
        self.assertEqual(self.http.get(f"/v1/runs/{b.run_id}/events?after=2").text,"")

    def test_fail_closed_invalid_cursor_cross_run_and_unsupported_ops(self):
        a,b=self.fixture(),self.fixture()
        url=f"/v1/runs/{a.run_id}/events"
        for kwargs in (
            {"headers":{"Last-Event-ID":b.run_id+":1"}},
            {"headers":{"Last-Event-ID":a.run_id+":oops"}},
            {"headers":{"Last-Event-ID":a.run_id+":1"},"params":{"after":0}},
            {"params":{"after":-1}},
        ):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self.http.get(url,**kwargs).status_code,422)
        self.assertEqual(self.http.get("/v1/responses/missing").status_code,404)
        self.assertEqual(self.http.post("/v1/responses",json={"input":"hello"}).status_code,501)

    def test_terminal_mismatch_never_claims_completed(self):
        b=self.fixture(unknown=True)
        with psycopg.connect(self.store.dsn) as pg:
            pg.execute("UPDATE poc_runs SET state='COMPLETED',terminal_at=now() "
                       "WHERE run_id=%s",(b.run_id,))
        self.assertEqual(self.http.get("/v1/responses/"+b.run_id).status_code,503)
