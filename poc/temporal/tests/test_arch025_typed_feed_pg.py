"""ARCH-025 G3 unified read-only Typed SSE: projection and actual PG facts.

C11 Artifact in the test is a metadata-only PG fixture (not a true S3
object). The real S3 proof remains C11; this test only verifies SSE bridge.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from platform_typed_feed import PORTABLE_FIELDS, TemporalEventFeed, project_event

try:
    import psycopg
    from fastapi.testclient import TestClient
    from live_g3_api import app
    from live_g3_facts import LiveFacts
    from c11_facts import C11Facts, C11Run
    from platform_facts import FrozenTemporal, TemporalTaskFacts
except ImportError:
    TestClient = None


class ProjectionSafety(unittest.TestCase):
    def row(self, kind, data):
        return {"event_id":"event-1","seq":1,"event_type":kind,
                "payload":data,"created_at":datetime.now(timezone.utc)}

    def metadata(self):
        return {"run_id":"run-safe","turn_id":"turn-safe",
                "conversation_id":"conversation-safe"}

    def test_c15_c11_c16_all_projected_and_provider_secrets_omitted(self):
        sample = {
            "response.output_text.delta":{"delta":"genuine token"},
            "artifact.created":{"artifact_id":"artifact-123","sha256":"a"*64,
                                "storage_ref":"s3://bucket/key"},
            "execution.unknown":{"failure_type":"EXECUTOR_CRASH_AFTER_DISPATCH",
                                 "reconciliation_state":"PENDING"},
            "execution.reconciled":{"status":"APPLIED","receipt_ref":"receipt://ok"},
        }
        for kind,payload in sample.items():
            with self.subTest(kind=kind):
                row=self.row(kind,payload | {
                    "native_workflow_id":"NATIVE-PRIVATE",
                    "authorization":"SECRET", "raw_tool_payload":"PRIVATE"})
                output=project_event(self.metadata(),row)
                raw=json.dumps(output)
                self.assertNotIn("NATIVE-PRIVATE",raw)
                self.assertNotIn("SECRET",raw)
                self.assertNotIn("PRIVATE",raw)
                self.assertEqual(output["schema_version"],"1")
                self.assertEqual(output["type"],kind)
                self.assertTrue(all(k in PORTABLE_FIELDS[kind] for k in output["data"]))
                self.assertEqual(output["id"],"run-safe:1")

    def test_unknown_event_and_invalid_payload_fail_closed(self):
        with self.assertRaises(ValueError):
            project_event(self.metadata(),self.row("provider.internal.dump",{"secret":"value"}))
        with self.assertRaises(ValueError):
            project_event(self.metadata(),self.row("artifact.created","not-an-object"))


@unittest.skipUnless(os.environ.get("POC_C_PLATFORM_DSN") and TestClient,
                     "Real Harness PG, FastAPI and official Temporal SDK required")
class PlatformEventFeedPG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_C_PLATFORM_DSN"]
        cls.c11=C11Facts(cls.dsn)
        cls.c11.initialize()
        cls.c15=LiveFacts(cls.dsn)
        cls.c15.initialize()
        cls.feed=TemporalEventFeed(cls.dsn)
        cls.http=TestClient(app)

    def test_real_pg_artifact_metadata_event_sse_cross_process_contract(self):
        run=C11Run.build("sha256:"+"a"*64)
        req=run.request()
        self.c11.prepare(run)
        stage=req["stages"][0]
        artifact=self.c11.record_artifact(
            req,stage,"b"*64,262160,"s3://poc-c11-artifacts/arch025-pg-fixture")
        # Terminate only this bounded metadata fixture to close SSE. The
        # real C11 workflow+S3 path is proved by verify_c11_real_s3.py.
        with psycopg.connect(self.dsn) as pg:
            pg.execute("UPDATE poc_runs SET state='FAILED',terminal_at=now() WHERE run_id=%s",
                       (run.run_id,))
            C11Facts.event(pg,run.run_id,"run.terminal",{"state":"FAILED"})
        url=f"/v1/runs/{run.run_id}/events"
        full=self.http.get(url)
        self.assertEqual(full.status_code,200,full.text)
        self.assertEqual(full.text.count("event: "),3)
        self.assertIn("event: artifact.created",full.text)
        self.assertIn(artifact,full.text)
        self.assertIn('"sha256":"'+("b"*64)+'"',full.text)
        self.assertNotIn(run.native_workflow_id,full.text)
        self.assertEqual(self.http.get(f"/v1/responses/{run.run_id}/events").status_code,404)
        replay=self.http.get(url,headers={"Last-Event-ID":run.run_id+":1"})
        self.assertEqual(replay.status_code,200,replay.text)
        self.assertEqual(replay.text.count("event: "),2)
        self.assertIn("event: artifact.created",replay.text)
        self.assertEqual(self.http.get(url,headers={"Last-Event-ID":"run-forged:1"}).status_code,422)
        self.assertEqual(self.http.get(url,params={"after":-1}).status_code,422)

    def test_c15_same_token_run_available_from_both_paths(self):
        req=self.c15.prepare("real PG event bridge test","ci-model")
        self.c15.terminal(req,"FAILED")
        a=self.http.get(f"/v1/responses/{req['run']}/events")
        b=self.http.get(f"/v1/runs/{req['run']}/events")
        self.assertEqual((a.status_code,b.status_code),(200,200))
        self.assertEqual(a.text,b.text)
        self.assertIn("event: plan.created",a.text)
        self.assertIn('"conversation_id":"conversation-',a.text)
        self.assertNotIn(req["native_workflow_id"],a.text)

    def test_actual_pg_unknown_fact_not_serialized_as_success(self):
        suffix=uuid4().hex
        binding=FrozenTemporal(
            run_id="run-"+suffix,plan_id="plan-"+suffix,
            step_id="step-"+suffix,attempt_id="attempt-"+suffix,
            execution_id="execution-"+suffix,native_workflow_id="native-"+suffix)
        facts=TemporalTaskFacts(self.dsn)
        facts.prepare(binding)
        owner=facts.owner.claim(binding.execution_id,owner_id="dead-arch025",ttl_seconds=3)
        facts.owner.dispatch(owner)
        with psycopg.connect(self.dsn) as pg:
            pg.execute("UPDATE poc_execution_ownership SET lease_expires_at=now()-interval '1 second' "
                       "WHERE execution_id=%s",(binding.execution_id,))
        self.assertEqual(facts.quarantine_after_dispatch(binding),"RECONCILIATION_PENDING")
        state,records=self.feed.snapshot(binding.run_id)
        self.assertEqual(state["state"],"RUNNING")
        self.assertEqual([e["type"] for e in records],["run.started","execution.unknown"])
        self.assertEqual(records[-1]["data"]["reconciliation_state"],"PENDING")
        self.assertNotIn(binding.native_workflow_id,json.dumps(records))


if __name__=="__main__":
    unittest.main()