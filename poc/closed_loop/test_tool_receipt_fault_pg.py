"""DEV-M4 real PostgreSQL + separate non-idempotent external ledger crash gate.

External DB intentionally has NO uniqueness/idempotency guard; a replay would
produce a second effect. SIGKILL occurs after the external commit and before
the Harness Receipt. SKIP is never considered a passing CI gate.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import signal
import subprocess
import sys
import unittest
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.tool_receipt import ToolReceiptJournal, EffectEvidence
from poc.closed_loop.external_ledger_demo import ExternalLedger


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL") and
                     os.getenv("HARNESS_LEDGER_DATABASE_URL"),
                     "Requires TWO real PostgreSQL databases: Harness + independent ledger")
class ToolReceiptFaultTests(unittest.TestCase):
    def setUp(self):
        self.db=PgFacts()
        self.ledger=ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"])
        self.journal=ToolReceiptJournal(self.db)
        self.rid="m4-tool-"+uuid4().hex
        cmd=self.db.create(self.rid,prompt="synthetic non-idempotent ledger task")
        self.db.dispatch(cmd)
        self.db.bind(cmd,"provider-"+self.rid)
        self.execution="exec-"+self.rid
        self.key="intent-"+self.rid
        self.journal.register_intent(
            self.rid,1,"effect-step","attempt-1",self.execution,
            "worker-A",7,"ledger.debit","synthetic-account",self.key)

    def _crash_worker(self, phase):
        proc=subprocess.run([
            sys.executable,"-B","-m","poc.closed_loop.nonidempotent_fault_worker",
            "--execution-id",self.execution,"--phase",phase,
        ],capture_output=True,text=True,timeout=20)
        self.assertEqual(proc.returncode,-signal.SIGKILL,
                         (proc.stdout,proc.stderr))
        return proc

    def test_sigkill_after_real_external_commit_reconciles_without_replay(self):
        self.journal.dispatch(self.execution,"worker-A",7)
        self._crash_worker("after-commit")
        self.assertEqual(len(self.ledger.find(self.execution)),1)
        self.assertEqual(self.journal.inspect(self.execution)["state"],"DISPATCHED")
        self.journal.mark_unknown(self.execution,"EXECUTOR_CRASH")
        self.assertEqual(self.journal.inspect(self.execution)["state"],"UNKNOWN")
        with self.assertRaises(UnsafeDispatch):
            self.journal.dispatch(self.execution,"worker-B",8)
        with self.assertRaises(UnsafeDispatch):
            self.journal.require_confirmed(self.execution)
        before=self.ledger.find(self.execution)[0]
        recovered=ToolReceiptJournal(PgFacts()).reconcile(
            self.execution,lambda execution:self.ledger.find(execution))
        self.assertEqual(recovered,"CONFIRMED_SUCCESS")
        self.assertEqual(self.journal.require_confirmed(self.execution),before.external_reference)
        self.assertEqual(len(self.ledger.find(self.execution)),1)
        self.assertEqual(self.journal.reconcile(
            self.execution,lambda _: (_ for _ in ()).throw(
                AssertionError("Do not query again after a confirmed Receipt"))),
            "CONFIRMED_SUCCESS")
        event_types=[e["type"] for e in self.db.snapshot(self.rid)["events"]]
        self.assertEqual(event_types.count("tool.receipt.confirmed"),1)

    def test_sigkill_before_external_commit_stays_unknown_not_assumed_unexecuted(self):
        self.journal.dispatch(self.execution,"worker-A",7)
        self._crash_worker("before-commit")
        self.assertEqual(self.ledger.find(self.execution),[])
        self.journal.mark_unknown(self.execution,"EXECUTOR_CRASH")
        with self.assertRaises(UnsafeDispatch):
            self.journal.reconcile(self.execution,
                lambda execution:self.ledger.find(execution))
        self.assertEqual(self.journal.inspect(self.execution)["state"],"UNKNOWN")
        with self.assertRaises(UnsafeDispatch):
            self.journal.dispatch(self.execution,"worker-A",7)

    def test_duplicate_unprotected_external_effects_are_never_auto_confirmed(self):
        self.journal.dispatch(self.execution,"worker-A",7)
        self.ledger.debit(self.execution,"ledger.debit","synthetic-account",self.key)
        self.ledger.debit(self.execution,"ledger.debit","synthetic-account",self.key)
        self.assertEqual(len(self.ledger.find(self.execution)),2)
        self.journal.mark_unknown(self.execution,"LOST_ACK")
        with self.assertRaises(UnsafeDispatch):
            self.journal.reconcile(self.execution, self.ledger.find)
        self.assertEqual(self.journal.inspect(self.execution)["state"],"UNKNOWN")

    def test_forged_receipt_wrong_owner_and_attempt_replay_denied(self):
        with self.assertRaises(UnsafeDispatch):
            self.journal.dispatch(self.execution,"worker-B",7)
        with self.assertRaises(UnsafeDispatch):
            self.journal.dispatch(self.execution,"worker-A",8)
        with self.assertRaises(UnsafeDispatch):
            self.journal.register_intent(self.rid,1,"effect-step","attempt-2",
                self.execution,"worker-B",8,"ledger.debit","synthetic-account",self.key)
        with self.assertRaises(UnsafeDispatch):
            self.journal.register_intent(self.rid,1,"effect-step","attempt-2",
                "another-"+self.execution,"worker-B",8,"ledger.debit",
                "synthetic-account",self.key)
        self.journal.dispatch(self.execution,"worker-A",7)
        self.journal.mark_unknown(self.execution,"LOST_ACK")
        false=EffectEvidence("bad",self.execution,"ledger.debit",
                             "synthetic-account","other-key")
        with self.assertRaises(UnsafeDispatch):
            self.journal.reconcile(self.execution,lambda _:[false])
        self.assertEqual(self.journal.inspect(self.execution)["state"],"UNKNOWN")

    def test_plan_change_blocks_dispatch(self):
        with self.db.tx() as c:
            c.execute("UPDATE harness_run SET plan_version=2 WHERE id=%s",(self.rid,))
        with self.assertRaises(UnsafeDispatch):
            self.journal.dispatch(self.execution,"worker-A",7)
        self.assertEqual(self.journal.inspect(self.execution)["state"],"RECORDED")

    def test_existing_non_pure_intent_blocks_pure_plan_promotion(self):
        from enum import Enum
        from poc.closed_loop.plan_guard import PlanGuard
        from poc.closed_loop.replan_v2 import ReplanV2
        class ProviderStatus(Enum):
            COMPLETED="COMPLETED"
        plan=PlanGuard(self.db)
        plan.freeze_initial(self.rid,"sha256:pure-v1")
        plan.request_replan(self.rid,1,"sha256:pure-v2","verification changed")
        with self.assertRaises(UnsafeDispatch):
            ReplanV2(self.db).promote(self.rid,lambda _:ProviderStatus.COMPLETED)
        self.assertEqual(self.db.snapshot(self.rid)["plan_version"],1)

    def test_replan_intent_blocks_new_tool_intent(self):
        from poc.closed_loop.plan_guard import PlanGuard
        plan=PlanGuard(self.db)
        plan.freeze_initial(self.rid,"sha256:pure-v1")
        plan.request_replan(self.rid,1,"sha256:pure-v2","verification changed")
        with self.assertRaises(UnsafeDispatch):
            self.journal.register_intent(self.rid,1,"new-step","attempt-new",
                "execution-new-"+self.rid,"worker-A",7,
                "ledger.debit","synthetic-account","intent-new-"+self.rid)

    def test_replan_intent_blocks_pending_tool_dispatch(self):
        from poc.closed_loop.plan_guard import PlanGuard
        plan=PlanGuard(self.db)
        plan.freeze_initial(self.rid,"sha256:pure-v1")
        plan.request_replan(self.rid,1,"sha256:pure-v2","verification changed")
        with self.assertRaises(UnsafeDispatch):
            self.journal.dispatch(self.execution,"worker-A",7)
        self.assertEqual(self.journal.inspect(self.execution)["state"],"RECORDED")

    def test_concurrent_recovery_one_receipt_event_and_no_extra_external_effect(self):
        self.journal.dispatch(self.execution,"worker-A",7)
        self.ledger.debit(self.execution,"ledger.debit","synthetic-account",self.key)
        self.journal.mark_unknown(self.execution,"LOST_ACK")
        def recover(_):
            return ToolReceiptJournal(PgFacts()).reconcile(
                self.execution,self.ledger.find)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(recover,(1,2)))
        self.assertEqual(outcomes,["CONFIRMED_SUCCESS","CONFIRMED_SUCCESS"])
        self.assertEqual(len(self.ledger.find(self.execution)),1)
        self.assertEqual(sum(e["type"]=="tool.receipt.confirmed"
            for e in self.db.snapshot(self.rid)["events"]),1)


if __name__=="__main__":
    unittest.main()
