"""Real PostgreSQL A34 immutable native Durable Functions mapping tests."""
import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from approval_wait import ApprovalWaitStore
from durable_approval_binding import DurableApprovalBindingStore, DurableBindingMismatch
from task_ledger import TaskLedger
from workflow_probe import VerificationFact

@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"), "requires dedicated PostgreSQL")
class DurableApprovalBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["POC_POSTGRES_DSN"]
        TaskLedger(cls.dsn).initialize()

    def setUp(self):
        self.approvals = ApprovalWaitStore(self.dsn)
        self.bindings = DurableApprovalBindingStore(self.dsn)
        key = uuid4().hex
        self.native = {
            "durable_instance_id": "instance-" + key,
            "durable_request_id": "request-" + key,
            "durable_workflow_name": "maf_mssql_poc_hitl",
            "frozen_workflow_version": "fixture-v1",
            "frozen_runtime_version": "agent-framework-azurefunctions==1.0.0b260922",
        }

    def request(self, **overrides):
        fact = VerificationFact.example(passed=False, evidence_ref=None)
        fields = {**self.native, **overrides}
        approval = self.approvals.request(
            fact, requester_principal="poc-requester",
            approver_principal="poc-approver", action_ref="tool:poc",
            resource_ref="resource:poc", policy_ref="policy:poc",
            **fields,
        )
        return fact, approval

    def resume(self, fact, **overrides):
        fields = dict(
            attempt_id=fact.attempt_id,
            native_instance_id=self.native["durable_instance_id"],
            native_request_id=self.native["durable_request_id"],
            workflow_name=self.native["durable_workflow_name"],
            workflow_version=self.native["frozen_workflow_version"],
            runtime_version=self.native["frozen_runtime_version"],
        )
        fields.update(overrides)
        return DurableApprovalBindingStore(self.dsn).require_waiting_resume(
            fact.run_id, **fields,
        )

    def test_atomically_persisted_and_cross_connection_same_attempt(self):
        fact, approval = self.request()
        row = self.resume(fact)
        self.assertEqual(row["approval_id"], approval.approval_id)
        self.assertEqual(row["step_id"], fact.step_id)
        self.assertEqual(row["attempt_id"], fact.attempt_id)
        attempts = self.bindings.load_attempt_history(fact.run_id)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["state"], "CREATED")
        with psycopg.connect(self.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    "UPDATE poc_maf_durable_approval_bindings "
                    "SET native_instance_id='forged' WHERE run_id=%s",
                    (fact.run_id,),
                )
        self.assertEqual(self.resume(fact)["native_instance_id"],
                         self.native["durable_instance_id"])

    def test_frozen_workflow_and_runtime_version_guard(self):
        fact, _ = self.request()
        for change in (
            {"workflow_version": "fixture-v2"},
            {"runtime_version": "agent-framework-azurefunctions==incompatible"},
            {"native_instance_id": "other-instance"},
            {"native_request_id": "other-request"},
            {"attempt_id": "other-attempt"},
            {"workflow_name": "other-workflow"},
        ):
            with self.subTest(change=change):
                with self.assertRaises(DurableBindingMismatch):
                    self.resume(fact, **change)
        self.assertEqual(len(self.bindings.load_attempt_history(fact.run_id)), 1)

    def test_all_or_none_rollback_and_no_checkpoint_aliasing(self):
        for values in (
            {"durable_instance_id": "orphan-instance"},
            {**self.native, "native_request_id": "file-checkpoint-request"},
        ):
            fact = VerificationFact.example(passed=False, evidence_ref=None)
            with self.assertRaises(ValueError):
                self.approvals.request(
                    fact, requester_principal="requester",
                    approver_principal="approver",
                    action_ref="tool",resource_ref="res",policy_ref="pol",
                    **values,
                )
            with psycopg.connect(self.dsn) as conn:
                self.assertEqual(conn.execute(
                    "SELECT count(*) FROM poc_runs WHERE run_id=%s",
                    (fact.run_id,),
                ).fetchone()[0],0)

    def test_unique_native_instance_conflict_rolls_back_second_run(self):
        first, _ = self.request()
        second = VerificationFact.example(passed=False, evidence_ref=None)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.approvals.request(
                second, requester_principal="poc-requester",
                approver_principal="poc-approver",
                action_ref="tool:poc",resource_ref="resource:poc",policy_ref="policy:poc",
                **{**self.native, "durable_request_id": "distinct-request-" + uuid4().hex},
            )
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM poc_runs WHERE run_id=%s",
                (second.run_id,),
            ).fetchone()[0], 0)
        self.assertEqual(self.resume(first)["native_instance_id"],
                         self.native["durable_instance_id"])

    def test_direct_insert_cannot_bind_another_attempt_lineage(self):
        old = VerificationFact.example(passed=False, evidence_ref=None)
        other = VerificationFact.example(passed=False, evidence_ref=None)
        a1 = self.approvals.request(
            old, requester_principal="poc-requester",
            approver_principal="poc-approver", action_ref="tool:poc",
            resource_ref="res", policy_ref="policy:poc",
        )
        self.approvals.request(
            other, requester_principal="poc-requester",
            approver_principal="poc-approver", action_ref="tool:poc",
            resource_ref="res", policy_ref="policy:poc",
        )
        with psycopg.connect(self.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    """INSERT INTO poc_maf_durable_approval_bindings
                       (approval_id,run_id,step_id,attempt_id,
                        native_instance_id,native_request_id,native_workflow_name,
                        frozen_workflow_version,frozen_runtime_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (a1.approval_id,old.run_id,old.step_id,other.attempt_id,
                     "fake-"+uuid4().hex,"req-"+uuid4().hex,"maf_mssql_poc_hitl",
                     "fixture-v1","sdk-fixture-v1"),
                )
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM poc_maf_durable_approval_bindings WHERE approval_id=%s",
                (a1.approval_id,),
            ).fetchone()[0], 0)

    def test_decided_request_cannot_reenter_pending_resume(self):
        fact, approval = self.request()
        self.approvals.decide(
            approval.approval_id,
            authenticated_principal="poc-approver",
            authorized=True, decision="APPROVED",
        )
        with self.assertRaises(DurableBindingMismatch):
            self.resume(fact)
        self.assertEqual(len(self.bindings.load_attempt_history(fact.run_id)), 1)

if __name__ == "__main__":
    unittest.main()
