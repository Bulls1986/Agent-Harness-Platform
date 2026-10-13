"""M3 v2 actual Segment / Step / Attempt business fact gate on real PostgreSQL."""
import os
import unittest
from enum import Enum
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.plan_guard import PlanGuard
from poc.closed_loop.replan_v2 import ReplanV2


class ProviderState(Enum):
    COMPLETED = "COMPLETED"


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"), "Real PG required")
class ReplanV2ExecutionPgTests(unittest.TestCase):
    def setUp(self):
        self.db = PgFacts()
        self.rid = "m3-e2e-" + uuid4().hex
        cmd = self.db.create(self.rid, prompt="synthetic verifier")
        self.db.dispatch(cmd)
        self.old = "old-" + self.rid
        self.new = "new-" + self.rid
        self.db.bind(cmd, self.old)
        guard = PlanGuard(self.db)
        guard.freeze_initial(self.rid, "sha256:recipe-v1")
        guard.request_replan(self.rid, 1, "sha256:recipe-v2", "verified need")
        self.rp = ReplanV2(self.db)
        self.key = self.rp.promote(self.rid, lambda _: ProviderState.COMPLETED)
        self.id1 = "v2-a-" + uuid4().hex
        self.id2 = "v2-b-" + uuid4().hex

    def bind(self):
        self.rp.claim(self.key)
        self.rp.bind(self.key, self.new)

    def test_v2_step_attempt_terminal_and_persistent_lineage(self):
        self.bind()
        self.assertIsNone(self.rp.start_step(self.rid, 2, self.new,
                           "verifier", "synthetic input", self.id1))
        self.rp.finish_step(self.rid, 2, self.new, "verifier", self.id1, "PASS")
        result = self.rp.complete(self.rid, 2, self.new,
                                  verified_outputs={"verifier": "PASS"})
        self.assertEqual(result["final_output"], "PASS")
        self.assertEqual(result["plan_version"], 2)
        facts = ReplanV2(PgFacts()).step_facts(self.rid, 2)
        self.assertEqual(facts["verifier"]["state"], "COMPLETED")
        self.assertEqual(facts["verifier"]["attempts"][0]["attempt_id"], self.id1)
        self.assertEqual(facts["verifier"]["attempts"][0]["plan_version"], 2)
        snap = self.db.snapshot(self.rid)
        self.assertEqual(snap["state"], "COMPLETED")
        self.assertEqual(snap["result"]["final_output"], "PASS")
        self.assertEqual(sum(x["type"]=="run.completed" for x in snap["events"]), 1)
        with self.assertRaises(UnsafeDispatch):
            self.rp.complete(self.rid, 2, self.new,
                             verified_outputs={"verifier": "PASS"})

    def test_v2_rejects_wrong_provider_and_unknown_ack(self):
        with self.assertRaises(UnsafeDispatch):
            self.rp.start_step(self.rid, 2, self.new, "verifier", "input", self.id1)
        self.bind()
        before = self.db.snapshot(self.rid)["events"]
        with self.assertRaises(UnsafeDispatch):
            self.rp.start_step(self.rid, 2, self.old, "verifier", "input", self.id1)
        with self.assertRaises(UnsafeDispatch):
            self.rp.start_step(self.rid, 1, self.new, "verifier", "input", self.id1)
        self.assertEqual(self.db.snapshot(self.rid)["events"], before)

    def test_v2_duplicate_dispatch_and_wrong_attempt_fail_closed(self):
        self.bind()
        self.rp.start_step(self.rid, 2, self.new, "verifier", "input", self.id1)
        before = self.db.snapshot(self.rid)["events"]
        with self.assertRaises(UnsafeDispatch):
            self.rp.start_step(self.rid, 2, self.new, "verifier", "input", self.id2)
        with self.assertRaises(UnsafeDispatch):
            self.rp.start_step(self.rid, 2, self.new, "verifier", "input", self.id1)
        with self.assertRaises(UnsafeDispatch):
            self.rp.finish_step(self.rid, 2, self.new, "verifier", self.id2, "evil")
        with self.assertRaises(UnsafeDispatch):
            self.rp.finish_step(self.rid, 2, self.old, "verifier", self.id1, "evil")
        self.assertEqual(self.db.snapshot(self.rid)["events"], before)
        self.rp.finish_step(self.rid, 2, self.new, "verifier", self.id1, "PASS")
        self.assertEqual(self.rp.start_step(self.rid, 2, self.new,
                         "verifier", "input", self.id2), "PASS")

    def test_v2_unverified_or_cancelled_does_not_complete(self):
        self.bind()
        self.rp.start_step(self.rid, 2, self.new, "verifier", "input", self.id1)
        with self.assertRaises(UnsafeDispatch):
            self.rp.complete(self.rid, 2, self.new,
                             verified_outputs={"verifier": "PASS"})
        self.rp.finish_step(self.rid, 2, self.new, "verifier", self.id1, "PASS")
        with self.assertRaises(UnsafeDispatch):
            self.rp.complete(self.rid, 2, self.new,
                             verified_outputs={"verifier": "FAIL"})
        self.db.request_cancel(self.rid)
        before = self.db.snapshot(self.rid)["events"]
        with self.assertRaises(UnsafeDispatch):
            self.rp.complete(self.rid, 2, self.new,
                             verified_outputs={"verifier": "PASS"})
        self.assertEqual(self.db.snapshot(self.rid)["events"], before)

    def test_cancelled_run_blocks_new_segment_claim_and_binding(self):
        self.db.request_cancel(self.rid)
        before = self.db.snapshot(self.rid)["events"]
        with self.assertRaises(UnsafeDispatch):
            self.rp.claim(self.key)
        self.assertEqual(self.rp.segment(self.rid)["state"], "PENDING")
        self.assertEqual(self.db.snapshot(self.rid)["events"], before)

        # A provider can be in flight when cancellation arrives; it must not
        # acquire a fresh confirmed binding after Run cancellation.
        self.db.acknowledge_cancel(self.rid)
        with self.assertRaises(UnsafeDispatch):
            self.rp.claim(self.key)
        self.assertEqual(self.rp.segment(self.rid)["state"], "PENDING")

    def test_cancel_between_claim_and_binding_refuses_late_provider(self):
        self.rp.claim(self.key)
        self.db.request_cancel(self.rid)
        before = self.db.snapshot(self.rid)["events"]
        with self.assertRaises(UnsafeDispatch):
            self.rp.bind(self.key,self.new)
        self.assertEqual(self.rp.segment(self.rid)["state"], "DISPATCHING")
        self.assertEqual(self.db.snapshot(self.rid)["events"], before)

    def test_v2_non_pure_effect_blocks_business_terminal(self):
        from poc.closed_loop.tool_receipt import ToolReceiptJournal
        self.bind()
        self.rp.start_step(self.rid, 2, self.new, "verifier", "input", self.id1)
        self.rp.finish_step(self.rid, 2, self.new, "verifier", self.id1, "PASS")
        # A real persisted intent must trump successful model/provider verdicts.
        journal = ToolReceiptJournal(self.db)
        journal.register_intent(self.rid, 2, "effect-step", "tool-attempt",
                                "non-pure-"+uuid4().hex, "owner-a", 1,
                                "write", "synthetic", "key-"+uuid4().hex)
        with self.assertRaises(UnsafeDispatch):
            self.rp.complete(self.rid, 2, self.new,
                             verified_outputs={"verifier": "PASS"})


if __name__ == "__main__":
    unittest.main()