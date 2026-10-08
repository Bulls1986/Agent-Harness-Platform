"""A29 real PostgreSQL owner/fencing and recovery tests."""
import os
import sys
import unittest
from pathlib import Path

import psycopg

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from execution_ownership import ExecutionOwnership, Ownership, StaleExecutionOwner
from recovery_boundary import RecoveryCoordinator
from task_ledger import TaskLedger, TaskFactConflict
from workflow_probe import VerificationFact
from document_workflow import run_document_case


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"),"dedicated real PostgreSQL CI")
class ExecutionOwnershipTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_POSTGRES_DSN"]
        cls.ledger=TaskLedger(cls.dsn)
        cls.ledger.initialize()
        cls.owners=ExecutionOwnership(cls.dsn)
        cls.recovery=RecoveryCoordinator(cls.dsn)

    def initial(self):
        fact=VerificationFact.example(passed=False,evidence_ref=None)
        execution_id=self.ledger.start(fact)
        return fact,execution_id

    def expire(self, execution_id):
        # Trusted fault injection; no real wall-clock waiting.
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "UPDATE poc_execution_ownership SET lease_expires_at=now()-interval '1 second' WHERE execution_id=%s",
                (execution_id,),
            )

    async def test_claim_renew_dispatch_and_fenced_finalize(self):
        fact, eid=self.initial()
        o=self.owners.claim(eid,owner_id="worker-A",ttl_seconds=30)
        self.assertEqual(o.fencing_token,1)
        self.owners.heartbeat(o,ttl_seconds=20)
        self.owners.dispatch(o)
        with self.assertRaises(StaleExecutionOwner):
            self.owners.dispatch(o)
        with self.assertRaises(StaleExecutionOwner):
            self.owners.claim(eid,owner_id="worker-B")
        outcome=await run_document_case("expected",fact)
        with self.assertRaises(StaleExecutionOwner):
            self.ledger.finish(fact,outcome,eid)
        with self.assertRaises(StaleExecutionOwner):
            self.ledger.finish(fact,outcome,eid,owner_id="worker-B",fencing_token=1)
        self.ledger.finish(fact,outcome,eid,owner_id=o.owner_id,fencing_token=o.fencing_token)
        self.assertEqual(self.ledger.read(fact.run_id)["run"]["state"],"COMPLETED")
        with self.assertRaises(StaleExecutionOwner):
            self.owners.heartbeat(o)

    async def test_live_owner_cannot_be_overridden_or_recovered(self):
        fact,eid=self.initial()
        o=self.owners.claim(eid,owner_id="worker-A")
        self.assertEqual(
            self.recovery.recover(fact.run_id,interrupted_attempt_id=fact.attempt_id).outcome,
            "OWNER_STILL_ACTIVE",
        )
        self.assertEqual(self.ledger.read(fact.run_id)["attempts"][0]["state"],"RUNNING")
        with self.assertRaises(StaleExecutionOwner):
            self.owners.claim(eid,owner_id="worker-B")

    async def test_expired_pure_owner_fenced_old_result_new_attempt(self):
        fact,eid=self.initial()
        o=self.owners.claim(eid,owner_id="worker-A")
        self.expire(eid)
        with self.assertRaises(StaleExecutionOwner):
            self.owners.heartbeat(o)
        with self.assertRaises(StaleExecutionOwner):
            self.owners.claim(eid,owner_id="worker-B")
        old_outcome=await run_document_case("expected",fact)
        with self.assertRaises(StaleExecutionOwner):
            self.ledger.finish(fact,old_outcome,eid,owner_id="worker-A",fencing_token=1)
        decision=self.recovery.recover(fact.run_id,interrupted_attempt_id=fact.attempt_id)
        self.assertEqual(decision.outcome,"STEP_BOUNDARY_RETRY")
        with psycopg.connect(self.dsn) as conn:
            row=conn.execute(
                "SELECT fencing_token,owner_id,revoked_at IS NOT NULL FROM poc_execution_ownership WHERE execution_id=%s",
                (eid,),
            ).fetchone()
            self.assertEqual(row,(2,None,True))
        with self.assertRaises(StaleExecutionOwner):
            self.owners.dispatch(o)
        next_owner=self.owners.claim(decision.execution_id,owner_id="worker-B")
        new_outcome=await run_document_case("expected",decision.fact)
        self.ledger.finish(decision.fact,new_outcome,decision.execution_id,
                           owner_id=next_owner.owner_id,fencing_token=next_owner.fencing_token)
        self.assertEqual(
            [x["state"] for x in self.ledger.read(fact.run_id)["attempts"]],
            ["FAILED","SUCCEEDED"],
        )

    async def test_expired_nonpure_dispatch_unknown_no_handoff(self):
        fact,eid=self.initial()
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "UPDATE poc_executions SET side_effect_class='NON_RETRYABLE' WHERE execution_id=%s",
                (eid,),
            )
        o=self.owners.claim(eid,owner_id="worker-A")
        self.owners.dispatch(o)
        self.expire(eid)
        decision=self.recovery.recover(fact.run_id,interrupted_attempt_id=fact.attempt_id)
        self.assertEqual(decision.outcome,"RECONCILIATION")
        with psycopg.connect(self.dsn) as conn:
            row=conn.execute(
                "SELECT state FROM poc_reconciliations WHERE execution_id=%s",
                (eid,),
            ).fetchone()
            self.assertEqual(row[0],"PENDING")
        self.assertEqual(
            [x["state"] for x in self.ledger.read(fact.run_id)["attempts"]],
            ["UNKNOWN"],
        )
        with self.assertRaises(StaleExecutionOwner):
            self.owners.dispatch(o)
        with self.assertRaises(StaleExecutionOwner):
            self.owners.claim(eid,owner_id="worker-B")


if __name__=="__main__":
    unittest.main()
