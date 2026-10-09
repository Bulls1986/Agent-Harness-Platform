"""ARCH-TODO-025 G3: read-only, provider-neutral Typed Event projection.

Consumes only Harness-owned PostgreSQL Run/Event facts. Supports the verified
C15 Token, C11 Artifact, and C16 UNKNOWN/Receipt event shapes across existing
Temporal-backed Runs. This does NOT create synthetic events or establish that
these distinct POC tasks execute within the same Run.
"""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row


# Explicit per-type allowlist: never copy arbitrary Tool, Native or Secret
# payload fields to browser SSE even if a Provider adds them to PG.
PORTABLE_FIELDS = {
    "run.started": ("step_id", "attempt_id", "execution_id", "provider_count"),
    "plan.created": ("step_id", "version"),
    "activity.started": ("step_id", "attempt_id", "execution_id"),
    "response.output_text.delta": ("delta",),
    "response.output_text.done": ("sha256", "chars"),
    "artifact.created": ("artifact_id", "step_id", "attempt_id",
                         "execution_id", "storage_ref", "sha256", "size_bytes"),
    "verification.passed": ("execution_id", "artifact_id", "evidence_id",
                             "sha256", "passed"),
    "execution.unknown": ("execution_id", "attempt_id", "failure_type",
                          "reconciliation_state"),
    "execution.reconciled": ("execution_id", "attempt_id", "status",
                             "receipt_ref"),
    "cancellation.requested": ("attempt_id", "execution_id"),
    "cancellation.acknowledged": ("provider",),
    "cancellation.confirmed": ("native_status", "state"),
    "run.terminal": ("state", "status"),
}
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "ABORTED"}


def project_event(run: dict, row: dict) -> dict:
    kind = row["event_type"]
    if kind not in PORTABLE_FIELDS:
        raise ValueError("Unsupported platform event type: " + str(kind))
    payload = row["payload"]
    if not isinstance(payload, dict):
        raise ValueError("Persisted event payload must be an object")
    data = {field: payload[field] for field in PORTABLE_FIELDS[kind]
            if field in payload}
    return {
        "id": f"{run['run_id']}:{row['seq']}",
        "event_id": row["event_id"],
        "sequence": row["seq"],
        "schema_version": "1",
        "run_id": run["run_id"],
        "conversation_id": run["conversation_id"],
        "turn_id": run["turn_id"],
        "item_id": data.get("attempt_id") or data.get("artifact_id") or run["run_id"],
        "type": kind,
        "data": data,
        "timestamp": row["created_at"].isoformat(),
    }


class TemporalEventFeed:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("Harness PostgreSQL not configured")
        self.dsn = dsn

    def snapshot(self, run_id: str, after: int = 0, limit: int = 1000):
        if after < 0 or not 1 <= limit <= 1000:
            raise ValueError("Invalid SSE paging bounds")
        with psycopg.connect(self.dsn, row_factory=dict_row) as pg:
            # One immutable MVCC snapshot of platform Run + Event facts.
            pg.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            run = pg.execute(
                """SELECT r.run_id,r.state,r.runtime_type,r.turn_id,
                          t.conversation_id
                   FROM poc_runs r JOIN poc_turns t ON t.turn_id=r.turn_id
                   WHERE r.run_id=%s""", (run_id,)).fetchone()
            if not run or run["runtime_type"] != "temporal":
                raise KeyError(run_id)
            rows = pg.execute(
                """SELECT event_id,seq,event_type,payload,created_at
                   FROM poc_events WHERE run_id=%s AND seq>%s
                   ORDER BY seq LIMIT %s""",
                (run_id, after, limit)).fetchall()
        # Reject gaps and unsupported event types instead of silently
        # skipping business facts or leaking provider-specific data.
        if rows and (rows[0]["seq"] != after + 1 or
                     any(b["seq"] != a["seq"] + 1 for a, b in zip(rows, rows[1:]))):
            raise ValueError("Noncontiguous Harness event history")
        data = [project_event(run, row) for row in rows]
        return dict(run), data