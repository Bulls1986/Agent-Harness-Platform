"""A29 real PostgreSQL cancellation/timeout semantics, no fake terminal ACK."""
import os
import sys
import unittest
from pathlib import Path

import psycopg

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from approval_wait import ApprovalWaitStore
from execution_control import ControlConflict, ExecutionControl
from execution_ownership import ExecutionOwnership, StaleExecutionOwner
from task_ledger import TaskLedger
from workflow_probe import VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"),"dedicated PostgreSQL CI")
class ExecutionControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_POSTGRES_DSN"]
        cls.ledger=TaskLedger(cls.dsn)
        cls.ledger.initialize()
        cls.control=ExecutionControl(cls.dsn)
        cls.owners=ExecutionOwnership(cls.dsn)

    def setup_execution(self, side_effect="PURE", *, dispatch=False):
        fact=VerificationFact.example(passed=False,evidence_ref=None)
        execution_id=self.ledger.start(fact)
        if side_effect!="PURE":
            with psycopg.connect(self.dsn) as conn:
                conn.execute(
                    "UPDATE poc_executions SET side_effect_class=%s WHERE execution_id=%s",
                    (side_effect,execution_id),
                )
        owner=self.owners.claim(execution_id,owner_id="worker-fixture")
        if dispatch:
            self.owners.dispatch(owner)
        return fact,execution_id,owner

    def test_cancel_waiting_approval_with_no_execution_keeps_history(self):
        fact=VerificationFact.example(passed=False,evidence_ref=None)
        request=ApprovalWaitStore(self.dsn).request(
            fact,requester_principal="initiator",approver_principal="approver",
            action_ref="tool:write",resource_ref="resource:test",policy_ref="policy:test",
        )
        result=self.control.request_cancel(fact.run_id,initiator="initiator")
        self.assertEqual((result.run_state,result.resolution),("CANCELLED","WAITING_CANCELLED"))
        read=self.ledger.read(fact.run_id)
        self.assertEqual(read["run"]["state"],"CANCELLED")
        self.assertEqual(read["attempts"][0]["state"],"CREATED")
        self.assertEqual(read["events"][-1]["event_type"],"run.cancelled_waiting")
        with psycopg.connect(self.dsn) as conn:
            row=conn.execute(
                "SELECT state FROM poc_approvals WHERE approval_id=%s",
                (request.approval_id,),
            ).fetchone()
            self.assertEqual(row[0],"CANCELLED")
        with self.assertRaises(KeyError):
            ApprovalWaitStore(self.dsn).load_pending(fact.run_id)
        with self.assertRaises(ControlConflict):
            self.control.request_cancel(fact.run_id)
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM poc_executions WHERE attempt_id=%s",
                (fact.attempt_id,),
            ).fetchone()[0],0)

    def test_acknowledgement_is_not_termination_or_permission_to_dispatch(self):
        fact,eid,owner=self.setup_execution()
        self.assertEqual(self.control.request_cancel(fact.run_id).run_state,"CANCELLING")
        self.assertEqual(self.control.request_cancel(fact.run_id).resolution,"ALREADY_REQUESTED")
        ack=self.control.accept_cancel_result(fact.run_id,adapter_result="ACKNOWLEDGED")
        self.assertEqual(ack.run_state,"CANCELLING")
        self.assertEqual(self.ledger.read(fact.run_id)["attempts"][0]["state"],"RUNNING")
        with self.assertRaises(StaleExecutionOwner):
            self.owners.dispatch(owner)
        with self.assertRaises(StaleExecutionOwner):
            self.owners.heartbeat(owner)
        ended=self.control.accept_cancel_result(fact.run_id,adapter_result="TERMINATED")
        self.assertEqual(ended.run_state,"CANCELLED")
        self.assertEqual(self.ledger.read(fact.run_id)["attempts"][0]["state"],"CANCELLED")
        with self.assertRaises(ControlConflict):
            self.control.accept_cancel_result(fact.run_id,adapter_result="TERMINATED")

    def test_nonpure_after_dispatch_cancel_terminated_still_unknown(self):
        fact,eid,owner=self.setup_execution("NON_RETRYABLE",dispatch=True)
        self.control.request_cancel(fact.run_id)
        result=self.control.accept_cancel_result(fact.run_id,adapter_result="TERMINATED")
        self.assertEqual((result.run_state,result.resolution),("CANCELLING","RECONCILIATION"))
        self.assertEqual(self.ledger.read(fact.run_id)["attempts"][0]["state"],"UNKNOWN")
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT state,failure_type FROM poc_reconciliations WHERE execution_id=%s",(eid,),
            ).fetchone(),("PENDING","UNKNOWN_OUTCOME"))
        with self.assertRaises(StaleExecutionOwner):
            self.owners.dispatch(owner)

    def test_nonpure_timeout_after_dispatch_is_not_cancelled(self):
        fact,eid,owner=self.setup_execution("NON_RETRYABLE",dispatch=True)
        result=self.control.record_timeout(fact.run_id)
        self.assertEqual((result.run_state,result.resolution,result.failure_type),
                         ("RUNNING","RECONCILIATION","TIMEOUT_AFTER_DISPATCH"))
        details=self.ledger.read(fact.run_id)
        self.assertEqual(details["attempts"][0]["state"],"UNKNOWN")
        self.assertEqual(details["attempts"][0]["failure_type"],"TIMEOUT_AFTER_DISPATCH")
        self.assertEqual(details["events"][-1]["event_type"],"execution.unknown")
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT failure_type FROM poc_reconciliations WHERE execution_id=%s",(eid,),
            ).fetchone()[0],"TIMEOUT_AFTER_DISPATCH")

    def test_predispatch_timeout_is_known_failure_not_unknown(self):
        fact,eid,owner=self.setup_execution("NON_RETRYABLE",dispatch=False)
        result=self.control.record_timeout(fact.run_id)
        self.assertEqual((result.run_state,result.failure_type),("FAILED","TIMEOUT"))
        self.assertEqual(self.ledger.read(fact.run_id)["attempts"][0]["state"],"FAILED")
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM poc_reconciliations WHERE execution_id=%s",(eid,),
            ).fetchone()[0],0)

    def test_dispatched_pure_timeout_requires_termination_proof(self):
        fact,eid,owner=self.setup_execution("PURE",dispatch=True)
        result=self.control.record_timeout(fact.run_id)
        self.assertEqual((result.run_state,result.resolution),("RUNNING","TERMINATION_REQUIRED"))
        self.assertEqual(self.ledger.read(fact.run_id)["attempts"][0]["state"],"RUNNING")
        self.assertEqual(self.ledger.read(fact.run_id)["events"][-1]["event_type"],
                         "execution.timeout_signal")


if __name__=="__main__":
    unittest.main()
