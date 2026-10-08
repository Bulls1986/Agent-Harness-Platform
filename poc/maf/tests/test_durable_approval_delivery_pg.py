"""PostgreSQL contract tests for A34 MSSQL-native approval response crash gaps."""
import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from approval_wait import ApprovalWaitStore
from durable_approval_binding import DurableBindingMismatch
from durable_approval_delivery import DurableApprovalDelivery
from task_ledger import TaskLedger
from workflow_probe import VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"), "requires real PostgreSQL")
class DurableDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["POC_POSTGRES_DSN"]
        TaskLedger(cls.dsn).initialize()

    def setUp(self):
        self.approvals = ApprovalWaitStore(self.dsn)
        self.store = DurableApprovalDelivery(self.dsn)
        self.keys = {
            "native_instance_id": "instance-" + uuid4().hex,
            "native_request_id": "request-" + uuid4().hex,
            "workflow_name": "maf_mssql_poc_hitl",
            "workflow_version": "fixture-v1",
            "runtime_version": "sdk-fixture-v1",
        }

    def create(self, decision=None):
        f = VerificationFact.example(passed=False, evidence_ref=None)
        request = self.approvals.request(
            f, requester_principal="poc-requester",
            approver_principal="poc-approver", action_ref="tool:poc",
            resource_ref="resource:poc", policy_ref="policy:poc",
            durable_instance_id=self.keys["native_instance_id"],
            durable_request_id=self.keys["native_request_id"],
            durable_workflow_name=self.keys["workflow_name"],
            frozen_workflow_version=self.keys["workflow_version"],
            frozen_runtime_version=self.keys["runtime_version"],
        )
        if decision:
            self.approvals.decide(
                request.approval_id,
                authenticated_principal="poc-approver",
                authorized=True, decision=decision,
            )
        return f, request

    def claim(self, fact, **changes):
        return DurableApprovalDelivery(self.dsn).claim(
            fact.run_id, **{**self.keys, "attempt_id": fact.attempt_id, **changes},
        )

    def test_safe_crash_after_decision_before_delivery_claim(self):
        fact, _ = self.create("APPROVED")
        # New connection/adapter after approval committed; no native response yet.
        first = self.claim(fact)
        self.assertEqual(first.state, "CLAIMED")
        self.assertEqual(first.decision, "APPROVED")
        self.assertEqual(first.request_id, self.keys["native_request_id"])
        with self.assertRaises(DurableBindingMismatch):
            self.store.complete(fact.run_id, token=first.token,
                                native_status="Running", output_kind="SIMULATED_EXECUTION")
        self.store.complete(fact.run_id, token=first.token,
                            native_status="Completed", output_kind="SIMULATED_EXECUTION")
        self.assertEqual(self.claim(fact).state, "ALREADY_APPLIED")
        with self.assertRaises(DurableBindingMismatch):
            self.store.complete(fact.run_id, token=first.token,
                                native_status="Completed", output_kind="SIMULATED_EXECUTION")

    def test_claimed_then_crash_is_unknown_no_replay(self):
        fact, _ = self.create("APPROVED")
        first = self.claim(fact)
        self.assertEqual(first.state, "CLAIMED")
        second = self.claim(fact)
        self.assertEqual(second.state, "UNKNOWN_REQUIRES_RECONCILIATION")
        self.assertIsNone(second.token)
        self.assertEqual(self.claim(fact).state, second.state)
        with self.assertRaises(DurableBindingMismatch):
            self.store.complete(fact.run_id, token=first.token,
                                native_status="Completed", output_kind="SIMULATED_EXECUTION")

    def test_unbound_or_undecided_or_mismatched_fails_before_dispatch(self):
        fact, _ = self.create()
        with self.assertRaises(DurableBindingMismatch):
            self.claim(fact)
        with self.assertRaises(DurableBindingMismatch):
            self.store.claim("unbound-" + uuid4().hex,
                             attempt_id=fact.attempt_id, **self.keys)
        self.approvals.decide(
            self.approvals.load_pending(fact.run_id).approval_id,
            authenticated_principal="poc-approver", authorized=True,
            decision="APPROVED",
        )
        for mismatch in (
            {"workflow_version": "fixture-v2"},
            {"runtime_version": "changed-sdk"},
            {"native_request_id": "wrong"},
            {"native_instance_id": "wrong"},
            {"attempt_id": "other"},
        ):
            with self.subTest(mismatch=mismatch):
                with self.assertRaises(DurableBindingMismatch):
                    self.claim(fact, **mismatch)
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                """SELECT COUNT(*) FROM poc_maf_hitl_deliveries d
                   JOIN poc_approvals a ON a.approval_id=d.approval_id
                   WHERE a.run_id=%s""", (fact.run_id,),
            ).fetchone()[0], 0)

    def test_rejection_never_claims_approved_output(self):
        fact, _ = self.create("REJECTED")
        claimed = self.claim(fact)
        self.assertEqual(claimed.decision, "REJECTED")
        with self.assertRaises(DurableBindingMismatch):
            self.store.complete(fact.run_id, token=claimed.token,
                                native_status="Completed", output_kind="SIMULATED_EXECUTION")
        self.store.complete(fact.run_id, token=claimed.token,
                            native_status="Completed", output_kind="DENIED_NO_EXECUTION")
        self.assertEqual(self.claim(fact).state, "ALREADY_APPLIED")


if __name__ == "__main__":
    unittest.main()
