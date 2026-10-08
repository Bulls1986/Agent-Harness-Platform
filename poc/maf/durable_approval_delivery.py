"""Fail-closed response delivery adapter for native MSSQL Durable HITL.

Platform Approval and native HTTP response are not a distributed transaction.
A subsequent Worker must never blindly replay an unacknowledged response.
"""
from dataclasses import dataclass
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
from durable_approval_binding import DurableBindingMismatch


@dataclass(frozen=True)
class DurableDeliveryClaim:
    state: str
    token: str | None
    decision: str
    instance_id: str
    request_id: str


class DurableApprovalDelivery:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("Platform PostgreSQL DSN required")
        self.dsn = dsn

    def claim(self, run_id: str, *, attempt_id: str, native_instance_id: str,
              native_request_id: str, workflow_name: str,
              workflow_version: str, runtime_version: str) -> DurableDeliveryClaim:
        identity = (run_id, attempt_id, native_instance_id, native_request_id,
                    workflow_name, workflow_version, runtime_version)
        if not all(identity):
            raise ValueError("Complete frozen Run/Attempt/native/version required")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # Same Run lock as approval decision: serialize responders.
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (run_id,))
                run = cur.fetchone()
                if run is None:
                    raise DurableBindingMismatch("No platform Run for native request")
                cur.execute(
                    """SELECT b.approval_id,b.run_id,b.attempt_id,b.native_instance_id,
                              b.native_request_id,b.native_workflow_name,
                              b.frozen_workflow_version,b.frozen_runtime_version,
                              a.state AS decision
                       FROM poc_maf_durable_approval_bindings b
                       JOIN poc_approvals a ON a.approval_id=b.approval_id
                       JOIN poc_attempts t ON t.attempt_id=b.attempt_id
                       JOIN poc_steps s ON s.step_id=b.step_id
                       JOIN poc_plans p ON p.plan_id=s.plan_id
                       WHERE b.run_id=%s AND a.run_id=b.run_id
                         AND a.step_id=b.step_id AND a.attempt_id=b.attempt_id
                         AND t.step_id=b.step_id AND t.state='CREATED'
                         AND p.run_id=b.run_id AND a.state IN ('APPROVED','REJECTED')""",
                    (run_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise DurableBindingMismatch("No decided approval on bound Attempt")
                stored = (row["run_id"], row["attempt_id"], row["native_instance_id"],
                          row["native_request_id"], row["native_workflow_name"],
                          row["frozen_workflow_version"], row["frozen_runtime_version"])
                target = "RUNNING" if row["decision"] == "APPROVED" else "FAILED"
                if stored != identity or run["state"] != target:
                    raise DurableBindingMismatch("Frozen identity/version or Run state mismatch")
                cur.execute(
                    "SELECT delivery_token,state FROM poc_maf_hitl_deliveries "
                    "WHERE approval_id=%s FOR UPDATE", (row["approval_id"],),
                )
                delivery = cur.fetchone()
                if delivery is None:
                    token = "durable-delivery-" + uuid4().hex
                    cur.execute(
                        "INSERT INTO poc_maf_hitl_deliveries "
                        "(approval_id,delivery_token,state) VALUES (%s,%s,'IN_FLIGHT')",
                        (row["approval_id"], token),
                    )
                    state = "CLAIMED"
                elif delivery["state"] == "APPLIED":
                    token, state = None, "ALREADY_APPLIED"
                else:
                    if delivery["state"] == "IN_FLIGHT":
                        cur.execute(
                            "UPDATE poc_maf_hitl_deliveries SET state='UNKNOWN' "
                            "WHERE approval_id=%s", (row["approval_id"],),
                        )
                    token, state = None, "UNKNOWN_REQUIRES_RECONCILIATION"
                return DurableDeliveryClaim(state, token, row["decision"],
                                            row["native_instance_id"], row["native_request_id"])

    def complete(self, run_id: str, *, token: str,
                 native_status: str, output_kind: str) -> None:
        """Only observed native terminal output can ACK delivery."""
        if not run_id or not token or native_status != "Completed":
            raise DurableBindingMismatch("Native Completed evidence and token required")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (run_id,))
                if cur.fetchone() is None:
                    raise DurableBindingMismatch("Unknown platform Run")
                cur.execute(
                    """SELECT a.state AS decision,d.state,d.delivery_token
                       FROM poc_maf_hitl_deliveries d
                       JOIN poc_approvals a ON a.approval_id=d.approval_id
                       JOIN poc_maf_durable_approval_bindings b ON b.approval_id=a.approval_id
                       WHERE b.run_id=%s FOR UPDATE OF d""", (run_id,),
                )
                row = cur.fetchone()
                if row is None or row["state"] != "IN_FLIGHT" or row["delivery_token"] != token:
                    raise DurableBindingMismatch("Stale or uncertain response delivery")
                expected = ("SIMULATED_EXECUTION" if row["decision"] == "APPROVED"
                            else "DENIED_NO_EXECUTION")
                if output_kind != expected:
                    raise DurableBindingMismatch("Native result contradicts approval")
                cur.execute(
                    "UPDATE poc_maf_hitl_deliveries "
                    "SET state='APPLIED',output_kind=%s,completed_at=now() "
                    "WHERE delivery_token=%s", (output_kind, token),
                )
