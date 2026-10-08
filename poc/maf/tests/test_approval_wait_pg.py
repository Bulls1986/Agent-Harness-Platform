"""A26 durable waiting contract on real PostgreSQL, without IAM imitation."""
import os
import sys
import unittest
from pathlib import Path

import psycopg

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from approval_wait import ApprovalConflict, ApprovalWaitStore
from task_ledger import TaskLedger
from workflow_probe import VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"),"requires real PostgreSQL CI")
class ApprovalWaitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_POSTGRES_DSN"]
        TaskLedger(cls.dsn).initialize()
        cls.store=ApprovalWaitStore(cls.dsn)

    def make_request(self):
        fact=VerificationFact.example(passed=False,evidence_ref=None)
        request=self.store.request(
            fact,requester_principal="user-initiator",
            approver_principal="user-authorized-approver",
            action_ref="tool:external-write",resource_ref="resource:demo",
            policy_ref="policy:poc-approval",
        )
        return fact,request

    def test_waiting_same_run_across_store_instances_and_approved_transition(self):
        fact,request=self.make_request()
        reloaded=ApprovalWaitStore(self.dsn).load_pending(fact.run_id)
        self.assertEqual(reloaded.approval_id,request.approval_id)
        self.assertEqual(reloaded.attempt_id,fact.attempt_id)
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM poc_executions WHERE attempt_id=%s",
                (fact.attempt_id,),
            ).fetchone()[0],0)  # Gate before dispatch: no Execution yet
            self.assertEqual(conn.execute(
                "SELECT state FROM poc_attempts WHERE attempt_id=%s",
                (fact.attempt_id,),
            ).fetchone()[0],"CREATED")
        with psycopg.connect(self.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    "UPDATE poc_approvals SET required_approver_principal_id='attacker' WHERE approval_id=%s",
                    (request.approval_id,),
                )
        with self.assertRaises(ApprovalConflict):
            self.store.decide(request.approval_id,authenticated_principal="wrong",authorized=True,decision="APPROVED")
        with self.assertRaises(ApprovalConflict):
            self.store.decide(request.approval_id,authenticated_principal="user-authorized-approver",authorized=False,decision="APPROVED")
        self.assertEqual(ApprovalWaitStore(self.dsn).decide(
            request.approval_id,authenticated_principal="user-authorized-approver",
            authorized=True,decision="APPROVED",
        ),"RUNNING")
        with self.assertRaises(KeyError):
            self.store.load_pending(fact.run_id)
        with self.assertRaises(ApprovalConflict):
            self.store.decide(request.approval_id,authenticated_principal="user-authorized-approver",authorized=True,decision="APPROVED")
        history=TaskLedger(self.dsn).read(fact.run_id)
        self.assertEqual(history["run"]["state"],"RUNNING")
        self.assertEqual([e["event_type"] for e in history["events"]],
                         ["approval.requested","approval.decided"])

    def test_rejection_is_terminal_and_no_execution_dispatched(self):
        fact,request=self.make_request()
        self.assertEqual(self.store.decide(
            request.approval_id,authenticated_principal="user-authorized-approver",
            authorized=True,decision="REJECTED",
        ),"FAILED")
        facts=TaskLedger(self.dsn).read(fact.run_id)
        self.assertEqual(facts["run"]["state"],"FAILED")
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM poc_executions WHERE attempt_id=%s",
                (fact.attempt_id,),
            ).fetchone()[0],0)
            with self.assertRaises(psycopg.Error):
                conn.execute("UPDATE poc_runs SET state='RUNNING' WHERE run_id=%s",
                             (fact.run_id,))

    def test_approval_history_is_immutable_after_decision(self):
        fact,request=self.make_request()
        self.store.decide(request.approval_id,authenticated_principal="user-authorized-approver",
                          authorized=True,decision="REJECTED")
        with psycopg.connect(self.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute("UPDATE poc_approvals SET state='APPROVED' WHERE approval_id=%s",
                             (request.approval_id,))


if __name__=="__main__":
    unittest.main()
