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

    def test_cancel_immutable_terminal_and_cannot_emit_late_tokens(self):
        run=self.fixture()
        self.assertEqual(self.store.cancel(run["run"]),"CANCELLED")
        self.assertEqual(self.store.cancel(run["run"]),"CANCELLED")
        self.assertFalse(self.store.append(run,"response.output_text.delta",{"delta":"late"}))
        self.assertEqual(self.store.terminal(run,"COMPLETED"),"CANCELLED")
        state,events=self.store.snapshot(run["run"])
        self.assertEqual(state["state"],"CANCELLED")
        self.assertEqual(events[-1]["event_type"],"run.terminal")
        self.assertEqual([e["seq"] for e in events],list(range(1,len(events)+1)))
        with psycopg.connect(self.store.dsn) as db:
            with self.assertRaises(psycopg.Error):
                db.execute("UPDATE poc_runs SET state='RUNNING' WHERE run_id=%s",
                           (run["run"],))

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
