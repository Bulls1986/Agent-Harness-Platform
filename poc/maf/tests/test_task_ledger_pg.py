"""Real PostgreSQL A23 integration tests. Must run in CI with POC_POSTGRES_DSN.

These tests do not claim Runtime Checkpoint/Resume or crash recovery.
"""
import asyncio
import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from document_workflow import run_document_case
from task_ledger import TaskFactConflict, TaskLedger
from workflow_probe import PlatformOutcome, VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"), "DB integration runs in dedicated CI step")
class LedgerPostgresTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = TaskLedger(os.environ["POC_POSTGRES_DSN"])
        cls.ledger.initialize()

    async def test_real_workflow_success_atomic_facts_and_new_connection(self):
        fact = VerificationFact.example(passed=False, evidence_ref=None)
        execution_id = self.ledger.start(fact)
        # Native MAF Workflow with independent verifier, not a mocked runner.
        outcome = await run_document_case("expected", fact)
        self.ledger.finish(fact, outcome, execution_id)
        record = TaskLedger(os.environ["POC_POSTGRES_DSN"]).read(fact.run_id)
        self.assertEqual(record["run"]["state"], "COMPLETED")
        self.assertEqual(record["run"]["runtime_type"], "maf")
        self.assertEqual(record["plans"][0]["version"], 1)
        self.assertEqual(record["attempts"][0]["state"], "SUCCEEDED")
        self.assertEqual(record["verifications"][0]["passed"], True)
        self.assertEqual([e["event_type"] for e in record["events"]], ["run.started","run.terminal"])
        self.assertEqual([e["seq"] for e in record["events"]], [1,2])
        with self.assertRaises(TaskFactConflict):
            self.ledger.finish(fact, outcome, execution_id)
        self.assertEqual(self.ledger.read(fact.run_id)["run"]["state"], "COMPLETED")
        with psycopg.connect(os.environ["POC_POSTGRES_DSN"]) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    "UPDATE poc_executions SET state='FAILED' WHERE execution_id=%s",
                    (execution_id,)
                )
        with psycopg.connect(os.environ["POC_POSTGRES_DSN"]) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    "UPDATE poc_runs SET state='RUNNING' WHERE run_id=%s", (fact.run_id,)
                )

    async def test_verification_failure_is_durable_and_not_rewritten(self):
        fact = VerificationFact.example(passed=False, evidence_ref=None)
        execution_id = self.ledger.start(fact)
        outcome = await run_document_case("buggy", fact)
        self.ledger.finish(fact, outcome, execution_id)
        readback = self.ledger.read(fact.run_id)
        self.assertEqual(readback["run"]["state"], "FAILED")
        self.assertEqual(readback["attempts"][0]["failure_type"], "VERIFICATION_FAILURE")
        self.assertEqual(readback["verifications"][0]["passed"], False)
        with psycopg.connect(os.environ["POC_POSTGRES_DSN"]) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    "UPDATE poc_attempts SET state='SUCCEEDED' WHERE attempt_id=%s",
                    (fact.attempt_id,)
                )

    async def test_replan_preserves_v1_and_rejects_stale_result(self):
        fact = VerificationFact.example(passed=False, evidence_ref=None)
        execution_id = self.ledger.start(fact)
        new_id, version = self.ledger.append_plan(
            fact.run_id, reason="verification requires changing approach"
        )
        self.assertEqual(version, 2)
        readback = self.ledger.read(fact.run_id)
        self.assertEqual([p["version"] for p in readback["plans"]], [1,2])
        self.assertEqual(readback["plans"][1]["parent_plan_id"], fact.plan_id)
        self.assertEqual([e["seq"] for e in readback["events"]], [1,2])
        with psycopg.connect(os.environ["POC_POSTGRES_DSN"]) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    "UPDATE poc_plans SET reason='overwrite' WHERE plan_id=%s", (fact.plan_id,)
                )
        outcome = await run_document_case("expected", fact)
        with self.assertRaises(TaskFactConflict):
            self.ledger.finish(fact, outcome, execution_id)
        # Transaction rollback: v1 Attempt is still RUNNING, Run remains RUNNING.
        readback = self.ledger.read(fact.run_id)
        self.assertEqual(readback["run"]["state"], "RUNNING")
        self.assertEqual(readback["attempts"][0]["state"], "RUNNING")

    async def test_identity_mismatch_and_missing_evidence_are_rejected_atomically(self):
        fact = VerificationFact.example(passed=False, evidence_ref=None)
        execution_id = self.ledger.start(fact)
        success = await run_document_case("expected", fact)
        with self.assertRaises(TaskFactConflict):
            self.ledger.finish(fact, replace(success, run_id="run-other"), execution_id)
        with self.assertRaises(TaskFactConflict):
            self.ledger.finish(fact, replace(success, evidence_ref=None), execution_id)
        readback = self.ledger.read(fact.run_id)
        self.assertEqual(readback["run"]["state"], "RUNNING")
        self.assertEqual(readback["verifications"], [])
        self.assertEqual([e["event_type"] for e in readback["events"]], ["run.started"])


if __name__ == "__main__":
    unittest.main()
