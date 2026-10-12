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
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    input_prompt TEXT, result_json JSONB,
                    model_mode TEXT NOT NULL DEFAULT 'deterministic_local_model',
                    model_id TEXT,
                    project_scope TEXT,
                    initiator_principal_id TEXT
                )
            """)
            c.execute("ALTER TABLE harness_run ADD COLUMN IF NOT EXISTS "
                      "created_at TIMESTAMPTZ NOT NULL DEFAULT now()")
            # Backward-compatible POC migration for persisted existing Runs.
            c.execute("ALTER TABLE harness_run ADD COLUMN IF NOT EXISTS input_prompt TEXT")
            c.execute("ALTER TABLE harness_run ADD COLUMN IF NOT EXISTS result_json JSONB")
            c.execute("ALTER TABLE harness_run ADD COLUMN IF NOT EXISTS model_mode "
                      "TEXT NOT NULL DEFAULT 'deterministic_local_model'")
            c.execute("ALTER TABLE harness_run ADD COLUMN IF NOT EXISTS model_id TEXT")
            # Legacy POC Runs remain unscoped and MUST NOT be made externally
            # readable by backfilling a project or deriving owner from prompt.
            c.execute("ALTER TABLE harness_run ADD COLUMN IF NOT EXISTS project_scope TEXT")
            c.execute("ALTER TABLE harness_run ADD COLUMN IF NOT EXISTS initiator_principal_id TEXT")
            c.execute("""
                CREATE OR REPLACE FUNCTION harness_reject_run_owner_change()
                RETURNS trigger
                LANGUAGE plpgsql
                AS $owner_guard$
                BEGIN
                    IF NEW.project_scope IS DISTINCT FROM OLD.project_scope
                       OR NEW.initiator_principal_id IS DISTINCT FROM OLD.initiator_principal_id
                    THEN
                        RAISE EXCEPTION 'Persisted Run ownership is immutable'
                            USING ERRCODE = '23514';
                    END IF;
                    RETURN NEW;
                END
                $owner_guard$
            """)
            c.execute("""
                DO $create_owner_guard$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_trigger
                        WHERE tgname='harness_run_owner_immutable'
                          AND tgrelid='harness_run'::regclass
                    ) THEN
                        CREATE TRIGGER harness_run_owner_immutable
                        BEFORE UPDATE OF project_scope, initiator_principal_id
                        ON harness_run
                        FOR EACH ROW EXECUTE FUNCTION harness_reject_run_owner_change();
                    END IF;
                END
                $create_owner_guard$
            """)
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

    @staticmethod
    def has_non_pure_tool_intent(c, rid: str) -> bool:
        """Avoid PURE-only Run completion/cancel when non-PURE Tool exists.

        Test POC schema may not have the new M4 journal installed yet.
        Run row must be locked by the caller to serialize intent insertions.
        """
        # Native OpenCode Shell is also an external side effect. It must not
        # be ignored just because the optional M4 Tool Intent journal was
        # never installed for this synthetic Run.
        if c.execute(
            "SELECT to_regclass('harness_cube_guest_effect') IS NOT NULL"
        ).fetchone()[0]:
            if c.execute(
                "SELECT 1 FROM harness_cube_guest_effect AS effect "
                "JOIN harness_cube_binding AS binding "
                "ON binding.execution_id=effect.execution_id "
                "WHERE binding.run_id=%s LIMIT 1", (rid,),
            ).fetchone():
                return True
        if not c.execute(
            "SELECT to_regclass('harness_tool_intent') IS NOT NULL"
        ).fetchone()[0]:
            return False
        return bool(c.execute(
            "SELECT 1 FROM harness_tool_intent WHERE run_id=%s LIMIT 1",
            (rid,),
        ).fetchone())

    def create(self, rid: str, prompt: str | None = None,
               model_mode: str = 'deterministic_local_model',
               model_id: str | None = None,
               *, project_scope: str | None = None,
               initiator_principal_id: str | None = None) -> str:
        # Prompt is only kept for local Inspector diagnosis; never forward
        # this POC plain-text input storage practice to production secrets.
        key = f"{rid}:segment-0:create:v1"
        # A trusted calling service supplies BOTH immutable ownership facts.
        # None/None is retained solely for historical local Inspector POC Runs.
        owner = (project_scope, initiator_principal_id)
        if owner != (None, None) and (
            not all(isinstance(v, str) and v and v == v.strip() for v in owner)
        ):
            raise ValueError("Scoped Run requires project and initiator identity")
        with self.tx() as c:
            if model_mode not in ('deterministic_local_model', 'live'):
                raise ValueError('Unsupported POC model mode')
            if model_mode == 'live' and not model_id:
                raise ValueError('Live Run requires pinned model')
            c.execute("INSERT INTO harness_run("
                      "id,plan_version,state,input_prompt,model_mode,model_id,"
                      "project_scope,initiator_principal_id) "
                      "VALUES (%s,1,'CREATED',%s,%s,%s,%s,%s)",
                      (rid, prompt, model_mode, model_id,
                       project_scope, initiator_principal_id))
            for name in ("pydantic", "openai"):
                c.execute("INSERT INTO harness_step(run_id,id,state) "
                          "VALUES (%s,%s,'PENDING')", (rid, name))
            c.execute("INSERT INTO harness_outbox VALUES (%s,%s,'PENDING')",
                      (key, rid))
            self.event(c, rid, "run.created", {"plan_version": 1})
        return key

    def assert_model_binding(self, rid: str, mode: str, model_id: str | None):
        with self.tx() as c:
            row = c.execute("SELECT model_mode,model_id FROM harness_run WHERE id=%s", (rid,)).fetchone()
        if row != (mode, model_id):
            raise UnsafeDispatch('Model mode/name changed during frozen Run')

    def events_since(self, rid: str, after: int = 0, limit: int = 250) -> list[dict]:
        if after < 0 or not 1 <= limit <= 500:
            raise ValueError('Invalid stream event cursor')
        with self.tx() as c:
            if not c.execute('SELECT 1 FROM harness_run WHERE id=%s', (rid,)).fetchone():
                raise KeyError(rid)
            records = c.execute('SELECT seq,type,data FROM harness_event '
                                'WHERE run_id=%s AND seq>%s ORDER BY seq LIMIT %s',
                                (rid, after, limit)).fetchall()
        return [{'seq': seq, 'type': kind, 'data': data} for seq,kind,data in records]

    def run_state(self, rid: str) -> str:
        with self.tx() as c:
            row = c.execute('SELECT state FROM harness_run WHERE id=%s', (rid,)).fetchone()
        if not row: raise KeyError(rid)
        return row[0]

    def cancel_requested(self, rid: str) -> bool:
        return self.run_state(rid) in ('CANCEL_REQUESTED','CANCELLED')

    def request_cancel(self, rid: str) -> str:
        with self.tx() as c:
            row = c.execute('SELECT state FROM harness_run WHERE id=%s FOR UPDATE',(rid,)).fetchone()
            if not row: raise KeyError(rid)
            if row[0] == 'CANCEL_REQUESTED': return row[0]
            if row[0] != 'RUNNING':
                raise UnsafeDispatch('Can cancel only a running model-only Run')
            c.execute("UPDATE harness_run SET state='CANCEL_REQUESTED' WHERE id=%s",(rid,))
            self.event(c,rid,'run.cancel.requested',{'reason':'user_requested'})
        return 'CANCEL_REQUESTED'

    def acknowledge_cancel(self, rid: str):
        with self.tx() as c:
            row=c.execute('SELECT state FROM harness_run WHERE id=%s FOR UPDATE',(rid,)).fetchone()
            if not row or row[0]!='CANCEL_REQUESTED':
                raise UnsafeDispatch('Cancellation cannot be acknowledged without request')
            if self.has_non_pure_tool_intent(c,rid):
                raise UnsafeDispatch('Model-only Cancel ACK cannot finalize a Run with external Tool Intent')
            c.execute("UPDATE harness_run SET state='CANCELLED' WHERE id=%s",(rid,))
            self.event(c,rid,'run.cancelled',{'side_effects':'NO_EXTERNAL_TOOLS_MODEL_ONLY'})

    def append_stream_delta(self, rid: str, step: str, delta: str, runtime: str):
        if not isinstance(delta,str) or not delta or len(delta.encode('utf-8'))>8192:
            raise ValueError('Invalid model text delta')
        if step not in ('pydantic','openai'):
            raise ValueError('Unknown stream Step')
        with self.tx() as c:
            row=c.execute('SELECT state,model_mode FROM harness_run WHERE id=%s FOR UPDATE',(rid,)).fetchone()
            if row != ('RUNNING','live'):
                raise UnsafeDispatch('Only active Live Runs accept model-stream events')
            sr=c.execute('SELECT state FROM harness_step WHERE run_id=%s AND id=%s',(rid,step)).fetchone()
            if sr!=('RUNNING',): raise UnsafeDispatch('Step is not actively streaming')
            self.event(c,rid,'response.output_text.delta',
                       {'step_id':step,'runtime':runtime,'delta':delta,'source':'provider_stream'})

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
            run = c.execute("SELECT state,input_prompt,plan_version FROM harness_run WHERE id=%s FOR UPDATE",
                            (rid,)).fetchone()
            if not run or run[0] not in ("CREATED", "RUNNING") or run[2] != 1:
                raise UnsafeDispatch("Run is missing, terminal or an old Plan version")
            # Old workflow cannot launch NEW work after a frozen Replan intent.
            if c.execute("SELECT 1 FROM information_schema.tables "
                         "WHERE table_schema=current_schema() AND table_name='harness_replan_intent'"
                         ).fetchone() and c.execute(
                "SELECT 1 FROM harness_replan_intent WHERE run_id=%s AND from_version=1",
                (rid,),
            ).fetchone():
                raise UnsafeDispatch("Old Plan cannot start a Step after Replan request")
            if name == "pydantic" and run[1] is not None and run[1] != value:
                raise UnsafeDispatch("Step A input differs from frozen original Prompt")
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
            active = c.execute("SELECT plan_version FROM harness_run "
                               "WHERE id=%s FOR UPDATE", (rid,)).fetchone()
            if active != (1,):
                raise UnsafeDispatch("Stale Plan/Attempt cannot commit after Replan")
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

    def complete(self, rid: str, *, verified_outputs: dict[str, str] | None = None) -> dict[str, str]:
        with self.tx() as c:
            run = c.execute(
                "SELECT state,provider_workflow_id,model_mode,model_id,plan_version FROM harness_run "
                "WHERE id=%s FOR UPDATE", (rid,),
            ).fetchone()
            steps = c.execute(
                "SELECT id,state,output FROM harness_step WHERE run_id=%s",
                (rid,),
            ).fetchall()
            if self.has_non_pure_tool_intent(c,rid):
                raise UnsafeDispatch("Model-only Run terminal cannot ignore non-PURE Tool Receipt")
            if (not run or run[0] != "RUNNING" or not run[1] or run[4] != 1
                    or len(steps) != 2
                    or any(s[1] != "COMPLETED" for s in steps)):
                raise UnsafeDispatch("Unverified Steps or missing Workflow binding")
            output_by_step = {name: output for name, _, output in steps}
            # The Model/Verifier owns the business schema, but Harness must
            # still demand an explicit, matching Verification evidence for
            # every step in a Live Run before making a domain terminal fact.
            if run[2] == 'live' and (
                verified_outputs is None or verified_outputs != output_by_step
            ):
                raise UnsafeDispatch('Live Run missing verified Step outputs')
            result = {
                "final_output": output_by_step["openai"],
                "result_source_step": "openai",
                "step_outputs": output_by_step,
                "mode": run[2], "model_id": run[3],
            }
            c.execute("UPDATE harness_run SET state='COMPLETED',result_json=%s::jsonb "
                      "WHERE id=%s", (json.dumps(result), rid))
            self.event(c, rid, "run.completed",
                       {"provider_workflow_run_id": run[1],
                        "result_source_step": "openai"})
            return output_by_step

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
                "SELECT plan_version,state,provider_workflow_id,input_prompt,result_json,model_mode,model_id "
                "FROM harness_run WHERE id=%s", (rid,),
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
        step_values = {name: {"state": state, "attempts": attempts,
                              "digest": digest, "output": output}
                       for name, state, attempts, digest, output in steps}
        if "pydantic" in step_values:
            step_values["pydantic"]["input"] = run[3]
        if "openai" in step_values:
            parent = step_values.get("pydantic", {})
            step_values["openai"]["input"] = (
                parent.get("output") if step_values["openai"]["attempts"] else None
            )
        # A pre-migration Run did not persist its final result; derive only
        # from its actual committed Step B result, explicitly marking legacy.
        result = run[4]
        if result is None and run[1] == "COMPLETED" and step_values.get("openai", {}).get("output") is not None:
            result = {"final_output": step_values["openai"]["output"],
                      "result_source_step": "openai", "mode": "deterministic_local_model",
                      "provenance": "derived_legacy_step"}
        return {
            "run_id": rid, "plan_version": run[0], "state": run[1],
            "provider_workflow_run_id": run[2], "outbox": outbox[0],
            "input_prompt": run[3], "model_mode": run[5],
            "model_id": run[6], "result": result,
            "steps": step_values,
            "events": [
                {"seq": seq, "type": kind, "data": data}
                for seq, kind, data in events
            ],
        }
