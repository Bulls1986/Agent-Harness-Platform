"""A24/A27/A28 bounded PostgreSQL integration tests.

No model calls, no durable MAF checkpoint, no self-built lease scheduler.
Runs in dedicated CI step with an actual PostgreSQL instance.
"""
import os
import sys
import unittest
from pathlib import Path

import psycopg
from agent_framework.openai import OpenAIChatClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from document_workflow import run_document_case
from harness_capabilities import build_harness
from native_session_store import NativeSessionStore, SessionConflict
from recovery_boundary import RecoveryCoordinator
from task_ledger import TaskFactConflict, TaskLedger
from workflow_probe import VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"), "requires dedicated PostgreSQL CI")
class NativeSessionRecoveryTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["POC_POSTGRES_DSN"]
        cls.ledger = TaskLedger(cls.dsn)
        cls.ledger.initialize()
        cls.sessions = NativeSessionStore(cls.dsn)
        cls.sessions.initialize()
        cls.recovery = RecoveryCoordinator(cls.dsn)
        cls.previous_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "ci-only-never-sent"

    @classmethod
    def tearDownClass(cls):
        if cls.previous_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = cls.previous_key

    async def test_native_session_json_roundtrip_bound_to_run_and_cas(self):
        fact = VerificationFact.example(passed=False, evidence_ref=None)
        self.ledger.start(fact)
        native = build_harness(OpenAIChatClient(model="ci-fake")).create_session()
        native.state["poc_marker"] = {"turn": 1, "source": "actual-native-AgentSession"}
        revision = self.sessions.save(fact.run_id,native,fingerprint="provider-a")
        self.assertEqual(revision,1)
        restored, version = NativeSessionStore(self.dsn).load(
            fact.run_id,fingerprint="provider-a"
        )
        self.assertEqual(version,1)
        self.assertEqual(restored.state["poc_marker"],native.state["poc_marker"])
        restored.state["poc_marker"]["turn"] = 2
        self.assertEqual(self.sessions.save(
            fact.run_id,restored,fingerprint="provider-a",expected_revision=1
        ),2)
        with self.assertRaises(SessionConflict):
            self.sessions.save(fact.run_id,native,fingerprint="provider-a",expected_revision=1)
        with self.assertRaises(SessionConflict):
            self.sessions.load(fact.run_id,fingerprint="different-model")
        with self.assertRaises(SessionConflict):
            self.sessions.save(fact.run_id,native,fingerprint="different-model",expected_revision=2)
        with self.assertRaises(KeyError):
            self.sessions.load("run-nonexistent",fingerprint="provider-a")

    async def test_pure_interruption_step_boundary_new_attempt_and_stale_guard(self):
        fact = VerificationFact.example(passed=False,evidence_ref=None)
        original_execution = self.ledger.start(fact)
        result = self.recovery.recover(fact.run_id,interrupted_attempt_id=fact.attempt_id)
        self.assertEqual(result.outcome,"STEP_BOUNDARY_RETRY")
        self.assertEqual(result.fact.run_id,fact.run_id)
        self.assertEqual(result.fact.step_id,fact.step_id)
        self.assertNotEqual(result.fact.attempt_id,fact.attempt_id)
        self.assertEqual(self.recovery.recover(
            fact.run_id,interrupted_attempt_id=fact.attempt_id
        ).outcome,"ATTEMPT_ALREADY_HANDLED")
        stale = await run_document_case("expected",fact)
        with self.assertRaises(TaskFactConflict):
            self.ledger.finish(fact,stale,original_execution)
        valid = await run_document_case("expected",result.fact)
        self.ledger.finish(result.fact,valid,result.execution_id)
        read = TaskLedger(self.dsn).read(fact.run_id)
        self.assertEqual(read["run"]["state"],"COMPLETED")
        self.assertEqual([x["state"] for x in read["attempts"]],["FAILED","SUCCEEDED"])
        self.assertEqual(read["attempts"][0]["failure_type"],"EXECUTOR_CRASH")
        self.assertEqual(
            [e["event_type"] for e in read["events"]],
            ["run.started","attempt.restarted","run.terminal"]
        )
        self.assertEqual([e["seq"] for e in read["events"]],[1,2,3])

    async def test_non_pure_interruption_enters_reconciliation_not_retry(self):
        fact = VerificationFact.example(passed=False,evidence_ref=None)
        execution_id = self.ledger.start(fact)
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "UPDATE poc_executions SET side_effect_class='NON_RETRYABLE' WHERE execution_id=%s",
                (execution_id,),
            )
        decision=self.recovery.recover(fact.run_id,interrupted_attempt_id=fact.attempt_id)
        self.assertEqual(decision.outcome,"RECONCILIATION")
        read=self.ledger.read(fact.run_id)
        self.assertEqual(read["run"]["state"],"RUNNING")
        self.assertEqual(len(read["attempts"]),1)
        self.assertEqual(read["attempts"][0]["state"],"UNKNOWN")
        self.assertEqual(read["events"][-1]["event_type"],"execution.unknown")
        with psycopg.connect(self.dsn) as conn:
            row=conn.execute(
                "SELECT state FROM poc_reconciliations WHERE execution_id=%s",
                (execution_id,),
            ).fetchone()
            self.assertEqual(row[0],"PENDING")
        again=self.recovery.recover(fact.run_id,interrupted_attempt_id=fact.attempt_id)
        self.assertEqual(again.outcome,"NO_UNIQUE_ACTIVE_EXECUTION")
        self.assertEqual(len(self.ledger.read(fact.run_id)["attempts"]),1)
        stale=await run_document_case("expected",fact)
        with self.assertRaises(TaskFactConflict):
            self.ledger.finish(fact,stale,execution_id)


if __name__ == "__main__":
    unittest.main()
