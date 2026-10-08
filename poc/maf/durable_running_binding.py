"""Harness-owned immutable RUNNING Execution -> native MAF Durable identity.

MSSQL owns native orchestration. This Adapter only pins identity/version and
checks an active task before native control actions. It does not lease a
Durable TaskHub or authorize Tool dispatch (ExecutionOwnership does that).
"""
from __future__ import annotations

from dataclasses import dataclass
import psycopg
from psycopg.rows import dict_row

from durable_approval_binding import DurableBindingMismatch


@dataclass(frozen=True)
class RunningNativeBinding:
    run_id: str
    step_id: str
    attempt_id: str
    execution_id: str
    native_instance_id: str
    native_workflow_name: str
    frozen_workflow_version: str
    frozen_runtime_version: str


class DurableRunningBindingStore:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("Platform PostgreSQL DSN is required")
        self.dsn = dsn

    def bind(self, binding: RunningNativeBinding) -> None:
        """Persist provider-reported instance identity with active task facts.

        Caller independently starts/validates the native instance using MAF's
        public API. An orphan may exist if native start succeeds and PG insert
        never commits: no cross-database transaction is implied.
        """
        if not all(vars(binding).values()):
            raise ValueError("All platform/native identity and versions required")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                            (binding.run_id,))
                row = cur.fetchone()
                if row is None or row[0] != "RUNNING":
                    raise DurableBindingMismatch("RUNNING Run identity required")
                # DB lineage trigger rejects unrelated Step/Attempt/Execution,
                # inactive work, and superseded Plans even under direct SQL.
                cur.execute(
                    """INSERT INTO poc_maf_durable_running_bindings
                       (execution_id,run_id,step_id,attempt_id,native_instance_id,
                        native_workflow_name,frozen_workflow_version,frozen_runtime_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (binding.execution_id,binding.run_id,binding.step_id,
                     binding.attempt_id,binding.native_instance_id,
                     binding.native_workflow_name,binding.frozen_workflow_version,
                     binding.frozen_runtime_version),
                )

    def require_running(self, expected: RunningNativeBinding) -> dict:
        """Fail closed before native control operations on an active Run.

        Never authorizes side-effect dispatch, lease takeover, or automatic
        replay; Tool execution requires a separate trusted ownership gate.
        """
        if not all(vars(expected).values()):
            raise ValueError("Complete native and platform identity required")
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                """SELECT b.execution_id,b.run_id,b.step_id,b.attempt_id,
                          b.native_instance_id,b.native_workflow_name,
                          b.frozen_workflow_version,b.frozen_runtime_version
                   FROM poc_maf_durable_running_bindings b
                   JOIN poc_executions e ON e.execution_id=b.execution_id
                   JOIN poc_attempts a ON a.attempt_id=b.attempt_id
                   JOIN poc_steps s ON s.step_id=b.step_id
                   JOIN poc_plans p ON p.plan_id=s.plan_id
                   JOIN poc_runs r ON r.run_id=b.run_id
                   WHERE b.execution_id=%s AND r.state='RUNNING'
                     AND e.state='RUNNING' AND a.state='RUNNING'
                     AND e.attempt_id=b.attempt_id AND a.step_id=b.step_id
                     AND p.run_id=b.run_id
                     AND p.version=(SELECT MAX(version) FROM poc_plans
                                     WHERE run_id=b.run_id)""",
                (expected.execution_id,),
            ).fetchone()
            if row is None:
                raise DurableBindingMismatch("No active RUNNING native binding")
            if tuple(row[key] for key in vars(expected)) != tuple(vars(expected).values()):
                raise DurableBindingMismatch("RUNNING Native Instance/Attempt/Version mismatch")
            return dict(row)
