"""Small *PostgreSQL-backed* Harness Facts adapter for the limited closed-loop POC.

This is NOT the final production schema, Reconciler, or authorization service.
Hatchet uses a separate PostgreSQL database and owns all engine task history.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os

import psycopg


class UnsafeDispatch(RuntimeError):
    """Fail closed on an ambiguous provider dispatch or business transition."""


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PgFacts:
    def __init__(self, url: str | None = None):
        self.url = url or os.environ["HARNESS_POC_DATABASE_URL"]
        if not self.url:
            raise ValueError("HARNESS_POC_DATABASE_URL is required")
        self.init_schema()

    @contextmanager
    def tx(self):
        with psycopg.connect(self.url) as connection:
            with connection.transaction():
                yield connection

    def init_schema(self):
        with self.tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_run (
                    id TEXT PRIMARY KEY, plan_version INTEGER NOT NULL,
                    state TEXT NOT NULL, provider_workflow_id TEXT UNIQUE,
                    event_seq BIGINT NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            c.execute("ALTER TABLE harness_run ADD COLUMN IF NOT EXISTS "
                      "created_at TIMESTAMPTZ NOT NULL DEFAULT now()")
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_step (
                    run_id TEXT NOT NULL REFERENCES harness_run(id), id TEXT NOT NULL,
                    state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    input_hash TEXT, output TEXT, output_hash TEXT,
                    PRIMARY KEY (run_id, id)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_outbox (
                    command_key TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES harness_run(id),
                    state TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_event (
                    run_id TEXT NOT NULL REFERENCES harness_run(id), seq BIGINT NOT NULL,
                    type TEXT NOT NULL, data JSONB NOT NULL,
                    PRIMARY KEY (run_id, seq)
                )
            """)

    @staticmethod
    def event(c, rid: str, kind: str, data: dict):
        # Each domain transaction locks its Run row: monotonic per-Run sequence
        # despite different Engine worker tasks and concurrent late observations.
        seq = c.execute(
            "UPDATE harness_run SET event_seq=event_seq+1 WHERE id=%s RETURNING event_seq",
            (rid,),
        ).fetchone()[0]
        c.execute(
            "INSERT INTO harness_event VALUES (%s,%s,%s,%s::jsonb)",
            (rid, seq, kind, json.dumps(data, sort_keys=True)),
        )

    def create(self, rid: str) -> str:
        key = f"{rid}:segment-0:create:v1"
        with self.tx() as c:
            c.execute("INSERT INTO harness_run(id,plan_version,state) "
                      "VALUES (%s,1,'CREATED')", (rid,))
            for name in ("pydantic", "openai"):
                c.execute("INSERT INTO harness_step(run_id,id,state) "
                          "VALUES (%s,%s,'PENDING')", (rid, name))
            c.execute("INSERT INTO harness_outbox VALUES (%s,%s,'PENDING')",
                      (key, rid))
            self.event(c, rid, "run.created", {"plan_version": 1})
        return key

    def dispatch(self, key: str):
        with self.tx() as c:
            row = c.execute(
                "SELECT run_id,state FROM harness_outbox WHERE command_key=%s FOR UPDATE",
                (key,),
            ).fetchone()
            if not row or row[1] != "PENDING":
                raise UnsafeDispatch("Provider ACK uncertain: never blindly create again")
            c.execute("UPDATE harness_outbox SET state='DISPATCHING' "
                      "WHERE command_key=%s", (key,))
            self.event(c, row[0], "workflow.dispatching", {"command_key": key})

    def bind(self, key: str, provider_id: str):
        if not provider_id:
            raise UnsafeDispatch("Missing Hatchet WorkflowRun ID")
        with self.tx() as c:
            row = c.execute(
                "SELECT run_id,state FROM harness_outbox WHERE command_key=%s FOR UPDATE",
                (key,),
            ).fetchone()
            if not row or row[1] != "DISPATCHING":
                raise UnsafeDispatch("Unexpected outbox state")
            c.execute("UPDATE harness_run SET state='RUNNING',provider_workflow_id=%s "
                      "WHERE id=%s AND state='CREATED'", (provider_id, row[0]))
            c.execute("UPDATE harness_outbox SET state='CONFIRMED' "
                      "WHERE command_key=%s", (key,))
            self.event(c, row[0], "workflow.bound",
                       {"provider_workflow_run_id": provider_id})

    def unknown(self, key: str):
        with self.tx() as c:
            row = c.execute(
                "SELECT run_id,state FROM harness_outbox WHERE command_key=%s FOR UPDATE",
                (key,),
            ).fetchone()
            if row and row[1] == "DISPATCHING":
                c.execute("UPDATE harness_outbox SET state='BLOCKED_UNKNOWN' "
                          "WHERE command_key=%s", (key,))
                self.event(c, row[0], "workflow.unknown", {"command_key": key})

    def start_step(self, rid: str, name: str, value: str) -> str | None:
        with self.tx() as c:
            # Acquire the parent Run serialization lock before Step locks.
            run = c.execute("SELECT state FROM harness_run WHERE id=%s FOR UPDATE",
                            (rid,)).fetchone()
            if not run or run[0] not in ("CREATED", "RUNNING"):
                raise UnsafeDispatch("Run is missing or terminal")
            row = c.execute(
                "SELECT state,attempts,input_hash,output FROM harness_step "
                "WHERE run_id=%s AND id=%s FOR UPDATE", (rid, name),
            ).fetchone()
            if row is None:
                raise UnsafeDispatch("Unknown platform Step")
            if row[0] == "COMPLETED":
                if row[2] != sha(value):
                    raise UnsafeDispatch("Completed Step input mismatch")
                return row[3]  # cached PURE result; never rerun completed SDK Step
            if name == "openai":
                parent = c.execute(
                    "SELECT state,output FROM harness_step "
                    "WHERE run_id=%s AND id='pydantic'", (rid,),
                ).fetchone()
                if not parent or parent != ("COMPLETED", value):
                    raise UnsafeDispatch("Verified parent output is required")
            c.execute("UPDATE harness_step SET state='RUNNING',attempts=%s,"
                      "input_hash=%s WHERE run_id=%s AND id=%s",
                      (row[1] + 1, sha(value), rid, name))
            self.event(c, rid, "step.started",
                       {"step_id": name, "attempt": row[1] + 1})
            return None

    def finish_step(self, rid: str, name: str, output: str, events: list):
        if not events or events[-1].type != "run.completed":
            raise UnsafeDispatch("AgentRuntime did not complete successfully")
        with self.tx() as c:
            c.execute("SELECT id FROM harness_run WHERE id=%s FOR UPDATE", (rid,))
            state = c.execute(
                "SELECT state FROM harness_step WHERE run_id=%s AND id=%s FOR UPDATE",
                (rid, name),
            ).fetchone()
            if state != ("RUNNING",):
                raise UnsafeDispatch("Step already committed or never started")
            for e in events:
                # Runtime sub-run terminals are NOT the platform Run terminal.
                self.event(c, rid, "runtime." + e.type,
                           {"step_id": name, "runtime": e.runtime, **e.data})
            c.execute("UPDATE harness_step SET state='COMPLETED',output=%s,"
                      "output_hash=%s WHERE run_id=%s AND id=%s",
                      (output, sha(output), rid, name))
            self.event(c, rid, "step.completed",
                       {"step_id": name, "output_digest": sha(output)})

    def complete(self, rid: str) -> dict[str, str]:
        with self.tx() as c:
            run = c.execute(
                "SELECT state,provider_workflow_id FROM harness_run "
                "WHERE id=%s FOR UPDATE", (rid,),
            ).fetchone()
            steps = c.execute(
                "SELECT id,state,output FROM harness_step WHERE run_id=%s",
                (rid,),
            ).fetchall()
            if (not run or run[0] != "RUNNING" or not run[1]
                    or len(steps) != 2
                    or any(s[1] != "COMPLETED" for s in steps)):
                raise UnsafeDispatch("Unverified Steps or missing Workflow binding")
            c.execute("UPDATE harness_run SET state='COMPLETED' WHERE id=%s",
                      (rid,))
            self.event(c, rid, "run.completed",
                       {"provider_workflow_run_id": run[1]})
            return {name: output for name, _, output in steps}

    def report_execution_error(self, rid: str, error_kind: str):
        # Diagnostic only: provider outcome may remain uncertain, not FAILED.
        with self.tx() as c:
            self.event(c, rid, "workflow.observation_error",
                       {"error_kind": error_kind})

    def list_runs(self, limit: int = 20) -> list[dict]:
        if limit < 1 or limit > 100:
            raise ValueError("limit out of bounds")
        with self.tx() as c:
            rows = c.execute(
                "SELECT id,state,plan_version,provider_workflow_id,created_at "
                "FROM harness_run ORDER BY created_at DESC,id DESC LIMIT %s", (limit,),
            ).fetchall()
        return [{"run_id": rid, "state": state, "plan_version": version,
                 "provider_workflow_run_id": provider, "created_at": created.isoformat()}
                for rid, state, version, provider, created in rows]

    def snapshot(self, rid: str) -> dict:
        with self.tx() as c:
            run = c.execute(
                "SELECT plan_version,state,provider_workflow_id FROM harness_run "
                "WHERE id=%s", (rid,),
            ).fetchone()
            steps = c.execute(
                "SELECT id,state,attempts,output_hash,output FROM harness_step "
                "WHERE run_id=%s ORDER BY id", (rid,),
            ).fetchall()
            events = c.execute(
                "SELECT seq,type,data FROM harness_event WHERE run_id=%s ORDER BY seq",
                (rid,),
            ).fetchall()
            outbox = c.execute(
                "SELECT state FROM harness_outbox WHERE run_id=%s", (rid,),
            ).fetchone()
        if not run:
            raise KeyError(rid)
        return {
            "run_id": rid, "plan_version": run[0], "state": run[1],
            "provider_workflow_run_id": run[2], "outbox": outbox[0],
            "steps": {
                name: {"state": state, "attempts": attempts,
                       "digest": digest, "output": output}
                for name, state, attempts, digest, output in steps
            },
            "events": [
                {"seq": seq, "type": kind, "data": data}
                for seq, kind, data in events
            ],
        }