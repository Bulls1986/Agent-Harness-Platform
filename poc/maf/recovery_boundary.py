"""A27/A28 bounded safe recovery decision at a task Step boundary.

A simulated process exit is deliberately NOT a MAF Workflow checkpoint.
Only a PURE, read-only fixture execution can be retried without inspection.
UNKNOWN non-PURE outcome becomes an explicit reconciliation record; never
re-dispatch external work merely because a worker disappeared.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from task_ledger import TaskFactConflict, _id
from workflow_probe import VerificationFact


@dataclass(frozen=True)
class RecoveryDecision:
    outcome: str
    fact: VerificationFact | None = None
    execution_id: str | None = None


class RecoveryCoordinator:
    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("Postgres DSN required")
        self.dsn = dsn

    def recover(self, run_id: str, *, interrupted_attempt_id: str) -> RecoveryDecision:
        if not interrupted_attempt_id:
            raise ValueError("Interrupted Attempt identity is required for idempotent recovery")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # Serialize with TaskLedger.finish() and concurrent recoverers.
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (run_id,))
                run = cur.fetchone()
                if run is None:
                    raise KeyError(run_id)
                if run["state"] != "RUNNING":
                    return RecoveryDecision(outcome="NOT_ACTIVE")
                cur.execute(
                    """SELECT p.plan_id,p.version,s.step_id,a.attempt_id,a.ordinal,
                              e.execution_id,e.side_effect_class
                       FROM poc_plans p
                       JOIN poc_steps s ON s.plan_id=p.plan_id
                       JOIN poc_attempts a ON a.step_id=s.step_id
                       JOIN poc_executions e ON e.attempt_id=a.attempt_id
                       WHERE p.run_id=%s AND a.state='RUNNING' AND e.state='RUNNING'
                       ORDER BY p.version DESC, a.ordinal DESC FOR UPDATE OF a,e""",
                    (run_id,),
                )
                active = cur.fetchall()
                if len(active) != 1:
                    # No implicit whole-Run replay and no ambiguous multiple dispatch.
                    return RecoveryDecision(outcome="NO_UNIQUE_ACTIVE_EXECUTION")
                old = active[0]
                if old["attempt_id"] != interrupted_attempt_id:
                    # Prevent a duplicate recovery command from killing its successor.
                    return RecoveryDecision(outcome="ATTEMPT_ALREADY_HANDLED")
                cur.execute(
                    "SELECT MAX(version) AS version FROM poc_plans WHERE run_id=%s",
                    (run_id,),
                )
                if cur.fetchone()["version"] != old["version"]:
                    return RecoveryDecision(outcome="SUPERSEDED_PLAN_REQUIRES_DECISION")
                if old["side_effect_class"] != "PURE":
                    cur.execute(
                        """UPDATE poc_attempts SET state='UNKNOWN',failure_type='EXECUTOR_CRASH'
                           WHERE attempt_id=%s""", (old["attempt_id"],),
                    )
                    cur.execute(
                        """UPDATE poc_executions SET state='UNKNOWN',failure_type='EXECUTOR_CRASH'
                           WHERE execution_id=%s""", (old["execution_id"],),
                    )
                    cur.execute(
                        """INSERT INTO poc_reconciliations(execution_id,run_id,state,failure_type)
                           VALUES (%s,%s,'PENDING','EXECUTOR_CRASH')""",
                        (old["execution_id"],run_id),
                    )
                    event_kind = "execution.unknown"
                    payload = {"attempt_id":old["attempt_id"],"decision":"RECONCILIATION"}
                    decision = RecoveryDecision(outcome="RECONCILIATION")
                else:
                    cur.execute(
                        """UPDATE poc_attempts SET state='FAILED',failure_type='EXECUTOR_CRASH'
                           WHERE attempt_id=%s""", (old["attempt_id"],),
                    )
                    cur.execute(
                        """UPDATE poc_executions SET state='FAILED',failure_type='EXECUTOR_CRASH'
                           WHERE execution_id=%s""", (old["execution_id"],),
                    )
                    fact = VerificationFact(
                        run_id=run_id,
                        plan_id=old["plan_id"],
                        step_id=old["step_id"],
                        attempt_id=_id("attempt"),
                        plan_version=old["version"],
                        passed=False,
                        evidence_ref=None,
                    )
                    cur.execute(
                        """INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state)
                           VALUES (%s,%s,%s,'RUNNING')""",
                        (fact.attempt_id, fact.step_id,old["ordinal"] + 1),
                    )
                    new_execution_id = _id("execution")
                    cur.execute(
                        """INSERT INTO poc_executions(execution_id,attempt_id,side_effect_class,state)
                           VALUES (%s,%s,'PURE','RUNNING')""",
                        (new_execution_id, fact.attempt_id),
                    )
                    event_kind = "attempt.restarted"
                    payload = {"prior_attempt_id":old["attempt_id"],
                               "new_attempt_id":fact.attempt_id, "step_id":fact.step_id}
                    decision = RecoveryDecision(outcome="STEP_BOUNDARY_RETRY",
                                                fact=fact, execution_id=new_execution_id)
                cur.execute(
                    """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                       VALUES (%s,%s,(SELECT COALESCE(MAX(seq),0)+1
                         FROM poc_events WHERE run_id=%s),%s,%s::jsonb)""",
                    (_id("event"),run_id,run_id,event_kind,json.dumps(payload)),
                )
                return decision
