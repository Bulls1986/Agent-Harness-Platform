"""POC-A23: PostgreSQL task-fact ledger owned by the Harness platform.

This is NOT a MAF SessionStore/HistoryProvider/CheckpointStorage and NOT a
distributed scheduler or recovery mechanism. Runtime checkpoint references
are opaque, and artifact payloads are never written to these tables.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from workflow_probe import PlatformOutcome, VerificationFact


class TaskFactConflict(RuntimeError):
    pass


def _id(kind: str) -> str:
    return f"{kind}-{uuid4().hex}"


class TaskLedger:
    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN required")
        self.dsn = dsn

    def initialize(self) -> None:
        root = Path(__file__).resolve().parent / "sql"
        with psycopg.connect(self.dsn) as conn:
            for name in ("001_task_facts.sql", "002_runtime_recovery.sql", "003_approval_wait.sql", "004_native_hitl_binding.sql", "005_hitl_delivery_and_execution_fencing.sql", "006_cancel_waiting_approval.sql", "007_durable_attempt_binding.sql", "008_durable_running_binding.sql", "009_durable_launch_intent.sql", "010_tool_receipt_reconciliation.sql", "011_recovery_point_refs.sql"):
                conn.execute((root / name).read_text(encoding="utf-8"))

    def start(self, fact: VerificationFact, *, initiator: str = "poc-ci-initiator") -> str:
        """Atomically create a Run plus first Plan/Step/Attempt/Execution."""
        if fact.plan_version != 1 or not all((
            fact.run_id, fact.plan_id, fact.step_id, fact.attempt_id, initiator
        )):
            raise ValueError("Invalid initial task identity")
        conversation_id, turn_id, execution_id = (
            _id("conversation"), _id("turn"), _id("execution")
        )
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO poc_conversations(conversation_id) VALUES (%s)",
                    (conversation_id,),
                )
                cur.execute(
                    "INSERT INTO poc_turns(turn_id,conversation_id) VALUES (%s,%s)",
                    (turn_id, conversation_id),
                )
                cur.execute(
                    """INSERT INTO poc_runs(run_id,turn_id,initiator_principal_id,
                       runtime_type,recipe_version,state)
                       VALUES (%s,%s,%s,'maf','poc-document-v1','RUNNING')""",
                    (fact.run_id, turn_id, initiator),
                )
                cur.execute(
                    "INSERT INTO poc_plans(plan_id,run_id,version,reason) VALUES (%s,%s,1,'initial')",
                    (fact.plan_id, fact.run_id),
                )
                cur.execute(
                    "INSERT INTO poc_steps(step_id,plan_id,ordinal,intent) VALUES (%s,%s,1,%s)",
                    (fact.step_id, fact.plan_id, "Verify trusted document fixture"),
                )
                cur.execute(
                    "INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state) VALUES (%s,%s,1,'RUNNING')",
                    (fact.attempt_id, fact.step_id),
                )
                cur.execute(
                    """INSERT INTO poc_executions(execution_id,attempt_id,
                       side_effect_class,state) VALUES (%s,%s,'PURE','RUNNING')""",
                    (execution_id, fact.attempt_id),
                )
                cur.execute(
                    """INSERT INTO poc_runtime_bindings(run_id,runtime_type)
                       VALUES (%s,'maf')""",
                    (fact.run_id,),
                )
                cur.execute(
                    """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                       VALUES (%s,%s,1,'run.started',%s::jsonb)""",
                    (_id("event"), fact.run_id,
                     json.dumps({"step_id": fact.step_id, "attempt_id": fact.attempt_id})),
                )
        return execution_id

    def append_plan(self, run_id: str, *, reason: str) -> tuple[str, int]:
        """Append a plan version while the Run is active; never overwrite v1."""
        if not reason.strip():
            raise ValueError("Replan reason required")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (run_id,))
                run = cur.fetchone()
                if run is None or run["state"] != "RUNNING":
                    raise TaskFactConflict("Only active Runs can be replanned")
                cur.execute(
                    """SELECT plan_id,version FROM poc_plans
                       WHERE run_id=%s ORDER BY version DESC LIMIT 1""",
                    (run_id,),
                )
                parent = cur.fetchone()
                version = parent["version"] + 1
                plan_id = _id("plan")
                cur.execute(
                    """INSERT INTO poc_plans(plan_id,run_id,version,parent_plan_id,reason)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (plan_id, run_id, version, parent["plan_id"], reason),
                )
                cur.execute(
                    "SELECT COALESCE(MAX(seq),0)+1 AS seq FROM poc_events WHERE run_id=%s",
                    (run_id,),
                )
                seq = cur.fetchone()["seq"]
                cur.execute(
                    """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                       VALUES (%s,%s,%s,'plan.replanned',%s::jsonb)""",
                    (_id("event"), run_id, seq, json.dumps({"plan_id": plan_id,"version":version})),
                )
                return plan_id, version

    def finish(self, fact: VerificationFact, outcome: PlatformOutcome, execution_id: str, *, owner_id: str | None = None, fencing_token: int | None = None) -> None:
        """Atomic attempt/execution/verifier/run terminal transaction.

        Called exclusively by the trusted POC runner after MAF Workflow gives an
        independently verified outcome. Never called on indeterminate results.
        """
        fields = ("run_id", "plan_id", "step_id", "attempt_id", "plan_version")
        if any(getattr(fact, field) != getattr(outcome, field) for field in fields):
            raise TaskFactConflict("MAF outcome identity does not match submitted platform facts")
        if outcome.run_state not in ("COMPLETED", "FAILED"):
            raise ValueError("Unsupported terminal state in this POC slice")
        if outcome.run_state == "COMPLETED" and (
            outcome.verification_state != "SUCCEEDED" or not outcome.evidence_ref
        ):
            raise TaskFactConflict("Completion requires external verification evidence")
        if outcome.run_state == "FAILED" and outcome.verification_state != "VERIFICATION_FAILURE":
            raise TaskFactConflict("Failure must retain its classification")
        if not outcome.evidence_ref:
            raise TaskFactConflict("Verifier must provide stable evidence reference")

        succeeded = outcome.run_state == "COMPLETED"
        attempt_state = "SUCCEEDED" if succeeded else "FAILED"
        failure_type = None if succeeded else "VERIFICATION_FAILURE"
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                # Row lock synchronizes competing completions. Terminal runs never reopen.
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (fact.run_id,))
                row = cur.fetchone()
                if row is None or row[0] != "RUNNING":
                    raise TaskFactConflict("Run absent or no longer active")
                # Only a current, live owner may finalize a claimed Execution.
                # Unowned legacy POC fixture executions remain compatible.
                cur.execute(
                    "SELECT 1 FROM poc_execution_ownership WHERE execution_id=%s",
                    (execution_id,),
                )
                if cur.fetchone() is not None:
                    from execution_ownership import assert_current_owner, StaleExecutionOwner
                    if not owner_id or fencing_token is None:
                        raise StaleExecutionOwner("Claimed Execution requires owner and fencing token")
                    assert_current_owner(cur,execution_id,owner_id=owner_id,token=fencing_token)
                cur.execute("SELECT MAX(version) FROM poc_plans WHERE run_id=%s", (fact.run_id,))
                if cur.fetchone()[0] != fact.plan_version:
                    raise TaskFactConflict("Cannot finalize Run using superseded Plan version")
                cur.execute(
                    """SELECT e.execution_id FROM poc_executions e
                       JOIN poc_attempts a ON a.attempt_id=e.attempt_id
                       JOIN poc_steps s ON s.step_id=a.step_id
                       JOIN poc_plans p ON p.plan_id=s.plan_id
                       WHERE e.execution_id=%s AND e.state='RUNNING'
                         AND a.attempt_id=%s AND a.state='RUNNING'
                         AND s.step_id=%s AND p.plan_id=%s AND p.version=%s
                         AND p.run_id=%s""",
                    (execution_id, fact.attempt_id, fact.step_id,
                     fact.plan_id, fact.plan_version, fact.run_id),
                )
                if cur.fetchone() is None:
                    raise TaskFactConflict("Attempt/Execution identity or state mismatch")
                cur.execute(
                    "UPDATE poc_attempts SET state=%s,failure_type=%s WHERE attempt_id=%s",
                    (attempt_state, failure_type, fact.attempt_id),
                )
                cur.execute(
                    "UPDATE poc_executions SET state=%s,failure_type=%s WHERE execution_id=%s",
                    (attempt_state, failure_type, execution_id),
                )
                cur.execute(
                    """INSERT INTO poc_verifications
                       (verification_id,execution_id,passed,evidence_ref)
                       VALUES (%s,%s,%s,%s)""",
                    (_id("verification"), execution_id, succeeded, outcome.evidence_ref),
                )
                cur.execute(
                    """UPDATE poc_runs SET state=%s,terminal_at=now()
                       WHERE run_id=%s""", (outcome.run_state, fact.run_id),
                )
                cur.execute(
                    """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                       VALUES (%s,%s,(SELECT COALESCE(MAX(seq),0)+1
                         FROM poc_events WHERE run_id=%s),%s,%s::jsonb)""",
                    (_id("event"), fact.run_id, fact.run_id, "run.terminal",
                     json.dumps({"state": outcome.run_state, "verification": outcome.verification_state,
                                 "attempt_id":fact.attempt_id, "evidence_ref":outcome.evidence_ref})),
                )

    def read(self, run_id: str) -> dict:
        """Re-open a fresh connection; readers never require an in-memory MAF Session."""
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            run = conn.execute(
                """SELECT run_id,state,turn_id,initiator_principal_id,recipe_version,
                          runtime_type,terminal_at FROM poc_runs WHERE run_id=%s""",
                (run_id,),
            ).fetchone()
            if run is None:
                raise KeyError(run_id)
            plans = conn.execute(
                """SELECT plan_id,version,parent_plan_id,reason FROM poc_plans
                   WHERE run_id=%s ORDER BY version""", (run_id,)
            ).fetchall()
            attempts = conn.execute(
                """SELECT a.attempt_id,a.ordinal,a.state,a.failure_type,s.step_id,p.version
                   FROM poc_attempts a JOIN poc_steps s ON s.step_id=a.step_id
                   JOIN poc_plans p ON p.plan_id=s.plan_id
                   WHERE p.run_id=%s ORDER BY p.version,a.ordinal""", (run_id,)
            ).fetchall()
            verifications = conn.execute(
                """SELECT v.passed,v.evidence_ref,e.execution_id
                   FROM poc_verifications v
                   JOIN poc_executions e ON e.execution_id=v.execution_id
                   JOIN poc_attempts a ON a.attempt_id=e.attempt_id
                   JOIN poc_steps s ON s.step_id=a.step_id
                   JOIN poc_plans p ON p.plan_id=s.plan_id
                   WHERE p.run_id=%s""", (run_id,)
            ).fetchall()
            events = conn.execute(
                "SELECT seq,event_type,payload FROM poc_events WHERE run_id=%s ORDER BY seq",
                (run_id,),
            ).fetchall()
            # Timestamp returned as string for JSON-safe CLI output.
            return {"run": {**run, "terminal_at": (
                        run["terminal_at"].isoformat() if run["terminal_at"] else None)},
                    "plans": plans, "attempts": attempts,
                    "verifications": verifications, "events": events}
