"""A34 fast native MAF Executor/Tool Adapter replay admission.

The native MSSQL fault experiment previously showed a RUNNING handler enters
twice. Here actual MAF Workflow.run enters the same public Executor twice
with one trusted Harness execution identity. PostgreSQL enforces admission.
This does NOT simulate the MSSQL provider or prove real external side effects.
"""
import os
import sys
import unittest
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from execution_ownership import ExecutionOwnership, Ownership, StaleExecutionOwner
from maf_execution_adapter import GuardedToolRequest, build_guarded_tool_workflow
from recovery_boundary import RecoveryCoordinator
from task_ledger import TaskLedger
from workflow_probe import VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"), "dedicated PostgreSQL required")
class NativeMafGuardedDispatchTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["POC_POSTGRES_DSN"]
        cls.ledger = TaskLedger(cls.dsn)
        cls.ledger.initialize()
        cls.owners = ExecutionOwnership(cls.dsn)

    def create_execution(self):
        fact = VerificationFact.example(passed=False, evidence_ref=None)
        execution = self.ledger.start(fact)
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "UPDATE poc_executions SET side_effect_class='NON_RETRYABLE' "
                "WHERE execution_id=%s", (execution,)
            )
        owner = self.owners.claim(execution, owner_id="MAF-worker-A", ttl_seconds=60)
        return fact, execution, owner

    async def test_native_maf_reentry_does_not_redispatch_tool(self):
        fact, execution, owner = self.create_execution()
        tool_calls = []

        async def external_tool(payload):
            tool_calls.append(payload)
            return "tool-receipt-fixture"

        request = GuardedToolRequest(owner, "simulated-write")
        # Two real MAF Workflow executions = two physical Executor entries.
        first = await build_guarded_tool_workflow(self.owners, external_tool).run(request)
        self.assertEqual(first.get_outputs(), ["tool-receipt-fixture"])
        try:
            await build_guarded_tool_workflow(self.owners, external_tool).run(request)
        except StaleExecutionOwner:
            pass  # MAF may propagate handler failure depending on SDK version.
        self.assertEqual(tool_calls, ["simulated-write"])
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(
                "SELECT dispatched_at IS NOT NULL, fencing_token FROM "
                "poc_execution_ownership WHERE execution_id=%s", (execution,)
            ).fetchone()
        self.assertEqual(row, (True, 1))
        self.assertEqual(len(self.ledger.read(fact.run_id)["attempts"]), 1)

    async def test_native_replay_after_crash_gap_requires_reconciliation(self):
        fact, execution, owner = self.create_execution()
        calls = []

        async def crash_after_admission(payload):
            calls.append(payload)
            raise RuntimeError("simulated downstream result lost after admission")

        request = GuardedToolRequest(owner, "simulated-unsafe-write")
        try:
            await build_guarded_tool_workflow(self.owners, crash_after_admission).run(request)
        except RuntimeError:
            pass
        self.assertEqual(len(calls), 1)
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "UPDATE poc_execution_ownership SET lease_expires_at="
                "now()-interval '1 second' WHERE execution_id=%s", (execution,)
            )
        decision = RecoveryCoordinator(self.dsn).recover(
            fact.run_id, interrupted_attempt_id=fact.attempt_id
        )
        self.assertEqual(decision.outcome, "RECONCILIATION")
        self.assertEqual(self.ledger.read(fact.run_id)["attempts"][0]["state"], "UNKNOWN")
        with self.assertRaises(StaleExecutionOwner):
            self.owners.claim(execution, owner_id="MAF-worker-B")
        try:
            await build_guarded_tool_workflow(self.owners, crash_after_admission).run(request)
        except StaleExecutionOwner:
            pass
        self.assertEqual(len(calls), 1)
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(
                "SELECT state FROM poc_reconciliations WHERE execution_id=%s",
                (execution,)
            ).fetchone()
        self.assertEqual(row[0], "PENDING")

    async def test_wrong_owner_token_never_calls_tool(self):
        _, _, owner = self.create_execution()
        calls = []

        async def side_effect(payload):
            calls.append(payload)
            return "unexpected"

        forged = Ownership(owner.execution_id, "MAF-worker-B", owner.fencing_token)
        try:
            await build_guarded_tool_workflow(self.owners, side_effect).run(
                GuardedToolRequest(forged, "simulated-write")
            )
        except StaleExecutionOwner:
            pass
        self.assertEqual(calls, [])
