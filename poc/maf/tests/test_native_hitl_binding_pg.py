"""Real PostgreSQL contract tests for opaque native HITL request mapping."""
import os
import sys
import unittest
from pathlib import Path

import psycopg

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from approval_wait import ApprovalWaitStore
from task_ledger import TaskLedger
from workflow_probe import VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"),"requires dedicated PostgreSQL")
class NativeHitlBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_POSTGRES_DSN"]
        TaskLedger(cls.dsn).initialize()
        cls.store=ApprovalWaitStore(cls.dsn)

    def request(self,**kwargs):
        return self.store.request(
            VerificationFact.example(passed=False,evidence_ref=None),
            requester_principal="fixture-requester",
            approver_principal="fixture-approver",
            action_ref="tool:poc",resource_ref="resource:poc",policy_ref="policy:poc",
            **kwargs,
        )

    def test_binding_immutable_and_same_run(self):
        approval=self.request(native_request_id="native-request-1",
                             native_checkpoint_ref="native-checkpoint-1",
                             native_workflow_name="native-poc-workflow")
        binding=ApprovalWaitStore(self.dsn).load_native_binding(approval.run_id)
        self.assertEqual(binding["run_id"],approval.run_id)
        self.assertEqual(binding["approval_id"],approval.approval_id)
        self.assertEqual(binding["native_request_id"],"native-request-1")
        with psycopg.connect(self.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    "UPDATE poc_maf_approval_bindings SET native_request_id='forged' WHERE approval_id=%s",
                    (approval.approval_id,),
                )
        self.assertEqual(self.store.load_pending(approval.run_id).approval_id,approval.approval_id)

    def test_partial_binding_rejected_before_transaction(self):
        with self.assertRaises(ValueError):
            self.request(native_request_id="missing-checkpoint")
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM poc_maf_approval_bindings WHERE native_request_id=%s",
                ("missing-checkpoint",),
            ).fetchone()[0],0)


if __name__=="__main__":
    unittest.main()
