"""DEV-M3 test-first Plan v1 freeze and Replan intent safety on actual PostgreSQL.

Partial gate only: no claim of native Hatchet dynamic Segment start or safe-stop ACK.
"""
import os
import unittest
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.plan_guard import PlanGuard

@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),
                     "Actual PostgreSQL is required for M3 durable facts tests")
class PlanGuardFactsTests(unittest.TestCase):
    def setUp(self):
        self.db=PgFacts()
        self.rid="m3-"+uuid4().hex
        self.key=self.db.create(self.rid,prompt="需求")
        self.db.dispatch(self.key)
        self.provider="hatchet-"+self.rid
        self.db.bind(self.key,self.provider)
        self.guard=PlanGuard(self.db)

    def test_freeze_idempotent_and_digest_cannot_drift(self):
        self.guard.freeze_initial(self.rid,recipe_digest="sha256:recipe-v1")
        self.guard.freeze_initial(self.rid,recipe_digest="sha256:recipe-v1")
        with self.assertRaises(UnsafeDispatch):
            self.guard.freeze_initial(self.rid,recipe_digest="sha256:altered")
        s=self.guard.inspect(self.rid)
        self.assertEqual(s["active_plan_version"],1)
        self.assertEqual(s["plans"],[{"version":1,"recipe_digest":"sha256:recipe-v1"}])

    def test_valid_admission_then_outdated_worker_rejected(self):
        self.guard.freeze_initial(self.rid,"sha256:recipe-v1")
        self.guard.admit(self.rid,expected_plan_version=1,provider_workflow_id=self.provider)
        with self.assertRaises(UnsafeDispatch):
            self.guard.admit(self.rid,expected_plan_version=2,provider_workflow_id=self.provider)
        with self.assertRaises(UnsafeDispatch):
            self.guard.admit(self.rid,expected_plan_version=1,provider_workflow_id="wrong")

    def test_replan_intent_fails_closed_until_verified_provider_quiescence(self):
        self.guard.freeze_initial(self.rid,"sha256:recipe-v1")
        self.guard.request_replan(self.rid,from_version=1,new_recipe_digest="sha256:recipe-v2",reason="verification failed")
        self.guard.request_replan(self.rid,from_version=1,new_recipe_digest="sha256:recipe-v2",reason="verification failed")
        with self.assertRaises(UnsafeDispatch):
            self.guard.admit(self.rid,expected_plan_version=1,provider_workflow_id=self.provider)
        with self.assertRaises(UnsafeDispatch):
            self.guard.request_replan(self.rid,1,"sha256:different","verification failed")
        other=PlanGuard(PgFacts())
        s=other.inspect(self.rid)
        self.assertEqual(s["active_plan_version"],1)
        self.assertEqual(s["replan"]["state"],"BLOCKED_PROVIDER_QUIESCENCE")
        self.assertEqual(self.db.snapshot(self.rid)["plan_version"],1)
        self.assertEqual(sum(e["type"]=="plan.replan.requested" for e in self.db.snapshot(self.rid)["events"]),1)

    def test_replan_requires_frozen_plan_and_running_run(self):
        with self.assertRaises(UnsafeDispatch):
            self.guard.request_replan(self.rid,1,"sha256:new","reason")
        self.guard.freeze_initial(self.rid,"sha256:recipe-v1")
        with self.assertRaises(UnsafeDispatch):
            self.guard.request_replan(self.rid,2,"sha256:new","reason")

if __name__=="__main__": unittest.main()
