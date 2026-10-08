"""A29: Execution-scoped ownership (PostgreSQL, not Runtime/TaskHub leases).

No scheduler or lock service: only claim, heartbeat, dispatch admission and
fencing validation on platform-owned Execution metadata. An expired owner
cannot commit. A new worker cannot steal the same RUNNING Execution; the
task recovery contract must first classify failure/side effects.
"""
from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row


class StaleExecutionOwner(RuntimeError):
    pass


@dataclass(frozen=True)
class Ownership:
    execution_id: str
    owner_id: str
    fencing_token: int


def _validate_ttl(ttl_seconds: int) -> None:
    if isinstance(ttl_seconds,bool) or not isinstance(ttl_seconds,int) or not 1 <= ttl_seconds <= 3600:
        raise ValueError("Lease TTL seconds must be an integer between 1 and 3600")


def assert_current_owner(cur, execution_id: str, *, owner_id: str, token: int) -> None:
    """Must be called inside a transaction holding the parent Run row lock."""
    cur.execute(
        """SELECT owner_id,fencing_token,revoked_at,lease_expires_at > now() AS live
           FROM poc_execution_ownership WHERE execution_id=%s FOR UPDATE""",
        (execution_id,),
    )
    x=cur.fetchone()
    if x is None or x[0]!=owner_id or x[1]!=token or x[2] is not None or not x[3]:
        raise StaleExecutionOwner("STALE_EXECUTION_OWNER")


class ExecutionOwnership:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("PostgreSQL DSN required")
        self.dsn=dsn

    def _lock_active_run(self, cur, execution_id: str):
        cur.execute(
            """SELECT p.run_id FROM poc_executions e
               JOIN poc_attempts a ON a.attempt_id=e.attempt_id
               JOIN poc_steps s ON s.step_id=a.step_id
               JOIN poc_plans p ON p.plan_id=s.plan_id
               WHERE e.execution_id=%s""",
            (execution_id,),
        )
        row=cur.fetchone()
        if row is None:
            raise KeyError(execution_id)
        cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (row[0],))
        if cur.fetchone()[0]!="RUNNING":
            raise StaleExecutionOwner("Run not active")
        cur.execute(
            """SELECT e.state,a.state FROM poc_executions e
               JOIN poc_attempts a ON a.attempt_id=e.attempt_id
               WHERE e.execution_id=%s""",
            (execution_id,),
        )
        execution,attempt=cur.fetchone()
        if execution!="RUNNING" or attempt!="RUNNING":
            raise StaleExecutionOwner("Execution or Attempt not active")

    def claim(self, execution_id: str, *, owner_id: str, ttl_seconds: int=30) -> Ownership:
        _validate_ttl(ttl_seconds)
        if not owner_id:
            raise ValueError("Worker identity required")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                self._lock_active_run(cur,execution_id)
                cur.execute(
                    "SELECT fencing_token FROM poc_execution_ownership WHERE execution_id=%s FOR UPDATE",
                    (execution_id,),
                )
                if cur.fetchone() is not None:
                    raise StaleExecutionOwner("Existing ownership must go through recovery; no blind handoff")
                cur.execute(
                    """INSERT INTO poc_execution_ownership
                       (execution_id,owner_id,fencing_token,lease_expires_at)
                       VALUES (%s,%s,1,now()+make_interval(secs => %s))""",
                    (execution_id,owner_id,ttl_seconds),
                )
                return Ownership(execution_id,owner_id,1)

    def heartbeat(self, ownership: Ownership, *, ttl_seconds: int=30) -> None:
        _validate_ttl(ttl_seconds)
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                self._lock_active_run(cur,ownership.execution_id)
                assert_current_owner(cur,ownership.execution_id,
                                     owner_id=ownership.owner_id,token=ownership.fencing_token)
                cur.execute(
                    """UPDATE poc_execution_ownership
                       SET last_heartbeat_at=now(),
                           lease_expires_at=now()+make_interval(secs => %s)
                       WHERE execution_id=%s""",
                    (ttl_seconds,ownership.execution_id),
                )

    def dispatch(self, ownership: Ownership) -> None:
        """Allow exactly one platform dispatch request for this ownership epoch.

        Does NOT guarantee the external receiver applied a side effect exactly once.
        """
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                self._lock_active_run(cur,ownership.execution_id)
                assert_current_owner(cur,ownership.execution_id,
                                     owner_id=ownership.owner_id,token=ownership.fencing_token)
                cur.execute(
                    """UPDATE poc_execution_ownership SET dispatched_at=now()
                       WHERE execution_id=%s AND dispatched_at IS NULL""",
                    (ownership.execution_id,),
                )
                if cur.rowcount!=1:
                    raise StaleExecutionOwner("Repeated dispatch requires idempotency/reconciliation")
