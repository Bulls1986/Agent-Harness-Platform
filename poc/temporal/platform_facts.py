"""C06/C07: Harness-owned PG facts and native Temporal Workflow binding.

IMPORTANT: This POC purposely does not implement a second Durable scheduler.
Temporal owns Workflow History/Retry; PG owns Run/Step/Attempt/Execution facts,
frozen binding and non-idempotent Tool Admission. No cross-DB atomicity claim.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

import sys
MAF_POC=Path(__file__).resolve().parents[1] / "maf"
if str(MAF_POC) not in sys.path:
    sys.path.insert(0,str(MAF_POC))
from execution_ownership import ExecutionOwnership, StaleExecutionOwner


class FrozenTemporalMismatch(RuntimeError):
    pass


@dataclass(frozen=True)
class FrozenTemporal:
    run_id: str
    plan_id: str
    step_id: str
    attempt_id: str
    execution_id: str
    native_workflow_id: str
    frozen_workflow_version: str = "temporal-c06-nonretryable-v1"
    frozen_runtime_version: str = "temporalio-1.34.0"


def _uid(prefix: str) -> str:
    return prefix + "-" + uuid4().hex


class TemporalTaskFacts:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("Harness PostgreSQL DSN required")
        self.dsn=dsn
        self.owner=ExecutionOwnership(dsn)

    def initialize(self) -> None:
        """Only POC Task Facts shared schema + this Temporal-specific binding."""
        root=MAF_POC / "sql"
        with psycopg.connect(self.dsn) as conn:
            for filename in ("001_task_facts.sql","002_runtime_recovery.sql",
                             "003_approval_wait.sql",
                             "005_hitl_delivery_and_execution_fencing.sql"):
                conn.execute((root/filename).read_text(encoding="utf-8"))
            conn.execute((Path(__file__).resolve().parent/"sql"/
                          "001_temporal_binding.sql").read_text(encoding="utf-8"))

    def prepare(self, binding: FrozenTemporal) -> None:
        """Commit platform task + immutable native ID BEFORE start_workflow.

        A later start failure may leave an orphan PG Run/Binding; never infer
        that retrying start_workflow is safe. C06/C07 does not solve start
        ACK uncertainty; that remains a separate future fault window.
        """
        if not all(vars(binding).values()):
            raise ValueError("Complete platform + frozen native identity required")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                conversation,turn=_uid("conversation"),_uid("turn")
                cur.execute("INSERT INTO poc_conversations(conversation_id) VALUES (%s)",
                            (conversation,))
                cur.execute("INSERT INTO poc_turns(turn_id,conversation_id) VALUES (%s,%s)",
                            (turn,conversation))
                cur.execute(
                    """INSERT INTO poc_runs(run_id,turn_id,initiator_principal_id,
                        runtime_type,recipe_version,state)
                       VALUES (%s,%s,'poc-c-internal','temporal','guarded-tool-v1','RUNNING')""",
                    (binding.run_id,turn))
                cur.execute("INSERT INTO poc_plans(plan_id,run_id,version,reason) "
                            "VALUES (%s,%s,1,'nonretryable activity recovery')",
                            (binding.plan_id,binding.run_id))
                cur.execute("INSERT INTO poc_steps(step_id,plan_id,ordinal,intent) "
                            "VALUES (%s,%s,1,'single controlled tool dispatch')",
                            (binding.step_id,binding.plan_id))
                cur.execute("INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state) "
                            "VALUES (%s,%s,1,'RUNNING')",
                            (binding.attempt_id,binding.step_id))
                cur.execute(
                    """INSERT INTO poc_executions(execution_id,attempt_id,side_effect_class,state)
                       VALUES (%s,%s,'NON_RETRYABLE','RUNNING')""",
                    (binding.execution_id,binding.attempt_id))
                cur.execute(
                    "INSERT INTO poc_runtime_bindings(run_id,runtime_type) VALUES (%s,'temporal')",
                    (binding.run_id,))
                cur.execute(
                    """INSERT INTO poc_c_temporal_bindings
                       (execution_id,run_id,step_id,attempt_id,native_workflow_id,
                        frozen_workflow_version,frozen_runtime_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (binding.execution_id,binding.run_id,binding.step_id,
                     binding.attempt_id,binding.native_workflow_id,
                     binding.frozen_workflow_version,binding.frozen_runtime_version))
                cur.execute(
                    """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                       VALUES (%s,%s,1,'run.started',%s::jsonb)""",
                    (_uid("event"),binding.run_id,json.dumps({
                        "step_id":binding.step_id,"attempt_id":binding.attempt_id,
                        "execution_id":binding.execution_id,
                        "native_workflow_id":binding.native_workflow_id})))

    def require_frozen(self, binding: FrozenTemporal) -> None:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row=conn.execute(
                """SELECT b.*,p.plan_id AS frozen_plan_id,
                          e.state AS execution_state,a.state AS attempt_state,
                          r.state AS run_state
                   FROM poc_c_temporal_bindings b
                   JOIN poc_executions e ON e.execution_id=b.execution_id
                   JOIN poc_attempts a ON a.attempt_id=b.attempt_id
                   JOIN poc_steps s ON s.step_id=b.step_id
                   JOIN poc_plans p ON p.plan_id=s.plan_id
                   JOIN poc_runs r ON r.run_id=b.run_id
                   WHERE b.execution_id=%s AND e.attempt_id=b.attempt_id
                     AND a.step_id=b.step_id AND p.run_id=b.run_id
                     AND p.version=(SELECT max(version) FROM poc_plans
                                    WHERE run_id=b.run_id)""",
                (binding.execution_id,)).fetchone()
            fields=("run_id","step_id","attempt_id","execution_id",
                    "native_workflow_id","frozen_workflow_version",
                    "frozen_runtime_version")
            if not row or any(row[k]!=getattr(binding,k) for k in fields):
                raise FrozenTemporalMismatch("TEMPORAL_FROZEN_BINDING_MISMATCH")
            if row["run_state"]!="RUNNING" or row["attempt_state"]!="RUNNING" or row["execution_state"]!="RUNNING":
                raise FrozenTemporalMismatch("Platform Attempt/Execution no longer dispatchable")
            if row["frozen_plan_id"] != binding.plan_id:
                raise FrozenTemporalMismatch("Plan identity mismatch")

    def admit(self, binding: FrozenTemporal, *, worker_id: str) -> None:
        """First dispatch only. Native Temporal may retry the Activity afterward."""
        self.require_frozen(binding)
        ownership=self.owner.claim(binding.execution_id,owner_id=worker_id,ttl_seconds=3)
        self.owner.dispatch(ownership)

    def quarantine_after_dispatch(self, binding: FrozenTemporal) -> str:
        """When retry appears after a crashed, expired, dispatched owner."""
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                            (binding.run_id,))
                run=cur.fetchone()
                if not run or run["state"]!="RUNNING":
                    raise FrozenTemporalMismatch("Run inactive")
                cur.execute(
                    """SELECT b.run_id,b.native_workflow_id,b.frozen_workflow_version,
                              b.frozen_runtime_version,b.step_id,b.attempt_id,
                              p.plan_id AS frozen_plan_id,
                              a.state AS astate,e.state AS estate,
                              o.dispatched_at,o.lease_expires_at,o.owner_id,
                              o.fencing_token,o.revoked_at,
                              o.lease_expires_at > now() AS owner_live
                       FROM poc_c_temporal_bindings b
                       JOIN poc_executions e ON e.execution_id=b.execution_id
                       JOIN poc_attempts a ON a.attempt_id=b.attempt_id
                       JOIN poc_execution_ownership o ON o.execution_id=b.execution_id
                       JOIN poc_steps s ON s.step_id=b.step_id
                       JOIN poc_plans p ON p.plan_id=s.plan_id
                       WHERE b.execution_id=%s
                         AND p.version=(SELECT max(version) FROM poc_plans
                                        WHERE run_id=b.run_id)
                       FOR UPDATE OF a,e,o""",
                    (binding.execution_id,))
                row=cur.fetchone()
                if not row or (
                    row["run_id"],row["native_workflow_id"],row["frozen_workflow_version"],
                    row["frozen_runtime_version"],row["frozen_plan_id"],
                    row["step_id"],row["attempt_id"]
                ) != (
                    binding.run_id,binding.native_workflow_id,binding.frozen_workflow_version,
                    binding.frozen_runtime_version,binding.plan_id,
                    binding.step_id,binding.attempt_id
                ):
                    raise FrozenTemporalMismatch("Native/Attempt/version mismatched")
                if row["astate"]=="UNKNOWN" and row["estate"]=="UNKNOWN":
                    return "RECONCILIATION_PENDING"
                if row["astate"]!="RUNNING" or row["estate"]!="RUNNING":
                    raise FrozenTemporalMismatch("Unexpected terminal platform execution")
                if row["dispatched_at"] is None or row["revoked_at"] is not None:
                    raise FrozenTemporalMismatch("No unresolved dispatched effect")
                if row["owner_live"]:
                    raise FrozenTemporalMismatch("Owner not expired; cannot quarantine")
                cur.execute(
                    "UPDATE poc_executions SET state='UNKNOWN',"
                    "failure_type='EXECUTOR_CRASH_AFTER_DISPATCH' WHERE execution_id=%s",
                    (binding.execution_id,))
                cur.execute(
                    "UPDATE poc_attempts SET state='UNKNOWN',"
                    "failure_type='EXECUTOR_CRASH_AFTER_DISPATCH' WHERE attempt_id=%s",
                    (binding.attempt_id,))
                cur.execute(
                    """UPDATE poc_execution_ownership SET fencing_token=fencing_token+1,
                       revoked_at=now(),owner_id=NULL WHERE execution_id=%s""",
                    (binding.execution_id,))
                cur.execute(
                    """INSERT INTO poc_reconciliations(execution_id,run_id,state,failure_type)
                       VALUES (%s,%s,'PENDING','EXECUTOR_CRASH_AFTER_DISPATCH')""",
                    (binding.execution_id,binding.run_id))
                cur.execute(
                    """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                       VALUES (%s,%s,(SELECT max(seq)+1 FROM poc_events WHERE run_id=%s),
                               'execution.unknown',%s::jsonb)""",
                    (_uid("event"),binding.run_id,binding.run_id,
                     json.dumps({"execution_id":binding.execution_id,
                                 "attempt_id":binding.attempt_id,
                                 "failure_type":"EXECUTOR_CRASH_AFTER_DISPATCH",
                                 "reconciliation_state":"PENDING"})))
                return "RECONCILIATION_PENDING"

    def snapshot(self, binding: FrozenTemporal) -> dict:
        with psycopg.connect(self.dsn,row_factory=dict_row) as conn:
            return dict(conn.execute(
                """SELECT r.state AS run_state,a.state AS attempt_state,
                          e.state AS execution_state,e.failure_type,
                          rec.state AS reconciliation_state,o.fencing_token,
                          o.dispatched_at IS NOT NULL AS dispatch_claimed,
                          b.native_workflow_id,b.frozen_workflow_version
                   FROM poc_c_temporal_bindings b
                   JOIN poc_runs r ON r.run_id=b.run_id
                   JOIN poc_attempts a ON a.attempt_id=b.attempt_id
                   JOIN poc_executions e ON e.execution_id=b.execution_id
                   LEFT JOIN poc_reconciliations rec ON rec.execution_id=b.execution_id
                   LEFT JOIN poc_execution_ownership o ON o.execution_id=b.execution_id
                   WHERE b.execution_id=%s""",
                (binding.execution_id,)).fetchone())
