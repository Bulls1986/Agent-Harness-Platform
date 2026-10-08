"""Harness-owned immutable linkage to official MAF Durable Functions.

This is ONLY the WAITING_APPROVAL/Attempt identity and pinned workflow gate.
Durable state remains in Microsoft MSSQL Provider; this POC must not claim
in-flight execution Same Attempt Resume or re-submit external effects.
"""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row


class DurableBindingMismatch(RuntimeError):
    pass


class DurableApprovalBindingStore:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("A platform PostgreSQL DSN is required")
        self.dsn = dsn

    def require_waiting_resume(
        self, run_id: str, *, attempt_id: str, native_instance_id: str,
        native_request_id: str, workflow_name: str,
        workflow_version: str, runtime_version: str,
    ) -> dict:
        """Fail closed before resuming MAF response on a new Worker.

        Caller must independently read the *native pending request* via the
        official AgentFunctionApp HTTP API; passing IDs is no authorization.
        This does not substitute the enterprise IAM/Policy boundary.
        """
        requested = (run_id,attempt_id,native_instance_id,native_request_id,
                     workflow_name,workflow_version,runtime_version)
        if not all(requested):
            raise ValueError("Complete frozen Run/Attempt/Instance/Request/version required")
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                """SELECT b.run_id,b.step_id,b.attempt_id,b.approval_id,
                          b.native_instance_id,b.native_request_id,
                          b.native_workflow_name,b.frozen_workflow_version,
                          b.frozen_runtime_version
                   FROM poc_maf_durable_approval_bindings b
                   JOIN poc_approvals a ON a.approval_id=b.approval_id
                   JOIN poc_runs r ON r.run_id=b.run_id
                   JOIN poc_attempts t ON t.attempt_id=b.attempt_id
                   JOIN poc_steps s ON s.step_id=b.step_id
                   JOIN poc_plans p ON p.plan_id=s.plan_id
                   WHERE b.run_id=%s AND a.state='PENDING'
                     AND r.state='WAITING_APPROVAL'
                     AND t.state='CREATED' AND t.step_id=b.step_id
                     AND a.run_id=b.run_id AND a.step_id=b.step_id
                     AND a.attempt_id=b.attempt_id AND p.run_id=b.run_id
                """, (run_id,),
            ).fetchone()
            if row is None:
                raise DurableBindingMismatch("No active platform/native approval binding")
            actual = (
                row["run_id"],row["attempt_id"],row["native_instance_id"],
                row["native_request_id"],row["native_workflow_name"],
                row["frozen_workflow_version"],row["frozen_runtime_version"],
            )
            if actual != requested:
                raise DurableBindingMismatch("Native instance/Attempt/frozen runtime version mismatch")
            return dict(row)

    def load_attempt_history(self, run_id: str) -> list[dict]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            return conn.execute(
                """SELECT t.attempt_id,t.ordinal,t.state,p.version
                   FROM poc_attempts t
                   JOIN poc_steps s ON s.step_id=t.step_id
                   JOIN poc_plans p ON p.plan_id=s.plan_id
                   WHERE p.run_id=%s ORDER BY p.version,t.ordinal""",
                (run_id,),
            ).fetchall()
