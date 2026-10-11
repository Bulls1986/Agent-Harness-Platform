"""DEV-M4: acknowledged segment creation with lost ACK, PG reconciliation.

The callback is a TRUSTED Provider query port. These are real PostgreSQL
transaction tests; actual Hatchet metadata lookup has a separate live gate.
"""
import os
import unittest
from enum import Enum
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.plan_guard import PlanGuard
from poc.closed_loop.replan_v2 import ReplanV2
from poc.closed_loop.segment_reconcile import ProviderMatch, SegmentReconciler


class Status(Enum):
    COMPLETED = "COMPLETED"


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),
                     "Real PostgreSQL required; skipped tests do not count as PASS")
class SegmentAckReconcilePgTests(unittest.TestCase):
    def setUp(self):
        self.db=PgFacts()
        self.rid="m4-ack-"+uuid4().hex
        cmd=self.db.create(self.rid,prompt="pure synthetic")
        self.db.dispatch(cmd)
        self.old="old-"+self.rid
        self.db.bind(cmd,self.old)
        guard=PlanGuard(self.db)
        guard.freeze_initial(self.rid,"sha256:recipe1")
        guard.request_replan(self.rid,1,"sha256:recipe2","pure-replan")
        self.replan=ReplanV2(self.db)
        self.key=self.replan.promote(self.rid,lambda _: Status.COMPLETED)
        self.replan.claim(self.key)
        self.replan.unknown(self.key)
        self.reconciler=SegmentReconciler(self.db)
        self.candidate="provider-"+self.rid

    def match(self, *, provider_id=None, command_key=None,
              run_id=None, plan_version=2):
        return ProviderMatch(
            workflow_run_id=provider_id or self.candidate,
            command_key=command_key or self.key,
            run_id=run_id or self.rid,
            plan_version=plan_version,
        )

    def test_one_verified_candidate_repairs_binding_without_create(self):
        called=[]
        def native_lookup(key):
            called.append(key)
            return [self.match()]
        resolved=self.reconciler.reconcile_unknown(self.key,native_lookup)
        self.assertEqual(resolved,self.candidate)
        self.assertEqual(called,[self.key])
        self.assertEqual(self.replan.segment(self.rid)["state"],"CONFIRMED")
        self.assertEqual(self.replan.segment(self.rid)["provider_workflow_id"],self.candidate)
        self.replan.admit(self.rid,2,self.candidate)
        with self.assertRaises(UnsafeDispatch):
            self.replan.claim(self.key)  # Never resubmit a reconciled Workflow
        self.assertEqual(self.reconciler.reconcile_unknown(
            self.key,lambda _: (_ for _ in ()).throw(AssertionError("No lookup on repeat"))),
            self.candidate)
        events=self.db.snapshot(self.rid)["events"]
        self.assertEqual(sum(e["type"]=="workflow.segment.reconciled" for e in events),1)

    def test_missing_ambiguous_or_invalid_native_evidence_fail_closed(self):
        for results in (
            [], [self.match(provider_id="two-"+self.rid),self.match()],
            [self.match(command_key="other-key")],
            [self.match(run_id="other-run")],
            [self.match(plan_version=1)],
            [self.match(provider_id=self.old)],
            [object()],
            [self.match(),self.match()],  # duplicate provider evidence is ambiguous
        ):
            with self.subTest(results=str(results)),self.assertRaises(UnsafeDispatch):
                self.reconciler.reconcile_unknown(self.key,lambda _,r=results:r)
            self.assertEqual(self.replan.segment(self.rid)["state"],"BLOCKED_UNKNOWN")
            self.assertIsNone(self.replan.segment(self.rid)["provider_workflow_id"])
        with self.assertRaises(UnsafeDispatch):
            self.reconciler.reconcile_unknown(self.key,lambda _: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(self.db.snapshot(self.rid)["plan_version"],2)

    def test_reconciliation_never_runs_without_uncertain_dispatch(self):
        from poc.closed_loop.replan_v2 import ReplanV2
        new_rid="m4-pending-"+uuid4().hex
        key=self.db.create(new_rid,prompt="pure")
        self.db.dispatch(key)
        old_id="first-"+new_rid
        self.db.bind(key,old_id)
        guard=PlanGuard(self.db)
        guard.freeze_initial(new_rid,"sha256:v1")
        guard.request_replan(new_rid,1,"sha256:v2","reason")
        outbox=ReplanV2(self.db).promote(new_rid,lambda _:Status.COMPLETED)
        with self.assertRaises(UnsafeDispatch):
            self.reconciler.reconcile_unknown(
                outbox,lambda _: [ProviderMatch("id",outbox,new_rid,2)])
        self.assertEqual(ReplanV2(self.db).segment(new_rid)["state"],"PENDING")

    def test_parallel_reconcilers_cannot_bind_different_provider_runs(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        gate = Barrier(2)
        providers = ("native-A-" + self.rid, "native-B-" + self.rid)

        def reconcile(provider):
            def native(_):
                gate.wait(timeout=15)
                return [self.match(provider_id=provider)]
            return SegmentReconciler(PgFacts()).reconcile_unknown(self.key, native)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reconcile, p) for p in providers]
            successes = []
            rejected = []
            for item in futures:
                try:
                    successes.append(item.result(timeout=30))
                except UnsafeDispatch as exc:
                    rejected.append(str(exc))
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(rejected), 1)
        self.assertIn(successes[0], providers)
        state = ReplanV2(PgFacts()).segment(self.rid)
        self.assertEqual(state["state"], "CONFIRMED")
        self.assertEqual(state["provider_workflow_id"], successes[0])
        events = self.db.snapshot(self.rid)["events"]
        self.assertEqual(sum(e["type"] == "workflow.segment.reconciled" for e in events), 1)

    def test_idempotent_ledger_persists_after_reconnect(self):
        self.reconciler.reconcile_unknown(self.key,lambda _:[self.match()])
        second=SegmentReconciler(PgFacts())
        self.assertEqual(second.reconcile_unknown(self.key,lambda _: []),self.candidate)
        self.assertEqual(ReplanV2(PgFacts()).segment(self.rid)["state"],"CONFIRMED")


if __name__=="__main__":
    unittest.main()
