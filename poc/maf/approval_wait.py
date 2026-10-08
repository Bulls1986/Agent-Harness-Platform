"""A26 platform Approval waiting facts: durable business wait, not MAF Checkpoint.

The API does not authenticate callers. `authenticated_principal` is input
from a future trusted IAM/Policy boundary and MUST NOT be passed through from
an untrusted request. The POC checks identity binding and lifecycle only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from task_ledger import _id
from workflow_probe import VerificationFact


class ApprovalConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    run_id: str
    step_id: str
    attempt_id: str
    state: str


class ApprovalWaitStore:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("PostgreSQL DSN required")
        self.dsn = dsn

    def request(
        self, fact: VerificationFact, *, requester_principal: str,
        approver_principal: str, action_ref: str, resource_ref: str, policy_ref: str,
        native_request_id: str | None = None,
        native_checkpoint_ref: str | None = None,
        native_workflow_name: str | None = None,
        durable_instance_id: str | None = None,
        durable_request_id: str | None = None,
        durable_workflow_name: str | None = None,
        frozen_workflow_version: str | None = None,
        frozen_runtime_version: str | None = None,
    ) -> ApprovalRequest:
        if fact.plan_version != 1 or not all((
            fact.run_id, fact.plan_id, fact.step_id, fact.attempt_id,
            requester_principal, approver_principal, action_ref, resource_ref, policy_ref
        )):
            raise ValueError("Missing approval and platform identity bindings")
        native_values = (native_request_id, native_checkpoint_ref, native_workflow_name)
        if any(value is not None for value in native_values) and not all(native_values):
            raise ValueError("Native HITL bindings must be supplied together")
        durable_values = (durable_instance_id, durable_request_id,
                          durable_workflow_name, frozen_workflow_version,
                          frozen_runtime_version)
        if any(value is not None for value in durable_values) and not all(durable_values):
            raise ValueError("Durable instance/request/workflow/version must be bound together")
        if any(durable_values) and any(native_values):
            raise ValueError("Do not mix FileCheckpoint and Durable Functions binding models")
        conversation_id, turn_id, approval_id = _id("conversation"), _id("turn"), _id("approval")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO poc_conversations(conversation_id) VALUES (%s)",(conversation_id,))
                cur.execute("INSERT INTO poc_turns(turn_id,conversation_id) VALUES (%s,%s)",(turn_id,conversation_id))
                cur.execute(
                    """INSERT INTO poc_runs
                       (run_id,turn_id,initiator_principal_id,runtime_type,recipe_version,state)
                       VALUES (%s,%s,%s,'maf','approval-demo-v1','WAITING_APPROVAL')""",
                    (fact.run_id,turn_id,requester_principal),
                )
                cur.execute(
                    "INSERT INTO poc_plans(plan_id,run_id,version,reason) VALUES (%s,%s,1,'initial')",
                    (fact.plan_id,fact.run_id),
                )
                cur.execute(
                    "INSERT INTO poc_steps(step_id,plan_id,ordinal,intent) VALUES (%s,%s,1,'Await approval before execution')",
                    (fact.step_id,fact.plan_id),
                )
                cur.execute(
                    "INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state) VALUES (%s,%s,1,'CREATED')",
                    (fact.attempt_id,fact.step_id),
                )
                cur.execute(
                    "INSERT INTO poc_runtime_bindings(run_id,runtime_type) VALUES (%s,'maf')",
                    (fact.run_id,),
                )
                cur.execute(
                    """INSERT INTO poc_approvals
                       (approval_id,run_id,step_id,attempt_id,action_ref,resource_ref,
                        policy_ref,requester_principal_id,required_approver_principal_id,state)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'PENDING')""",
                    (approval_id,fact.run_id,fact.step_id,fact.attempt_id,
                     action_ref,resource_ref,policy_ref,requester_principal,approver_principal),
                )
                if all(native_values):
                    cur.execute(
                        """INSERT INTO poc_maf_approval_bindings
                           (approval_id,run_id,native_request_id,native_checkpoint_ref,native_workflow_name)
                           VALUES (%s,%s,%s,%s,%s)""",
                        (approval_id,fact.run_id,*native_values),
                    )
                if all(durable_values):
                    cur.execute(
                        """INSERT INTO poc_maf_durable_approval_bindings
                           (approval_id,run_id,step_id,attempt_id,
                            native_instance_id,native_request_id,native_workflow_name,
                            frozen_workflow_version,frozen_runtime_version)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (approval_id,fact.run_id,fact.step_id,fact.attempt_id,
                         *durable_values),
                    )
                cur.execute(
                    """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                       VALUES (%s,%s,1,'approval.requested',%s::jsonb)""",
                    (_id("event"),fact.run_id,json.dumps({
                        "approval_id":approval_id,"step_id":fact.step_id,"action_ref":action_ref,
                    })),
                )
        return ApprovalRequest(approval_id,fact.run_id,fact.step_id,fact.attempt_id,"PENDING")

    def load_pending(self, run_id: str) -> ApprovalRequest:
        """Reload same WAITING_APPROVAL Run without restarting execution."""
        with psycopg.connect(self.dsn,row_factory=dict_row) as conn:
            row=conn.execute(
                """SELECT a.approval_id,a.run_id,a.step_id,a.attempt_id,a.state
                   FROM poc_approvals a JOIN poc_runs r ON r.run_id=a.run_id
                   WHERE a.run_id=%s AND a.state='PENDING' AND r.state='WAITING_APPROVAL'""",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            return ApprovalRequest(**row)

    def load_native_binding(self, run_id: str) -> dict:
        """Read trusted MAF request/checkpoint refs for the *pending* platform Approval."""
        with psycopg.connect(self.dsn,row_factory=dict_row) as conn:
            row=conn.execute(
                """SELECT b.approval_id,b.run_id,b.native_request_id,b.native_checkpoint_ref,
                          b.native_workflow_name
                   FROM poc_maf_approval_bindings b
                   JOIN poc_approvals a ON a.approval_id=b.approval_id
                   JOIN poc_runs r ON r.run_id=a.run_id
                   WHERE b.run_id=%s AND a.state='PENDING' AND r.state='WAITING_APPROVAL'""",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            return dict(row)

    def decide(self, approval_id: str, *, authenticated_principal: str,
               authorized: bool, decision: str) -> str:
        """Trusted Policy boundary provides authorized flag; no IAM implementation here."""
        if decision not in ("APPROVED","REJECTED") or not authenticated_principal:
            raise ValueError("Explicit decision and principal required")
        if not authorized:
            raise ApprovalConflict("External Policy did not authorize approval decision")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT run_id,state FROM poc_approvals WHERE approval_id=%s",(approval_id,))
                preliminary=cur.fetchone()
                if preliminary is None:
                    raise KeyError(approval_id)
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",(preliminary["run_id"],))
                run=cur.fetchone()
                cur.execute(
                    """SELECT required_approver_principal_id,state,run_id
                       FROM poc_approvals WHERE approval_id=%s FOR UPDATE""",(approval_id,),
                )
                request=cur.fetchone()
                if run is None or run["state"]!="WAITING_APPROVAL" or request["state"]!="PENDING":
                    raise ApprovalConflict("Approval is already decided or Run is not waiting")
                if request["required_approver_principal_id"]!=authenticated_principal:
                    raise ApprovalConflict("Wrong approving principal")
                cur.execute(
                    """UPDATE poc_approvals
                       SET state=%s,decided_by_principal_id=%s,decided_at=now()
                       WHERE approval_id=%s""",
                    (decision,authenticated_principal,approval_id),
                )
                target="RUNNING" if decision=="APPROVED" else "FAILED"
                cur.execute(
                    """UPDATE poc_runs SET state=%s,terminal_at=CASE
                       WHEN %s='FAILED' THEN now() ELSE NULL END WHERE run_id=%s""",
                    (target,target,request["run_id"]),
                )
                cur.execute(
                    """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                       VALUES (%s,%s,(SELECT COALESCE(MAX(seq),0)+1 FROM poc_events WHERE run_id=%s),
                               'approval.decided',%s::jsonb)""",
                    (_id("event"),request["run_id"],request["run_id"],
                     json.dumps({"approval_id":approval_id,"decision":decision,
                                 "principal_id":authenticated_principal})),
                )
                return target
