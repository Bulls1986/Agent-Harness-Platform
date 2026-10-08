"""A34 P1 crash gaps: real PG intent, immutable binding and native response reconciliation.

Native responses are read-only OBSERVATIONS supplied by trusted adapter in
these tests. Live native HTTP/SIGKILL integration is separate.
"""
import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from approval_wait import ApprovalWaitStore
from durable_approval_binding import DurableBindingMismatch
from durable_approval_delivery import DurableApprovalDelivery
from durable_launch_intent import DurableLaunchIntentStore, NativeLaunchIntent
from durable_running_binding import DurableRunningBindingStore, RunningNativeBinding
from task_ledger import TaskLedger
from workflow_probe import VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"), "real PG required")
class NativeStartGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_POSTGRES_DSN"]
        cls.ledger=TaskLedger(cls.dsn)
        cls.ledger.initialize()
        cls.intents=DurableLaunchIntentStore(cls.dsn)

    def fixture(self):
        fact=VerificationFact.example(passed=False,evidence_ref=None)
        execution_id=self.ledger.start(fact)
        native=RunningNativeBinding(
            run_id=fact.run_id,step_id=fact.step_id,attempt_id=fact.attempt_id,
            execution_id=execution_id,native_instance_id="native-"+uuid4().hex,
            native_workflow_name="maf_mssql_poc_guarded",
            frozen_workflow_version="poc-v1",frozen_runtime_version="sdk-v1")
        intent=NativeLaunchIntent(
            run_id=native.run_id,step_id=native.step_id,
            attempt_id=native.attempt_id,execution_id=native.execution_id,
            native_workflow_name=native.native_workflow_name,
            frozen_workflow_version=native.frozen_workflow_version,
            frozen_runtime_version=native.frozen_runtime_version)
        return fact,native,intent

    def test_native_created_then_binding_missing_is_quarantined_without_relaunch(self):
        fact,native,intent=self.fixture()
        self.intents.prepare(intent)  # durable before /run
        self.assertEqual(self.intents.inspect(intent).state,
                         "UNBOUND_NATIVE_MUST_RECONCILE")
        with self.assertRaises(DurableBindingMismatch):
            self.intents.prepare(intent)  # repeat /run forbidden
        result=self.intents.quarantine_unbound(intent)
        self.assertEqual(result.state,"RECONCILIATION_PENDING")
        self.assertEqual(self.intents.quarantine_unbound(native).state,
                         "RECONCILIATION_PENDING")
        with psycopg.connect(self.dsn) as conn:
            row=conn.execute(
                """SELECT a.state,e.state,rc.state,rc.failure_type
                   FROM poc_attempts a
                   JOIN poc_executions e ON e.attempt_id=a.attempt_id
                   JOIN poc_reconciliations rc ON rc.execution_id=e.execution_id
                   WHERE a.attempt_id=%s""",(fact.attempt_id,)
            ).fetchone()
        self.assertEqual(row,("UNKNOWN","UNKNOWN","PENDING","NATIVE_START_UNCERTAIN"))
        self.assertEqual(len(self.ledger.read(fact.run_id)["attempts"]),1)
        # DB lineage trigger rejects binding to quarantined Execution.
        with self.assertRaises(psycopg.Error):
            DurableRunningBindingStore(self.dsn).bind(native)

    def test_normal_prepared_then_bound_is_read_only_and_immutable(self):
        _,native,intent=self.fixture()
        self.intents.prepare(intent)
        DurableRunningBindingStore(self.dsn).bind(native)
        self.assertEqual(self.intents.inspect(native).state,"BOUND")
        self.assertEqual(self.intents.inspect(intent).state,
                         "BOUND_REQUIRES_NATIVE_VERIFICATION")
        with self.assertRaises(DurableBindingMismatch):
            self.intents.quarantine_unbound(native)
        with self.assertRaises(DurableBindingMismatch):
            self.intents.inspect(replace(native,native_instance_id="wrong"))
        with psycopg.connect(self.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute("DELETE FROM poc_maf_durable_launch_intents WHERE execution_id=%s",
                             (native.execution_id,))

    def test_missing_or_mismatched_intent_rejected(self):
        _,native,intent=self.fixture()
        with self.assertRaises(DurableBindingMismatch):
            self.intents.inspect(native)
        self.intents.prepare(intent)
        for field in ("run_id","step_id","attempt_id","native_workflow_name",
                      "frozen_workflow_version","frozen_runtime_version"):
            with self.subTest(field=field):
                with self.assertRaises(DurableBindingMismatch):
                    self.intents.inspect(replace(native,**{field:"forged"}))

    def test_direct_sql_forged_lineage_is_rejected(self):
        _,native,intent=self.fixture()
        _,other,_=self.fixture()
        with psycopg.connect(self.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    """INSERT INTO poc_maf_durable_launch_intents
                       (execution_id,run_id,step_id,attempt_id,
                        native_workflow_name,frozen_workflow_version,frozen_runtime_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (native.execution_id,native.run_id,other.step_id,other.attempt_id,
                     intent.native_workflow_name,intent.frozen_workflow_version,
                     intent.frozen_runtime_version),
                )
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM poc_maf_durable_launch_intents WHERE execution_id=%s",
                (native.execution_id,)).fetchone()[0],0)


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"), "real PG required")
class NativeResponseGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_POSTGRES_DSN"]
        TaskLedger(cls.dsn).initialize()
        cls.deliveries=DurableApprovalDelivery(cls.dsn)
        cls.approvals=ApprovalWaitStore(cls.dsn)

    def fixture(self,decision="APPROVED"):
        fact=VerificationFact.example(passed=False,evidence_ref=None)
        ids=dict(native_instance_id="native-"+uuid4().hex,
                 native_request_id="request-"+uuid4().hex,
                 workflow_name="maf_mssql_poc_hitl",
                 workflow_version="fixture-v1",runtime_version="sdk-v1")
        approval=self.approvals.request(
            fact,requester_principal="initiator",approver_principal="approver",
            action_ref="tool:poc",resource_ref="resource:poc",policy_ref="policy:poc",
            durable_instance_id=ids["native_instance_id"],
            durable_request_id=ids["native_request_id"],
            durable_workflow_name=ids["workflow_name"],
            frozen_workflow_version=ids["workflow_version"],
            frozen_runtime_version=ids["runtime_version"])
        self.approvals.decide(
            approval.approval_id,authenticated_principal="approver",
            authorized=True,decision=decision)
        return fact,dict(attempt_id=fact.attempt_id,**ids)

    def observe(self,fact,ids,**changes):
        return self.deliveries.reconcile_observation(
            fact.run_id,**{**ids,"native_status":"Completed",
                           "output_kind":"SIMULATED_EXECUTION",**changes})

    def test_http_sent_result_unknown_then_native_completed_confirms_without_redispatch(self):
        fact,ids=self.fixture()
        claim=self.deliveries.claim(fact.run_id,**ids)
        self.assertEqual(claim.state,"CLAIMED")
        self.assertEqual(self.deliveries.claim(fact.run_id,**ids).state,
                         "UNKNOWN_REQUIRES_RECONCILIATION")
        self.assertEqual(self.observe(fact,ids),"APPLIED_FROM_NATIVE_EVIDENCE")
        self.assertEqual(self.observe(fact,ids),"ALREADY_APPLIED")
        self.assertEqual(self.deliveries.claim(fact.run_id,**ids).state,"ALREADY_APPLIED")
        with psycopg.connect(self.dsn) as conn:
            row=conn.execute(
                """SELECT d.state,d.output_kind
                   FROM poc_maf_hitl_deliveries d
                   JOIN poc_maf_durable_approval_bindings b
                     ON b.approval_id=d.approval_id WHERE b.run_id=%s""",
                (fact.run_id,)).fetchone()
        self.assertEqual(row,("APPLIED","SIMULATED_EXECUTION"))

    def test_pending_failed_or_contradictory_native_evidence_remains_unknown(self):
        for state,output in (("Running",None),("Pending",None),("Failed",None),
                             ("Completed","DENIED_NO_EXECUTION")):
            with self.subTest(status=state):
                fact,ids=self.fixture()
                self.deliveries.claim(fact.run_id,**ids)
                self.assertEqual(
                    self.observe(fact,ids,native_status=state,output_kind=output),
                    "UNKNOWN_REQUIRES_RECONCILIATION")
                self.assertEqual(self.deliveries.claim(fact.run_id,**ids).state,
                                 "UNKNOWN_REQUIRES_RECONCILIATION")

    def test_invalid_native_identity_cannot_confirm_unknown_response(self):
        fact,ids=self.fixture()
        self.deliveries.claim(fact.run_id,**ids)
        for change in (
            {"native_instance_id":"other"},{"native_request_id":"other"},
            {"workflow_version":"other"},{"runtime_version":"other"},
            {"attempt_id":"other"}):
            with self.subTest(change=change):
                with self.assertRaises(DurableBindingMismatch):
                    self.observe(fact,ids,**change)
        self.assertEqual(self.observe(fact,ids,native_status="Failed",
                                      output_kind=None),"UNKNOWN_REQUIRES_RECONCILIATION")

    def test_native_rejected_response_completion_is_confirmed_only_as_denied(self):
        fact,ids=self.fixture("REJECTED")
        self.deliveries.claim(fact.run_id,**ids)
        self.assertEqual(self.observe(fact,ids,native_status="Completed",
                                      output_kind="SIMULATED_EXECUTION"),
                         "UNKNOWN_REQUIRES_RECONCILIATION")
        self.assertEqual(self.observe(fact,ids,native_status="Completed",
                                      output_kind="DENIED_NO_EXECUTION"),
                         "APPLIED_FROM_NATIVE_EVIDENCE")
