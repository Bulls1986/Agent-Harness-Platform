"""A29: deterministic Run cancellation and Execution timeout facts.

This is a platform-side POC control decision, NOT an implementation of a
runtime provider's cancellation signal. The caller must supply a trusted,
verified adapter termination result. ACKNOWLEDGED does not mean TERMINATED.
No new dispatch is admitted while Run=CANCELLING. No automatic compensation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from task_ledger import _id


class ControlConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class ControlOutcome:
    run_id: str
    run_state: str
    resolution: str
    failure_type: str | None = None


class ExecutionControl:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("PostgreSQL DSN required")
        self.dsn = dsn

    @staticmethod
    def _event(cur, run_id: str, kind: str, payload: dict) -> None:
        cur.execute(
            """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
               VALUES (%s,%s,(SELECT COALESCE(MAX(seq),0)+1 FROM poc_events WHERE run_id=%s),
                       %s,%s::jsonb)""",
            (_id("event"),run_id,run_id,kind,json.dumps(payload)),
        )

    @staticmethod
    def _active(cur, run_id: str) -> dict:
        cur.execute(
            """SELECT e.execution_id,e.side_effect_class,e.state AS execution_state,
                      a.attempt_id,a.state AS attempt_state,
                      o.dispatched_at,o.owner_id,o.fencing_token,o.revoked_at
               FROM poc_executions e
               JOIN poc_attempts a ON a.attempt_id=e.attempt_id
               JOIN poc_steps s ON s.step_id=a.step_id
               JOIN poc_plans p ON p.plan_id=s.plan_id
               LEFT JOIN poc_execution_ownership o ON o.execution_id=e.execution_id
               WHERE p.run_id=%s AND e.state='RUNNING' AND a.state='RUNNING'
               FOR UPDATE OF e,a""",
            (run_id,),
        )
        rows=cur.fetchall()
        if len(rows)!=1:
            raise ControlConflict("Need exactly one active Execution for this POC slice")
        return dict(rows[0])

    @staticmethod
    def _finish(cur, execution: dict, *, state: str, failure_type: str | None):
        cur.execute(
            "UPDATE poc_executions SET state=%s,failure_type=%s WHERE execution_id=%s",
            (state,failure_type,execution["execution_id"]),
        )
        cur.execute(
            "UPDATE poc_attempts SET state=%s,failure_type=%s WHERE attempt_id=%s",
            (state,failure_type,execution["attempt_id"]),
        )

    @staticmethod
    def _reconcile(cur, run_id: str, execution: dict, reason: str):
        cur.execute(
            """INSERT INTO poc_reconciliations
               (execution_id,run_id,state,failure_type)
               VALUES (%s,%s,'PENDING',%s) ON CONFLICT (execution_id) DO NOTHING""",
            (execution["execution_id"],run_id,reason),
        )

    def request_cancel(self, run_id: str, *, initiator: str = "poc-fixture-user") -> ControlOutcome:
        """Record intent only; never equate cancel request with safe termination."""
        if not initiator:
            raise ValueError("Initiator principal required")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (run_id,))
                row=cur.fetchone()
                if row is None:
                    raise KeyError(run_id)
                if row["state"] in ("WAITING_APPROVAL","WAITING_INPUT"):
                    # No gated Execution may have started in this bounded fixture.
                    cur.execute(
                        """SELECT count(*) AS n FROM poc_executions e
                           JOIN poc_attempts a ON a.attempt_id=e.attempt_id
                           JOIN poc_steps s ON s.step_id=a.step_id
                           JOIN poc_plans p ON p.plan_id=s.plan_id
                           WHERE p.run_id=%s""",
                        (run_id,),
                    )
                    if cur.fetchone()["n"] != 0:
                        raise ControlConflict("Waiting Run already has Execution; cannot direct-cancel")
                    cur.execute(
                        "UPDATE poc_approvals SET state='CANCELLED' WHERE run_id=%s AND state='PENDING'",
                        (run_id,),
                    )
                    cur.execute(
                        "UPDATE poc_runs SET state='CANCELLED',terminal_at=now() WHERE run_id=%s",
                        (run_id,),
                    )
                    self._event(cur,run_id,"run.cancelled_waiting",{"initiator":initiator})
                    return ControlOutcome(run_id,"CANCELLED","WAITING_CANCELLED")
                if row["state"]=="CANCELLING":
                    return ControlOutcome(run_id,"CANCELLING","ALREADY_REQUESTED")
                if row["state"]!="RUNNING":
                    raise ControlConflict("Run is not cancellable")
                self._active(cur,run_id)
                cur.execute("UPDATE poc_runs SET state='CANCELLING' WHERE run_id=%s",(run_id,))
                self._event(cur,run_id,"run.cancel_requested",{"initiator":initiator})
                return ControlOutcome(run_id,"CANCELLING","SIGNAL_REQUIRED")

    def accept_cancel_result(self, run_id: str, *, adapter_result: str) -> ControlOutcome:
        """Consume a trusted Provider adapter result, not a client ACK.

        ACKNOWLEDGED merely means a signal was received. TERMINATED only
        establishes no further execution; it does not undo earlier dispatch.
        """
        if adapter_result not in ("ACKNOWLEDGED","TERMINATED","UNSUPPORTED","UNKNOWN"):
            raise ValueError("Unknown adapter cancellation capability result")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",(run_id,))
                row=cur.fetchone()
                if row is None:
                    raise KeyError(run_id)
                if row["state"]!="CANCELLING":
                    raise ControlConflict("Run must be CANCELLING")
                execution=self._active(cur,run_id)
                # If no ownership row exists, cannot prove whether dispatched.
                definitely_not_dispatched = (
                    execution["owner_id"] is not None
                    and execution["dispatched_at"] is None
                    and execution["revoked_at"] is None
                )
                if adapter_result in ("ACKNOWLEDGED","UNSUPPORTED"):
                    self._event(cur,run_id,"run.cancel_signal",{"adapter_result":adapter_result})
                    return ControlOutcome(run_id,"CANCELLING",adapter_result)
                if adapter_result=="TERMINATED" and (
                    definitely_not_dispatched or execution["side_effect_class"]=="PURE"
                ):
                    self._finish(cur,execution,state="CANCELLED",failure_type="USER_CANCELLED")
                    cur.execute(
                        "UPDATE poc_runs SET state='CANCELLED',terminal_at=now() WHERE run_id=%s",
                        (run_id,),
                    )
                    self._event(cur,run_id,"run.cancelled",{"adapter_result":"TERMINATED"})
                    return ControlOutcome(run_id,"CANCELLED","TERMINATED")
                # Dispatched non-PURE/unknown owner -> cannot infer its side effect,
                # even if a cancellation signal has stopped future activity.
                reason="UNKNOWN_OUTCOME"
                self._finish(cur,execution,state="UNKNOWN",failure_type=reason)
                self._reconcile(cur,run_id,execution,reason)
                self._event(cur,run_id,"execution.unknown",{
                    "cause":"CANCEL","adapter_result":adapter_result,
                    "execution_id":execution["execution_id"],
                })
                return ControlOutcome(run_id,"CANCELLING","RECONCILIATION",reason)

    def record_timeout(self, run_id: str) -> ControlOutcome:
        """Timeout is a failure cause, not a Run state or proof of safe stop."""
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",(run_id,))
                row=cur.fetchone()
                if row is None:
                    raise KeyError(run_id)
                if row["state"]!="RUNNING":
                    raise ControlConflict("Timeout requires active RUNNING Run")
                execution=self._active(cur,run_id)
                definitely_not_dispatched = (
                    execution["owner_id"] is not None
                    and execution["dispatched_at"] is None
                    and execution["revoked_at"] is None
                )
                if definitely_not_dispatched:
                    self._finish(cur,execution,state="FAILED",failure_type="TIMEOUT")
                    cur.execute(
                        "UPDATE poc_runs SET state='FAILED',terminal_at=now() WHERE run_id=%s",
                        (run_id,),
                    )
                    self._event(cur,run_id,"run.timeout",{"failure_type":"TIMEOUT"})
                    return ControlOutcome(run_id,"FAILED","NOT_DISPATCHED","TIMEOUT")
                if execution["side_effect_class"]=="PURE":
                    # No speculative terminalization while old PURE worker may
                    # still be running; wait for adapter termination/fencing.
                    self._event(cur,run_id,"execution.timeout_signal",{
                        "failure_type":"TIMEOUT","termination_unverified":True,
                    })
                    return ControlOutcome(run_id,"RUNNING","TERMINATION_REQUIRED","TIMEOUT")
                reason="TIMEOUT_AFTER_DISPATCH"
                self._finish(cur,execution,state="UNKNOWN",failure_type=reason)
                self._reconcile(cur,run_id,execution,reason)
                self._event(cur,run_id,"execution.unknown",{
                    "cause":"TIMEOUT","failure_type":reason,
                    "execution_id":execution["execution_id"],
                })
                return ControlOutcome(run_id,"RUNNING","RECONCILIATION",reason)
