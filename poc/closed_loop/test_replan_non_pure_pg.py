"""M3 HC-01/02: non-PURE Replan is opt-in only after verified receipts (real PG).

The synthetic receipt callback is a trusted-test stand-in for an external
ledger query, NOT an independent external effect E2E. M4 verifies that gate.
"""
import os
import unittest
from enum import Enum
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.plan_guard import PlanGuard
from poc.closed_loop.replan_v2 import ReplanV2
from poc.closed_loop.tool_receipt import ToolReceiptJournal, EffectEvidence


class ProviderStatus(Enum):
    COMPLETED="COMPLETED"


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"), "Actual PG required")
class ReplanNonPurePgTests(unittest.TestCase):
    def setUp(self):
        self.db=PgFacts()
        self.rid="m3-effect-"+uuid4().hex
        key=self.db.create(self.rid,prompt="synthetic")
        self.db.dispatch(key)
        self.old="provider-old-"+self.rid
        self.new="provider-new-"+self.rid
        self.db.bind(key,self.old)
        self.guard=PlanGuard(self.db)
        self.guard.freeze_initial(self.rid,"sha256:effect-v1")
        self.journal=ToolReceiptJournal(self.db)
        self.execution="execution-"+self.rid
        self.effect_key="key-"+self.rid
        self.journal.register_intent(self.rid,1,"effect",
            "attempt-original",self.execution,"worker-A",7,
            "external.write","synthetic",self.effect_key)
        self.journal.dispatch(self.execution,"worker-A",7)

    def request(self):
        self.guard.request_replan(self.rid,1,"sha256:effect-v2","verified receipt replan")
        return ReplanV2(self.db)

    def receipt(self):
        return EffectEvidence("external:"+self.execution,self.execution,
                              "external.write","synthetic",self.effect_key)

    def test_unknown_or_unconfirmed_side_effect_must_block_every_promotion(self):
        self.journal.mark_unknown(self.execution,"LOST_ACK")
        rp=self.request()
        with self.assertRaises(UnsafeDispatch):
            rp.promote(self.rid,lambda _: ProviderStatus.COMPLETED)
        with self.assertRaises(UnsafeDispatch):
            rp.promote(self.rid,lambda _: ProviderStatus.COMPLETED,
                       effect_policy="CONFIRMED_RECEIPTS_ONLY")
        self.assertEqual(self.db.snapshot(self.rid)["plan_version"],1)
        self.assertIsNone(rp.segment(self.rid))

    def test_reconciled_receipt_allows_explicit_safe_continuation_without_replay(self):
        self.assertEqual(self.journal.reconcile(
            self.execution,lambda _: [self.receipt()]),"CONFIRMED_SUCCESS")
        rp=self.request()
        with self.assertRaises(UnsafeDispatch):
            rp.promote(self.rid,lambda _: ProviderStatus.COMPLETED)
        key=rp.promote(self.rid,lambda _: ProviderStatus.COMPLETED,
                       effect_policy="CONFIRMED_RECEIPTS_ONLY")
        self.assertEqual(rp.promote(self.rid,lambda _: ProviderStatus.COMPLETED,
                                    effect_policy="CONFIRMED_RECEIPTS_ONLY"),key)
        with self.assertRaises(UnsafeDispatch):
            rp.promote(self.rid,lambda _: ProviderStatus.COMPLETED)
        rp.claim(key)
        rp.bind(key,self.new)
        rp.start_step(self.rid,2,self.new,"verifier","input","v2-"+self.rid)
        rp.finish_step(self.rid,2,self.new,"verifier","v2-"+self.rid,"APPROVED")
        result=rp.complete(self.rid,2,self.new,verified_outputs={"verifier":"APPROVED"})
        self.assertEqual(result["side_effect_policy"],"CONFIRMED_RECEIPTS_ONLY")
        self.assertEqual(result["reconciled_receipts"],
                         [{"execution_id":self.execution,
                           "external_reference":"external:"+self.execution}])
        self.assertEqual(self.db.snapshot(self.rid)["state"],"COMPLETED")
        self.assertEqual(self.journal.require_confirmed(self.execution),
                         "external:"+self.execution)

    def test_forged_or_new_v2_effect_never_enables_terminal(self):
        self.journal.reconcile(self.execution,lambda _: [self.receipt()])
        rp=self.request()
        key=rp.promote(self.rid,lambda _: ProviderStatus.COMPLETED,
                       effect_policy="CONFIRMED_RECEIPTS_ONLY")
        rp.claim(key);rp.bind(key,self.new)
        rp.start_step(self.rid,2,self.new,"verifier","input","v2-"+self.rid)
        rp.finish_step(self.rid,2,self.new,"verifier","v2-"+self.rid,"APPROVED")
        # An unexpected new v2 Tool Intent is outside the frozen v1 receipt
        # continuation policy, even when a previous receipt was verified.
        self.journal.register_intent(self.rid,2,"unexpected","a-v2",
            "second-"+self.execution,"worker-B",8,
            "external.write","synthetic","second-"+self.effect_key)
        before=self.db.snapshot(self.rid)["events"]
        with self.assertRaises(UnsafeDispatch):
            rp.complete(self.rid,2,self.new,verified_outputs={"verifier":"APPROVED"})
        self.assertEqual(self.db.snapshot(self.rid)["events"],before)
        self.assertEqual(self.db.snapshot(self.rid)["state"],"RUNNING")


if __name__=="__main__":
    unittest.main()