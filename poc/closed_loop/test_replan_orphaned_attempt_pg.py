"""M3: old PURE Attempt may be superseded only after true Provider quiescence."""
import os
import unittest
from enum import Enum
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.plan_guard import PlanGuard
from poc.closed_loop.replan_v2 import ReplanV2


class ProviderState(Enum):
    COMPLETED="COMPLETED"
    RUNNING="RUNNING"
    CANCELLED="CANCELLED"


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),"Actual PostgreSQL required")
class ReplanOrphanedAttemptPgTests(unittest.TestCase):
    def setUp(self):
        self.db=PgFacts()
        self.rid="m3-orphan-"+uuid4().hex
        cmd=self.db.create(self.rid,prompt="synthetic verifier")
        self.db.dispatch(cmd)
        self.old="native-old-"+self.rid
        self.new="native-new-"+self.rid
        self.db.bind(cmd,self.old)
        self.guard=PlanGuard(self.db)
        self.guard.freeze_initial(self.rid,"sha256:v1")
        self.attempt="old-actual-"+self.rid
        self.db.start_step(self.rid,"pydantic","synthetic verifier",
                           attempt_id=self.attempt)
        self.guard.request_replan(self.rid,1,"sha256:v2","lost PG Step completion")
        self.rp=ReplanV2(self.db)

    def test_lost_pure_callback_may_supersede_only_after_native_terminal(self):
        key=self.rp.promote(self.rid,lambda _: ProviderState.COMPLETED,
                            resolve_inflight_pure=True)
        with self.db.tx() as c:
            before=c.execute(
                "SELECT state FROM harness_step_attempt WHERE attempt_id=%s",
                (self.attempt,),
            ).fetchone()
        self.assertEqual(before,("SUPERSEDED",))
        self.assertEqual(self.db.snapshot(self.rid)["steps"]["pydantic"]["state"],
                         "SUPERSEDED")
        self.rp.claim(key)
        self.rp.bind(key,self.new)
        with self.assertRaises(UnsafeDispatch):
            from poc.runtime_spi.contract import TypedEvent
            self.db.finish_step(self.rid,"pydantic","stale",
                [TypedEvent(self.rid,1,"run.completed","pydantic",{})],
                attempt_id=self.attempt)
        attempt2="new-"+self.rid
        self.rp.start_step(self.rid,2,self.new,"verifier","synthetic",attempt2)
        self.rp.finish_step(self.rid,2,self.new,"verifier",attempt2,"PASS")
        self.rp.complete(self.rid,2,self.new,verified_outputs={"verifier":"PASS"})
        self.assertEqual(self.db.snapshot(self.rid)["state"],"COMPLETED")
        self.assertEqual(self.db.snapshot(self.rid)["steps"]["pydantic"]["state"],
                         "SUPERSEDED")
        self.assertEqual(sum(x["type"]=="step.superseded"
                             for x in self.db.snapshot(self.rid)["events"]),1)

    def test_running_unknown_cancelled_and_default_never_supersede(self):
        with self.assertRaises(UnsafeDispatch):
            self.rp.promote(self.rid,lambda _: ProviderState.COMPLETED)
        for state in (ProviderState.RUNNING,ProviderState.CANCELLED,"COMPLETED"):
            with self.subTest(state=str(state)):
                with self.assertRaises(UnsafeDispatch):
                    self.rp.promote(self.rid,lambda _:state,
                                    resolve_inflight_pure=True)
        self.assertEqual(self.db.snapshot(self.rid)["plan_version"],1)
        with self.db.tx() as c:
            self.assertEqual(c.execute(
                "SELECT state FROM harness_step_attempt WHERE attempt_id=%s",
                (self.attempt,),
            ).fetchone(),("RUNNING",))

    def test_missing_old_attempt_evidence_never_autofills(self):
        with self.db.tx() as c:
            c.execute("DELETE FROM harness_step_attempt WHERE attempt_id=%s",
                      (self.attempt,))
        with self.assertRaises(UnsafeDispatch):
            self.rp.promote(self.rid,lambda _:ProviderState.COMPLETED,
                            resolve_inflight_pure=True)
        self.assertEqual(self.db.snapshot(self.rid)["plan_version"],1)

    def test_side_effect_intent_forbids_pure_orphan_abandonment(self):
        from poc.closed_loop.tool_receipt import ToolReceiptJournal
        # Replan intent already frozen, so original Tool registration must be
        # simulated as an existing journal fact from pre-intent execution.
        journal=ToolReceiptJournal(self.db)
        with self.db.tx() as c:
            c.execute(
                "INSERT INTO harness_tool_intent"
                "(run_id,plan_version,step_id,attempt_id,execution_id,owner_id,"
                "fencing_epoch,operation,target,idempotency_key,state) "
                "VALUES (%s,1,'effect','old-external',%s,'owner-A',1,"
                "'write','synthetic',%s,'UNKNOWN')",
                (self.rid,"side-effect-"+self.rid,"key-"+self.rid),
            )
        with self.assertRaises(UnsafeDispatch):
            self.rp.promote(self.rid,lambda _:ProviderState.COMPLETED,
                            resolve_inflight_pure=True)
        self.assertEqual(self.db.snapshot(self.rid)["plan_version"],1)


if __name__=="__main__":
    unittest.main()