"""Real PG HC-03 owner/fencing takeover after a non-idempotent Tool crash.

No Hatchet dispatcher is replicated here. The DB records a *permit*, not
a technical task lease. B only acquires after A's authority expires and
the effect has already become UNKNOWN; B can reconcile but never redispatch.
"""
from concurrent.futures import ThreadPoolExecutor
import os
import unittest
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.tool_receipt import ToolReceiptJournal
from poc.closed_loop.external_ledger_demo import ExternalLedger
from poc.closed_loop.tool_recovery_owner import ToolRecoveryOwner


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL") and
                     os.getenv("HARNESS_LEDGER_DATABASE_URL"),
                     "Real Harness PG and external non-idempotent ledger required")
class ToolRecoveryOwnerPgTests(unittest.TestCase):
    def setUp(self):
        self.db=PgFacts()
        self.ledger=ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"])
        self.journal=ToolReceiptJournal(self.db)
        self.owner=ToolRecoveryOwner(self.db)
        self.rid="m4-lease-"+uuid4().hex
        key=self.db.create(self.rid,prompt="synthetic crash recovery")
        self.db.dispatch(key)
        self.db.bind(key,"native-"+self.rid)
        self.execution="exec-"+self.rid
        self.journal.register_intent(
            self.rid,1,"write-step","attempt-A",self.execution,
            "worker-A",7,"ledger.debit","synthetic-account",
            "ledger-key-"+self.rid,
        )
        self.owner.initialize(self.execution,"worker-A",7,lease_seconds=30)
        self.journal.dispatch(self.execution,"worker-A",7)
        self.ledger.debit(self.execution,"ledger.debit",
                          "synthetic-account","ledger-key-"+self.rid)
        self.journal.mark_unknown(self.execution,"EXECUTOR_CRASH")

    def _expire_original(self):
        # Fault injection simulates verified owner lease expiry on the DB
        # server; production code itself MUST NOT accept a client clock.
        with self.db.tx() as c:
            c.execute("UPDATE harness_tool_recovery_authority "
                      "SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))

    def test_b_takes_over_only_after_expiry_and_never_reexecutes_tool(self):
        with self.assertRaises(UnsafeDispatch):
            self.owner.takeover(self.execution,"worker-B",expected_epoch=7)
        self._expire_original()
        permit=self.owner.takeover(self.execution,"worker-B",expected_epoch=7)
        self.assertEqual(permit.fencing_epoch,8)
        self.assertEqual(permit.owner_id,"worker-B")
        with self.assertRaises(UnsafeDispatch):
            self.owner.admit(self.execution,"worker-A",7)
        with self.assertRaises(UnsafeDispatch):
            self.owner.reconcile(self.execution,"worker-A",7,self.ledger.find)
        self.assertEqual(self.owner.reconcile(
            self.execution,"worker-B",8,self.ledger.find),"CONFIRMED_SUCCESS")
        self.assertEqual(self.journal.inspect(self.execution)["state"],"CONFIRMED_SUCCESS")
        with self.assertRaises(UnsafeDispatch):
            self.journal.dispatch(self.execution,"worker-B",8)
        self.assertEqual(len(self.ledger.find(self.execution)),1)
        events=self.db.snapshot(self.rid)["events"]
        self.assertEqual(sum(e["type"]=="tool.recovery.owner.transferred" for e in events),1)
        self.assertEqual(sum(e["type"]=="tool.receipt.confirmed" for e in events),1)

    def test_two_concurrent_claimers_only_one_epoch_winner(self):
        self._expire_original()
        def claim(who):
            try:
                return self.owner.takeover(self.execution,who,expected_epoch=7)
            except UnsafeDispatch:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            won=list(pool.map(claim,("worker-B","worker-C")))
        winners=[v for v in won if v]
        self.assertEqual(len(winners),1)
        self.assertEqual(winners[0].fencing_epoch,8)
        loser="worker-C" if winners[0].owner_id=="worker-B" else "worker-B"
        with self.assertRaises(UnsafeDispatch):
            self.owner.admit(self.execution,loser,8)
        self.assertEqual(self.owner.reconcile(
            self.execution,winners[0].owner_id,8,self.ledger.find),
            "CONFIRMED_SUCCESS")

    def test_b_cannot_assume_no_effect_and_lease_expiry_denies_recovery(self):
        self._expire_original()
        self.owner.takeover(self.execution,"worker-B",expected_epoch=7,
                            lease_seconds=30)
        with self.assertRaises(UnsafeDispatch):
            self.owner.reconcile(self.execution,"worker-B",8,lambda _:[])
        self.assertEqual(self.journal.inspect(self.execution)["state"],"UNKNOWN")
        with self.db.tx() as c:
            c.execute("UPDATE harness_tool_recovery_authority "
                      "SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))
        with self.assertRaises(UnsafeDispatch):
            self.owner.reconcile(self.execution,"worker-B",8,self.ledger.find)
        self.assertEqual(self.journal.inspect(self.execution)["state"],"UNKNOWN")

    def test_stale_plan_and_unconfirmed_dispatch_cannot_transfer(self):
        self._expire_original()
        with self.db.tx() as c:
            c.execute("UPDATE harness_run SET plan_version=2 WHERE id=%s",(self.rid,))
        with self.assertRaises(UnsafeDispatch):
            self.owner.takeover(self.execution,"worker-B",expected_epoch=7)

    def test_current_owner_is_mandatory_when_recovery_authority_exists(self):
        self._expire_original()
        self.owner.takeover(self.execution,"worker-B",expected_epoch=7)
        with self.assertRaises(UnsafeDispatch):
            self.journal.reconcile(self.execution,self.ledger.find)
        with self.assertRaises(UnsafeDispatch):
            self.journal.reconcile(self.execution,self.ledger.find,
                                   recovery_owner="worker-A",recovery_epoch=7)
        self.assertEqual(self.owner.reconcile(
            self.execution,"worker-B",8,self.ledger.find),"CONFIRMED_SUCCESS")


if __name__=="__main__":
    unittest.main()
