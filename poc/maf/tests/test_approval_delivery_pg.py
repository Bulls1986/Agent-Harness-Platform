"""A26 real PostgreSQL checks for crash-safe native Approval response delivery."""
import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from approval_delivery import ApprovalDelivery, DeliveryConflict
from approval_wait import ApprovalWaitStore
from task_ledger import TaskLedger
from workflow_probe import VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"),"dedicated PostgreSQL CI")
class ApprovalDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_POSTGRES_DSN"]
        TaskLedger(cls.dsn).initialize()
        cls.approvals=ApprovalWaitStore(cls.dsn)
        cls.delivery=ApprovalDelivery(cls.dsn)

    def create_decided(self, decision):
        fact=VerificationFact.example(passed=False,evidence_ref=None)
        request=self.approvals.request(
            fact,requester_principal="fixture-requester",
            approver_principal="fixture-approver",action_ref="tool:fixture",
            resource_ref="resource:fixture",policy_ref="policy:fixture",
            native_request_id=f"maf-{uuid4().hex}",
            native_checkpoint_ref=f"checkpoint-{uuid4().hex}",
            native_workflow_name="poc-native-approval",
        )
        return fact,request

    def decide(self,request,decision):
        return self.approvals.decide(
            request.approval_id,authenticated_principal="fixture-approver",
            authorized=True,decision=decision
        )

    def test_committed_decision_before_delivery_is_recoverable(self):
        fact,request=self.create_decided("APPROVED")
        self.decide(request,"APPROVED")
        # New process would only need Run ID; no pending Approval exists.
        loaded=ApprovalDelivery(self.dsn).load_decided(fact.run_id)
        self.assertEqual(loaded["decision"],"APPROVED")
        claim=ApprovalDelivery(self.dsn).claim(fact.run_id)
        self.assertEqual(claim.state,"CLAIMED")
        self.assertEqual(claim.request_id,loaded["native_request_id"])
        with self.assertRaises(DeliveryConflict):
            self.delivery.complete(fact.run_id,token="wrong-token",output_kind="SIMULATED_EXECUTION")
        self.delivery.complete(fact.run_id,token=claim.token,output_kind="SIMULATED_EXECUTION")
        second=self.delivery.claim(fact.run_id)
        self.assertEqual(second.state,"ALREADY_APPLIED")
        self.assertEqual(second.output_kind,"SIMULATED_EXECUTION")
        with self.assertRaises(DeliveryConflict):
            self.delivery.complete(fact.run_id,token=claim.token,output_kind="SIMULATED_EXECUTION")

    def test_delivery_intent_crash_quarantines_uncertain_result(self):
        fact,request=self.create_decided("APPROVED")
        self.decide(request,"APPROVED")
        first=self.delivery.claim(fact.run_id)
        self.assertEqual(first.state,"CLAIMED")
        recovered=ApprovalDelivery(self.dsn).claim(fact.run_id)
        self.assertEqual(recovered.state,"UNKNOWN_REQUIRES_RECONCILIATION")
        self.assertEqual(self.delivery.claim(fact.run_id).state,"UNKNOWN_REQUIRES_RECONCILIATION")
        with self.assertRaises(DeliveryConflict):
            self.delivery.complete(fact.run_id,token=first.token,output_kind="SIMULATED_EXECUTION")
        # Zero speculative second native request is issued by this store.

    def test_rejected_decision_cannot_be_changed_by_delivery(self):
        fact,request=self.create_decided("REJECTED")
        self.decide(request,"REJECTED")
        claim=self.delivery.claim(fact.run_id)
        with self.assertRaises(DeliveryConflict):
            self.delivery.complete(fact.run_id,token=claim.token,output_kind="SIMULATED_EXECUTION")
        self.delivery.complete(fact.run_id,token=claim.token,output_kind="DENIED_NO_EXECUTION")
        self.assertEqual(self.delivery.claim(fact.run_id).state,"ALREADY_APPLIED")


if __name__=="__main__":
    unittest.main()
