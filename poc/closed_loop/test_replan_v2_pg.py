"""DEV-M3 v1→v2 domain/segment safety against real Harness PostgreSQL.

Synthetic provider-state probes here are NEGATIVE contracts; a separate
Hatchet Engine live gate is required to claim provider quiescence evidence.
"""
import os
from enum import Enum
from uuid import uuid4
import unittest

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.plan_guard import PlanGuard
from poc.closed_loop.replan_v2 import ReplanV2


class ProviderState(Enum):
    COMPLETED = "COMPLETED"
    RUNNING = "RUNNING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),
                     "Real PostgreSQL required; skip is NOT a PASS")
class ReplanV2PgTests(unittest.TestCase):
    def setUp(self):
        self.db = PgFacts()
        self.rid = "m3-v2-" + uuid4().hex
        key = self.db.create(self.rid, prompt="generic synthetic intent")
        self.db.dispatch(key)
        self.old = "hatchet-old-" + self.rid
        self.db.bind(key, self.old)
        self.guard = PlanGuard(self.db)
        self.guard.freeze_initial(self.rid, "sha256:recipe-one")
        self.guard.request_replan(self.rid, 1, "sha256:recipe-two", "verifier replan")
        self.replan = ReplanV2(self.db)

    def test_not_terminal_or_ambiguous_quiescence_never_promotes(self):
        for state in (ProviderState.RUNNING, ProviderState.CANCELLED,
                      ProviderState.FAILED, "COMPLETED", None):
            with self.assertRaises(UnsafeDispatch):
                self.replan.promote(self.rid, lambda _: state)
        with self.assertRaises(UnsafeDispatch):
            self.replan.promote(self.rid, lambda _: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(self.db.snapshot(self.rid)["plan_version"], 1)
        self.assertIsNone(self.replan.segment(self.rid))
        self.assertEqual(len(self.guard.inspect(self.rid)["plans"]), 1)

    def test_v2_atomic_promotion_and_versioned_fencing(self):
        key = self.replan.promote(self.rid, lambda x: ProviderState.COMPLETED)
        self.assertEqual(self.replan.promote(self.rid, lambda _: ProviderState.RUNNING), key)
        self.assertEqual(self.db.snapshot(self.rid)["plan_version"], 2)
        self.assertEqual(self.replan.segment(self.rid)["state"], "PENDING")
        self.assertEqual(self.guard.inspect(self.rid)["plans"], [
            {"version": 1, "recipe_digest": "sha256:recipe-one"},
            {"version": 2, "recipe_digest": "sha256:recipe-two"},
        ])
        with self.assertRaises(UnsafeDispatch):
            self.guard.admit(self.rid, expected_plan_version=1,
                             provider_workflow_id=self.old)
        with self.assertRaises(UnsafeDispatch):
            self.replan.admit(self.rid, 2, "wrong")
        with self.assertRaises(UnsafeDispatch):
            self.db.complete(self.rid)
        with self.assertRaises(UnsafeDispatch):
            self.db.start_step(self.rid, "openai", "unverified")

    def test_dispatch_binding_atomic_and_no_ambiguous_duplicate(self):
        key = self.replan.promote(self.rid, lambda _: ProviderState.COMPLETED)
        self.replan.claim(key)
        with self.assertRaises(UnsafeDispatch):
            self.replan.claim(key)
        self.replan.bind(key, "new-engine-id-" + self.rid)
        self.replan.admit(self.rid, 2, "new-engine-id-" + self.rid)
        with self.assertRaises(UnsafeDispatch):
            self.replan.admit(self.rid, 1, self.old)
        with self.assertRaises(UnsafeDispatch):
            self.replan.bind(key, "other-engine-id")
        self.assertEqual(ReplanV2(PgFacts()).segment(self.rid)["state"], "CONFIRMED")

    def test_failed_provider_creation_blocks_retries(self):
        key = self.replan.promote(self.rid, lambda _: ProviderState.COMPLETED)
        self.replan.claim(key)
        self.replan.unknown(key)
        self.assertEqual(self.replan.segment(self.rid)["state"], "BLOCKED_UNKNOWN")
        with self.assertRaises(UnsafeDispatch):
            self.replan.claim(key)
        with self.assertRaises(UnsafeDispatch):
            self.replan.admit(self.rid, 2, "some-run")

    def test_running_step_blocks_promotion_and_stale_attempt_cannot_commit(self):
        # A stale or incomplete Platform Step remains a stronger veto even
        # when the Provider observation claims it has terminated.
        with self.db.tx() as c:
            c.execute("UPDATE harness_step SET state='RUNNING' "
                      "WHERE run_id=%s AND id='pydantic'", (self.rid,))
        with self.assertRaises(UnsafeDispatch):
            self.replan.promote(self.rid, lambda _: ProviderState.COMPLETED)
        self.assertEqual(self.db.snapshot(self.rid)["plan_version"], 1)
        with self.db.tx() as c:
            c.execute("UPDATE harness_step SET state='PENDING' "
                      "WHERE run_id=%s AND id='pydantic'", (self.rid,))
        self.replan.promote(self.rid, lambda _: ProviderState.COMPLETED)
        # Simulate an old Worker replaying a stale completion after v2 commit.
        with self.db.tx() as c:
            c.execute("UPDATE harness_step SET state='RUNNING' "
                      "WHERE run_id=%s AND id='pydantic'", (self.rid,))
        from poc.runtime_spi.contract import TypedEvent
        with self.assertRaises(UnsafeDispatch):
            self.db.finish_step(self.rid, "pydantic", "late",
                                [TypedEvent(self.rid, 1, "run.completed", "pydantic",
                                            {"result": "late"})])
        self.assertEqual(self.db.snapshot(self.rid)["steps"]["pydantic"]["state"],
                         "RUNNING")
        self.assertEqual(self.db.snapshot(self.rid)["plan_version"], 2)


if __name__ == "__main__":
    unittest.main()
