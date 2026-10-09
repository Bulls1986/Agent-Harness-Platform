"""C15 G2/G3 PostgreSQL contracts for immutable native Start/RecoveryPoint and cancel."""
from __future__ import annotations
import os
import sys
import unittest
from pathlib import Path
import psycopg
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from live_g3_facts import LiveFacts

@unittest.skipUnless(os.environ.get("POC_C_PLATFORM_DSN"),"Real Harness PG required")
class LiveG3PG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=LiveFacts(os.environ["POC_C_PLATFORM_DSN"])
        cls.store.initialize()

    def fixture(self):
        return self.store.prepare("C15 bounded protocol PG test","poc-model")

    def test_start_unknown_reconcile_same_immutable_workflow_binding(self):
        run=self.fixture()
        ref=self.store.recovery_reference(run["run"])
        self.assertEqual(ref["runtime_checkpoint_ref"],
                         "temporal-workflow-id://"+run["native_workflow_id"])
        self.assertEqual(ref["attempt_id"],run["attempt"])
        self.store.mark_start_uncertain(run["run"])
        state,_=self.store.snapshot(run["run"])
        self.assertEqual(state["start_state"],"START_UNKNOWN")
        self.store.ack(run["run"],run["native_workflow_id"])
        state,_=self.store.snapshot(run["run"])
        self.assertEqual(state["start_state"],"ACKED")
        self.store.mark_start_uncertain(run["run"])
        state,_=self.store.snapshot(run["run"])
        self.assertEqual(state["start_state"],"ACKED")

    def test_frozen_native_recovery_and_model_cannot_be_tampered(self):
        run=self.fixture()
        self.store.require(run)
        for key in ("native_workflow_id","frozen_workflow_version","model","prompt","attempt"):
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.store.require(run|{key:"tamper"})
        with psycopg.connect(self.store.dsn) as db:
            with self.assertRaises(psycopg.Error):
                db.execute("UPDATE poc_c15_runs SET native_workflow_id='forged' WHERE run_id=%s",
                           (run["run"],))
        with psycopg.connect(self.store.dsn) as db:
            with self.assertRaises(psycopg.Error):
                db.execute("UPDATE poc_recovery_points SET runtime_checkpoint_ref='fake' WHERE run_id=%s",
                           (run["run"],))
        with psycopg.connect(self.store.dsn) as db:
            with self.assertRaises(psycopg.Error):
                db.execute("""INSERT INTO poc_recovery_points
                        (recovery_point_id,run_id,step_id,attempt_id,runtime_checkpoint_ref)
                        VALUES('forged',%s,%s,%s,'temporal://forged')""",
                           (run["run"],run["step"],run["attempt"]))

    def test_cancel_intent_is_not_terminal_until_native_termination_confirmed(self):
        run=self.fixture()
        self.assertEqual(self.store.request_cancel(run["run"]),"CANCELLING")
        self.assertEqual(self.store.request_cancel(run["run"]),"CANCELLING")
        self.assertFalse(self.store.append(run,"response.output_text.delta",{"delta":"late"}))
        self.assertEqual(self.store.terminal(run,"COMPLETED"),"CANCELLING")
        self.assertFalse(self.store.verify(run,"f"*64,1))
        state,events=self.store.snapshot(run["run"])
        self.assertEqual(state["state"],"CANCELLING")
        self.assertEqual([e["event_type"] for e in events].count("cancellation.requested"),1)
        self.assertNotIn("run.terminal",[e["event_type"] for e in events])
        # ACK alone must NOT count as termination.
        self.assertTrue(self.store.note_cancel_ack(run["run"]))
        self.assertFalse(self.store.note_cancel_ack(run["run"]))
        self.assertEqual(self.store.snapshot(run["run"])[0]["state"],"CANCELLING")
        for unsafe_status in ("RUNNING","CONTINUED_AS_NEW","UNKNOWN"):
            with self.subTest(native=unsafe_status),self.assertRaises(ValueError):
                self.store.finish_cancel(run["run"],unsafe_status)
        self.assertEqual(self.store.finish_cancel(run["run"],"CANCELED"),"CANCELLED")
        self.assertEqual(self.store.request_cancel(run["run"]),"CANCELLED")
        self.assertEqual(self.store.finish_cancel(run["run"],"CANCELED"),"CANCELLED")
        self.assertEqual(self.store.terminal(run,"COMPLETED"),"CANCELLED")
        state,events=self.store.snapshot(run["run"])
        self.assertEqual(state["state"],"CANCELLED")
        self.assertEqual(events[-1]["event_type"],"run.terminal")
        self.assertEqual([e["seq"] for e in events],list(range(1,len(events)+1)))
        with psycopg.connect(self.store.dsn) as db:
            with self.assertRaises(psycopg.Error):
                db.execute("UPDATE poc_runs SET state='RUNNING' WHERE run_id=%s",
                           (run["run"],))

    def test_failed_native_termination_keeps_truthful_failed_terminal(self):
        run=self.fixture()
        self.assertEqual(self.store.request_cancel(run["run"]),"CANCELLING")
        self.assertEqual(self.store.finish_cancel(run["run"],"TIMED_OUT"),"FAILED")
        state,events=self.store.snapshot(run["run"])
        self.assertEqual(state["state"],"FAILED")
        self.assertEqual(events[-1]["payload"]["state"],"FAILED")
        self.assertFalse(self.store.append(run,"response.output_text.delta",{"delta":"late"}))

    def test_original_pure_execution_success_is_not_rewritten(self):
        from hashlib import sha256
        run=self.fixture()
        text="already verified model text"
        digest=sha256(text.encode()).hexdigest()
        self.store.append(run,"response.output_text.delta",{"delta":text})
        self.store.append(run,"response.output_text.done",
                          {"sha256":digest,"chars":len(text)})
        self.assertTrue(self.store.verify(run,digest,len(text)))
        self.assertEqual(self.store.request_cancel(run["run"]),"CANCELLING")
        self.assertEqual(self.store.finish_cancel(run["run"],"COMPLETED"),"CANCELLED")
        with psycopg.connect(self.store.dsn) as db:
            attempt=db.execute("SELECT state FROM poc_attempts WHERE attempt_id=%s",
                               (run["attempt"],)).fetchone()[0]
            execution=db.execute("SELECT state FROM poc_executions WHERE execution_id=%s",
                                 (run["execution"],)).fetchone()[0]
        self.assertEqual((attempt,execution),("SUCCEEDED","SUCCEEDED"))

    def test_native_unreachable_or_running_cannot_finalize_cancel(self):
        from unittest.mock import AsyncMock, MagicMock, patch
        from types import SimpleNamespace
        from fastapi.testclient import TestClient
        from live_g3_api import app
        run=self.fixture()
        self.assertEqual(self.store.request_cancel(run["run"]),"CANCELLING")
        http=TestClient(app)
        url=f"/v1/responses/{run['run']}/reconcile-cancel"
        with patch("live_g3_api.Client.connect",
                   new=AsyncMock(side_effect=ConnectionError("Native unreachable"))):
            denied=http.post(url)
            self.assertEqual(denied.status_code,409)
        handle=MagicMock()
        native=MagicMock()
        native.get_workflow_handle.return_value=handle
        handle.describe=AsyncMock(return_value=SimpleNamespace(
            id=run["native_workflow_id"],status=SimpleNamespace(name="RUNNING")))
        with patch("live_g3_api.Client.connect",new=AsyncMock(return_value=native)):
            pending=http.post(url)
            self.assertEqual(pending.status_code,202)
            self.assertEqual(pending.json()["native_termination"],"RUNNING")
        handle.describe=AsyncMock(return_value=SimpleNamespace(
            id="tampered-native-id",status=SimpleNamespace(name="CANCELED")))
        with patch("live_g3_api.Client.connect",new=AsyncMock(return_value=native)):
            mismatch=http.post(url)
            self.assertEqual(mismatch.status_code,409)
        state,events=self.store.snapshot(run["run"])
        self.assertEqual(state["state"],"CANCELLING")
        self.assertNotIn("run.terminal",[event["event_type"] for event in events])

    def test_artifact_same_run_frozen_lineage_and_proof_required(self):
        from hashlib import sha256
        run=self.store.prepare("real PG bounded Artifact contract","poc-model",
                               save_artifact=True)
        self.store.require(run)
        with self.assertRaises(ValueError):
            self.store.require(run|{"save_artifact":False})
        text="C15 persisted source"
        digest=sha256(text.encode()).hexdigest()
        self.store.append(run,"response.output_text.delta",{"delta":text})
        self.store.append(run,"response.output_text.done",{"sha256":digest,"chars":len(text)})
        with self.assertRaises(ValueError):
            self.store.verify(run,digest,len(text)) # no actual S3 proof yet
        ref="s3://poc-c11-artifacts/fixture-only-"+run["run"]
        artifact=self.store.record_artifact(run,digest,len(text.encode()),ref)
        self.assertEqual(artifact,self.store.record_artifact(run,digest,len(text.encode()),ref))
        with self.assertRaises(ValueError):
            self.store.record_artifact(run,digest,len(text.encode()),ref+"-different")
        with self.assertRaises(ValueError):
            self.store.mark_artifact_verified(run,artifact,digest,ref+"-forged",len(text))
        self.assertTrue(self.store.mark_artifact_verified(run,artifact,digest,ref,len(text)))
        self.assertTrue(self.store.mark_artifact_verified(run,artifact,digest,ref,len(text)))
        self.assertTrue(self.store.verify(run,digest,len(text)))
        self.assertEqual(self.store.terminal(run,"COMPLETED"),"COMPLETED")
        state,events=self.store.snapshot(run["run"])
        self.assertEqual(state["state"],"COMPLETED")
        self.assertEqual([e["event_type"] for e in events].count("artifact.created"),1)
        self.assertEqual([e["event_type"] for e in events].count("artifact.verified"),1)

    def test_nonpure_s3_artifact_cancel_fails_closed_without_false_terminal(self):
        run=self.store.prepare("bounded cancel artifact guard","poc-model",save_artifact=True)
        with psycopg.connect(self.store.dsn) as db:
            kind=db.execute("SELECT side_effect_class FROM poc_executions "
                            "WHERE execution_id=%s",(run["execution"],)).fetchone()[0]
        self.assertEqual(kind,"IDEMPOTENT")  # S3 PUT is an external effect
        with self.assertRaises(ValueError):
            self.store.request_cancel(run["run"])
        state,events=self.store.snapshot(run["run"])
        self.assertEqual(state["state"],"RUNNING")
        self.assertNotIn("cancellation.requested",[e["event_type"] for e in events])
        self.assertNotIn("run.terminal",[e["event_type"] for e in events])

    def test_s3_after_dispatch_unknown_is_immutable_pending_not_false_failed(self):
        run=self.store.prepare("S3 write ACK missing PG negative","poc-model",
                               save_artifact=True)
        self.assertEqual(self.store.mark_artifact_unknown(run),"PENDING")
        self.assertEqual(self.store.mark_artifact_unknown(run),"PENDING")
        self.assertEqual(self.store.terminal(run,"FAILED"),"RUNNING")
        self.assertFalse(self.store.append(run,"response.output_text.delta",{"delta":"late"}))
        with self.assertRaises(ValueError):
            self.store.request_cancel(run["run"])  # Non-PURE, fail-closed
        state,events=self.store.snapshot(run["run"])
        self.assertEqual(state["state"],"RUNNING")
        self.assertEqual(state["execution_state"],"UNKNOWN")
        self.assertEqual(state["reconciliation_state"],"PENDING")
        kinds=[e["event_type"] for e in events]
        self.assertEqual(kinds.count("execution.unknown"),1)
        self.assertNotIn("run.terminal",kinds)
        with psycopg.connect(self.store.dsn) as pg:
            states=pg.execute("SELECT a.state,e.state FROM poc_attempts a "
                "JOIN poc_executions e ON e.attempt_id=a.attempt_id "
                "WHERE e.execution_id=%s",(run["execution"],)).fetchone()
            self.assertEqual(states,("UNKNOWN","UNKNOWN"))
            with self.assertRaises(psycopg.Error):
                pg.execute("UPDATE poc_executions SET state='RUNNING' "
                           "WHERE execution_id=%s",(run["execution"],))

    def test_token_verification_must_match_actual_persisted_events(self):
        from hashlib import sha256
        run=self.fixture()
        self.store.append(run,"activity.started",{"execution_id":run["execution"]})
        self.store.append(run,"response.output_text.delta",{"delta":"the actual streamed model"})
        raw="the actual streamed model"
        digest=sha256(raw.encode()).hexdigest()
        self.store.append(run,"response.output_text.done",
                          {"sha256":digest,"chars":len(raw)})
        with self.assertRaises(ValueError):
            self.store.verify(run,"f"*64,len(raw))
        self.assertTrue(self.store.verify(run,digest,len(raw)))
        self.assertEqual(self.store.terminal(run,"COMPLETED"),"COMPLETED")
        self.assertEqual(self.store.snapshot(run["run"])[0]["state"],"COMPLETED")

if __name__=="__main__":unittest.main()