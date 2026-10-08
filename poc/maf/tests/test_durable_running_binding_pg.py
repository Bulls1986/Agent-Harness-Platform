"""A34 RUNNING native-identity binding guards against real PostgreSQL facts.

Native identity comes from a trusted provider Adapter, not from the model.
No claim of checkpoint resume, cross-DB atomicity, or native Worker upgrade.
"""
import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from durable_approval_binding import DurableBindingMismatch
from durable_running_binding import DurableRunningBindingStore, RunningNativeBinding
from task_ledger import TaskLedger
from workflow_probe import VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"), "dedicated real PostgreSQL")
class DurableRunningBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["POC_POSTGRES_DSN"]
        cls.ledger = TaskLedger(cls.dsn)
        cls.ledger.initialize()
        cls.bindings = DurableRunningBindingStore(cls.dsn)

    def fixture(self):
        fact = VerificationFact.example(passed=False, evidence_ref=None)
        execution_id = self.ledger.start(fact)
        binding = RunningNativeBinding(
            run_id=fact.run_id, step_id=fact.step_id,
            attempt_id=fact.attempt_id, execution_id=execution_id,
            native_instance_id="native-running-" + uuid4().hex,
            native_workflow_name="maf_mssql_poc_running",
            frozen_workflow_version="running-fixture:v1",
            frozen_runtime_version="agent-framework-azurefunctions==1.0.0b260922",
        )
        return fact, binding

    def test_new_connection_preserves_all_ids_and_immutable_version(self):
        fact, binding = self.fixture()
        self.bindings.bind(binding)
        self.assertEqual(self.bindings.require_running(binding)["attempt_id"], fact.attempt_id)
        self.assertEqual(self.bindings.require_running(binding)["native_instance_id"],
                         binding.native_instance_id)
        with psycopg.connect(self.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    "UPDATE poc_maf_durable_running_bindings "
                    "SET frozen_runtime_version='untrusted-new' WHERE execution_id=%s",
                    (binding.execution_id,),
                )
        self.assertEqual(self.bindings.require_running(binding)["frozen_runtime_version"],
                         binding.frozen_runtime_version)

    def test_all_frozen_ids_and_versions_fail_closed(self):
        _, b = self.fixture()
        self.bindings.bind(b)
        for field in ("run_id", "step_id", "attempt_id", "execution_id",
                      "native_instance_id", "native_workflow_name",
                      "frozen_workflow_version", "frozen_runtime_version"):
            with self.subTest(field=field):
                with self.assertRaises(DurableBindingMismatch):
                    self.bindings.require_running(replace(b, **{field: "incorrect"}))
        with self.assertRaises(ValueError):
            self.bindings.require_running(replace(b, native_workflow_name=""))

    def test_native_instance_cannot_alias_another_execution(self):
        _, original = self.fixture()
        _, another = self.fixture()
        self.bindings.bind(original)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.bindings.bind(replace(another, native_instance_id=original.native_instance_id))
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM poc_maf_durable_running_bindings "
                "WHERE execution_id=%s", (another.execution_id,)
            ).fetchone()[0], 0)

    def test_direct_sql_cannot_cross_bind_valid_unrelated_run_and_attempt(self):
        _, left = self.fixture()
        _, right = self.fixture()
        with psycopg.connect(self.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    """INSERT INTO poc_maf_durable_running_bindings
                       (execution_id,run_id,step_id,attempt_id,native_instance_id,
                        native_workflow_name,frozen_workflow_version,frozen_runtime_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (left.execution_id, left.run_id, right.step_id, right.attempt_id,
                     left.native_instance_id, left.native_workflow_name,
                     left.frozen_workflow_version, left.frozen_runtime_version),
                )
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM poc_maf_durable_running_bindings "
                "WHERE execution_id=%s", (left.execution_id,)
            ).fetchone()[0], 0)

    def test_inactive_attempt_or_superceded_plan_refuses_resume(self):
        fact, b = self.fixture()
        self.bindings.bind(b)
        with psycopg.connect(self.dsn) as conn:
            conn.execute("UPDATE poc_executions SET state='UNKNOWN' WHERE execution_id=%s",
                         (b.execution_id,))
        with self.assertRaises(DurableBindingMismatch):
            self.bindings.require_running(b)

        fact2, b2 = self.fixture()
        self.bindings.bind(b2)
        self.ledger.append_plan(fact2.run_id, reason="new plan version")
        with self.assertRaises(DurableBindingMismatch):
            self.bindings.require_running(b2)

    def test_attempt_guard_is_not_a_tool_dispatch_admission(self):
        _, b = self.fixture()
        self.bindings.bind(b)
        # Binding does not claim an Execution owner or invoke a Tool Adapter.
        self.bindings.require_running(b)
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM poc_execution_ownership WHERE execution_id=%s",
                (b.execution_id,),
            ).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
