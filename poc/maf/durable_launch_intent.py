"""A34 P1: persist native launch intent before invoking official Durable /run.

A Durable start and a PostgreSQL binding cannot be committed atomically.
A caller MUST record an intent, invoke native MAF API once, and subsequently
persist the Native Instance binding. No stored native ID means UNKNOWN, not
permission to submit /run again. Only the official runtime/status API can
verify a recovered native ID; this store cannot inspect the provider itself.
"""
from __future__ import annotations

from dataclasses import dataclass
import psycopg
from psycopg.rows import dict_row

from durable_approval_binding import DurableBindingMismatch
from durable_running_binding import RunningNativeBinding


@dataclass(frozen=True)
class NativeLaunchIntent:
    run_id: str
    step_id: str
    attempt_id: str
    execution_id: str
    native_workflow_name: str
    frozen_workflow_version: str
    frozen_runtime_version: str


@dataclass(frozen=True)
class LaunchGapDecision:
    state: str
    execution_id: str


class DurableLaunchIntentStore:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("Platform PostgreSQL DSN required")
        self.dsn = dsn

    def prepare(self, binding: NativeLaunchIntent) -> None:
        """Before native /run: one immutable platform start intent per Attempt."""
        if not all(vars(binding).values()):
            raise ValueError("Complete platform/native frozen identity required")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                            (binding.run_id,))
                row = cur.fetchone()
                if row is None or row[0] != "RUNNING":
                    raise DurableBindingMismatch("No active Run for native launch")
                try:
                    cur.execute(
                        """INSERT INTO poc_maf_durable_launch_intents
                           (execution_id,run_id,step_id,attempt_id,
                            native_workflow_name,frozen_workflow_version,
                            frozen_runtime_version)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        (binding.execution_id,binding.run_id,binding.step_id,
                         binding.attempt_id,binding.native_workflow_name,
                         binding.frozen_workflow_version,binding.frozen_runtime_version),
                    )
                except psycopg.errors.UniqueViolation as exc:
                    raise DurableBindingMismatch(
                        "Native launch intent already exists: no blind /run replay"
                    ) from exc

    def inspect(self, expected: NativeLaunchIntent | RunningNativeBinding) -> LaunchGapDecision:
        """Read-only decision. Never starts/retries Native Instance.

        Caller must independently observe native identity using official API.
        """
        if not all(vars(expected).values()):
            raise ValueError("Complete platform/native identity required")
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                """SELECT i.execution_id,i.run_id,i.step_id,i.attempt_id,
                          i.native_workflow_name,i.frozen_workflow_version,
                          i.frozen_runtime_version,
                          b.native_instance_id AS bound_instance,
                          e.state AS execution_state
                   FROM poc_maf_durable_launch_intents i
                   JOIN poc_executions e ON e.execution_id=i.execution_id
                   LEFT JOIN poc_maf_durable_running_bindings b
                     ON b.execution_id=i.execution_id
                   WHERE i.execution_id=%s""",
                (expected.execution_id,),
            ).fetchone()
            if row is None:
                raise DurableBindingMismatch("Missing persisted launch intent")
            for field in ("execution_id","run_id","step_id","attempt_id",
                          "native_workflow_name","frozen_workflow_version",
                          "frozen_runtime_version"):
                if row[field] != getattr(expected, field):
                    raise DurableBindingMismatch("Frozen native launch identity mismatch")
            if row["bound_instance"] is not None:
                observed = getattr(expected, "native_instance_id", None)
                if observed is None:
                    return LaunchGapDecision("BOUND_REQUIRES_NATIVE_VERIFICATION", expected.execution_id)
                if row["bound_instance"] != observed:
                    raise DurableBindingMismatch("Another native Instance is already bound")
                return LaunchGapDecision("BOUND", expected.execution_id)
            if row["execution_state"] == "UNKNOWN":
                return LaunchGapDecision("RECONCILIATION_PENDING", expected.execution_id)
            return LaunchGapDecision("UNBOUND_NATIVE_MUST_RECONCILE", expected.execution_id)

    def quarantine_unbound(self, expected: NativeLaunchIntent | RunningNativeBinding) -> LaunchGapDecision:
        """Crash between Native start and PG bind: fail closed, no new Attempt.

        The discovered native ID is not authorization. An absent Native
        instance in a read-only query is inconclusive: never relaunch blindly.
        """
        if self.inspect(expected).state.startswith("BOUND"):
            raise DurableBindingMismatch("Bound Native Instance is not an orphan")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                            (expected.run_id,))
                run = cur.fetchone()
                if run is None or run["state"] != "RUNNING":
                    raise DurableBindingMismatch("Native launch Run no longer active")
                cur.execute(
                    """SELECT e.state,a.state AS attempt_state,
                              b.native_instance_id AS bound
                       FROM poc_executions e
                       JOIN poc_attempts a ON a.attempt_id=e.attempt_id
                       LEFT JOIN poc_maf_durable_running_bindings b
                         ON b.execution_id=e.execution_id
                       JOIN poc_maf_durable_launch_intents i
                         ON i.execution_id=e.execution_id
                       WHERE e.execution_id=%s AND i.attempt_id=%s
                       FOR UPDATE OF e,a""",
                    (expected.execution_id,expected.attempt_id),
                )
                row = cur.fetchone()
                if row is None or row["bound"] is not None:
                    raise DurableBindingMismatch("Missing or already-bound launch intent")
                if row["state"] == "UNKNOWN" and row["attempt_state"] == "UNKNOWN":
                    return LaunchGapDecision("RECONCILIATION_PENDING", expected.execution_id)
                if row["state"] != "RUNNING" or row["attempt_state"] != "RUNNING":
                    raise DurableBindingMismatch("Interrupted launch is not active")
                cur.execute(
                    """UPDATE poc_executions SET state='UNKNOWN',
                       failure_type='NATIVE_START_UNCERTAIN' WHERE execution_id=%s""",
                    (expected.execution_id,),
                )
                cur.execute(
                    """UPDATE poc_attempts SET state='UNKNOWN',
                       failure_type='NATIVE_START_UNCERTAIN' WHERE attempt_id=%s""",
                    (expected.attempt_id,),
                )
                cur.execute(
                    """INSERT INTO poc_reconciliations
                       (execution_id,run_id,state,failure_type)
                       VALUES (%s,%s,'PENDING','NATIVE_START_UNCERTAIN')""",
                    (expected.execution_id,expected.run_id),
                )
                return LaunchGapDecision("RECONCILIATION_PENDING", expected.execution_id)
