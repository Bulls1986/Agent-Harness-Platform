"""A24: persist *native* MAF AgentSession as opaque runtime state.

This POC uses a dedicated runtime table to prove serialization/rehydration
across Python processes, NOT platform Run state, a new history engine, or a
production-grade large session payload backend. Provider fingerprint is bound
to the saved session and revision uses compare-and-swap.
"""
from __future__ import annotations

import json
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from agent_framework import AgentSession


class SessionConflict(RuntimeError):
    pass


class NativeSessionStore:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("PostgreSQL DSN required")
        self.dsn = dsn

    def initialize(self) -> None:
        from pathlib import Path
        sql = (Path(__file__).resolve().parent / "sql" / "002_runtime_recovery.sql").read_text()
        with psycopg.connect(self.dsn) as conn:
            conn.execute(sql)

    def save(self, run_id: str, session: AgentSession, *,
             fingerprint: str, expected_revision: int | None = None) -> int:
        if not run_id or not fingerprint:
            raise ValueError("Run and provider fingerprint required")
        payload = session.to_dict()
        raw = json.dumps(payload, sort_keys=True)
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT runtime_type FROM poc_runs WHERE run_id=%s FOR UPDATE",
                    (run_id,),
                )
                row = cur.fetchone()
                if row is None or row["runtime_type"] != "maf":
                    raise SessionConflict("Unknown or incompatible MAF Run")
                cur.execute(
                    """SELECT revision,provider_fingerprint,session_ref FROM poc_maf_sessions
                       WHERE run_id=%s FOR UPDATE""", (run_id,),
                )
                prev = cur.fetchone()
                if prev is None:
                    if expected_revision is not None:
                        raise SessionConflict("Session absent; expected revision must be null")
                    reference = f"maf-session://{uuid4().hex}"
                    cur.execute(
                        """INSERT INTO poc_maf_sessions
                           (run_id,session_ref,provider_fingerprint,revision,native_payload)
                           VALUES (%s,%s,%s,1,%s::jsonb)""",
                        (run_id, reference, fingerprint, raw),
                    )
                    cur.execute(
                        """UPDATE poc_runtime_bindings SET native_session_ref=%s
                           WHERE run_id=%s""", (reference,run_id),
                    )
                    return 1
                if prev["provider_fingerprint"] != fingerprint:
                    raise SessionConflict("Provider configuration differs from saved session")
                if expected_revision is None or prev["revision"] != expected_revision:
                    raise SessionConflict("Stale native session writer")
                version = expected_revision + 1
                cur.execute(
                    """UPDATE poc_maf_sessions
                       SET native_payload=%s::jsonb, revision=%s, updated_at=now()
                       WHERE run_id=%s""", (raw, version, run_id),
                )
                return version

    def load(self, run_id: str, *, fingerprint: str) -> tuple[AgentSession, int]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                """SELECT s.native_payload,s.revision,s.provider_fingerprint
                   FROM poc_maf_sessions s
                   JOIN poc_runtime_bindings b
                     ON b.run_id=s.run_id AND b.native_session_ref=s.session_ref
                   WHERE s.run_id=%s AND b.runtime_type='maf'""",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            if row["provider_fingerprint"] != fingerprint:
                raise SessionConflict("Provider configuration differs from saved session")
            # MAF public factory owns hydration. Harness does not parse history.
            return AgentSession.from_dict(row["native_payload"]), row["revision"]
