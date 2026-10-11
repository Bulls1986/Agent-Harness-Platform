"""DEV-M3: guarded PostgreSQL Plan v1 → v2 and independent Workflow Segment.

Not a second scheduler. The Hatchet adapter MUST observe the actual prior
WorkflowRun's terminal state; cancellation requests/ACKs never qualify.
This limited implementation only releases deterministic model-only PURE Runs
and is not a production HC-02 Receipt/side-effect reconciler.
"""
from __future__ import annotations

from enum import Enum
from typing import Callable

from poc.closed_loop.facts import PgFacts, UnsafeDispatch


class ReplanV2:
    def __init__(self, facts: PgFacts):
        self.facts = facts
        self.init_schema()

    def init_schema(self):
        with self.facts.tx() as c:
            # A Plan is frozen before Hatchet returns a Provider Workflow ID.
            # Old v1 rows retain their existing NOT NULL binding.
            c.execute("ALTER TABLE harness_plan_snapshot "
                      "ALTER COLUMN provider_workflow_id DROP NOT NULL")
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_replan_segment_v2 (
                    run_id TEXT PRIMARY KEY REFERENCES harness_run(id),
                    from_provider_workflow_id TEXT NOT NULL,
                    recipe_digest TEXT NOT NULL,
                    command_key TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL CHECK (state IN
                        ('PENDING','DISPATCHING','CONFIRMED','BLOCKED_UNKNOWN')),
                    provider_workflow_id TEXT UNIQUE,
                    observed_provider_status TEXT NOT NULL
                        CHECK (observed_provider_status='COMPLETED'),
                    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)

    def promote(self, rid: str, lookup_status: Callable[[str], Enum]) -> str:
        """Only real, terminal COMPLETED provider state permits v2 for PURE runs.

        Inject a TRUSTED SDK adapter bound to the provider workflow; never use
        a user-supplied status. The double DB check prevents a changed Run/
        Provider/intent between the native lookup and the commit.
        """
        with self.facts.tx() as c:
            r = c.execute(
                "SELECT plan_version,state,provider_workflow_id,model_mode "
                "FROM harness_run WHERE id=%s", (rid,),
            ).fetchone()
            if r and r[0] == 2:
                existing = c.execute(
                    "SELECT command_key,recipe_digest FROM harness_replan_segment_v2 "
                    "WHERE run_id=%s", (rid,),
                ).fetchone()
                if existing:
                    return existing[0]  # idempotent: never trigger a new provider
            if not r or r[0] != 1 or r[1] != "RUNNING" or not r[2] or r[3] != "deterministic_local_model":
                raise UnsafeDispatch("Cannot promote without active PURE Plan v1")
            old_provider_id = r[2]
        try:
            provider_state = lookup_status(old_provider_id)
        except Exception:
            raise UnsafeDispatch("Provider terminal lookup unavailable; block Replan") from None
        # Literal strings / untyped external assertions are not trusted proof.
        if not isinstance(provider_state, Enum) or provider_state.value != "COMPLETED":
            raise UnsafeDispatch("Old Provider not proven COMPLETED; cancellation ACK is insufficient")

        with self.facts.tx() as c:
            run = c.execute(
                "SELECT plan_version,state,provider_workflow_id,model_mode "
                "FROM harness_run WHERE id=%s FOR UPDATE", (rid,),
            ).fetchone()
            if run != (1, "RUNNING", old_provider_id, "deterministic_local_model"):
                raise UnsafeDispatch("Provider/Run changed since terminal check")
            if c.execute(
                "SELECT 1 FROM harness_step WHERE run_id=%s AND state='RUNNING'", (rid,),
            ).fetchone():
                raise UnsafeDispatch("Step still RUNNING; quiescence not proven")
            # "deterministic model" is not proof of PURE execution. A Run
            # might have registered a non-PURE Tool via another Worker/SDK.
            # The Run row lock serializes Tool Intent registration and Plan
            # promotion. For this limited PURE-v2 adapter ANY such Intent
            # (including an already reconciled Receipt) makes PURE promotion
            # ineligible; non-PURE Replan needs its own HC-02/03 Gate.
            exists = c.execute(
                "SELECT to_regclass('harness_tool_intent') IS NOT NULL",
            ).fetchone()[0]
            if exists and c.execute(
                "SELECT 1 FROM harness_tool_intent WHERE run_id=%s LIMIT 1",
                (rid,),
            ).fetchone():
                raise UnsafeDispatch("Non-PURE Tool Intent forbids PURE Replan")
            intent = c.execute(
                "SELECT intended_recipe_digest,state FROM harness_replan_intent "
                "WHERE run_id=%s AND from_version=1", (rid,),
            ).fetchone()
            old_plan = c.execute(
                "SELECT recipe_digest,provider_workflow_id FROM harness_plan_snapshot "
                "WHERE run_id=%s AND version=1", (rid,),
            ).fetchone()
            if (not intent or intent[1] != "BLOCKED_PROVIDER_QUIESCENCE"
                    or not old_plan or old_plan[1] != old_provider_id
                    or old_plan[0] == intent[0]):
                raise UnsafeDispatch("Frozen Plan and approved distinct Replan intent required")
            key = f"{rid}:segment-1:create:v2"
            c.execute(
                "INSERT INTO harness_plan_snapshot(run_id,version,recipe_digest,provider_workflow_id) "
                "VALUES (%s,2,%s,NULL)", (rid, intent[0]),
            )
            c.execute(
                "INSERT INTO harness_replan_segment_v2 "
                "(run_id,from_provider_workflow_id,recipe_digest,command_key,state,observed_provider_status) "
                "VALUES (%s,%s,%s,%s,'PENDING','COMPLETED')",
                (rid, old_provider_id, intent[0], key),
            )
            c.execute("UPDATE harness_run SET plan_version=2 WHERE id=%s", (rid,))
            self.facts.event(c, rid, "plan.replan.committed",
                             {"from_version":1,"to_version":2,
                              "old_provider_workflow_id":old_provider_id,
                              "new_segment_state":"PENDING"})
        return key

    def claim(self, key: str):
        with self.facts.tx() as c:
            row = c.execute(
                "SELECT run_id,state FROM harness_replan_segment_v2 "
                "WHERE command_key=%s FOR UPDATE", (key,),
            ).fetchone()
            if not row or row[1] != "PENDING":
                raise UnsafeDispatch("Replan segment dispatch uncertain or already claimed")
            c.execute("UPDATE harness_replan_segment_v2 SET state='DISPATCHING' "
                      "WHERE command_key=%s", (key,))
            self.facts.event(c, row[0], "workflow.segment.dispatching", {"command_key":key})

    def bind(self, key: str, provider_workflow_id: str):
        if not isinstance(provider_workflow_id, str) or not provider_workflow_id.strip():
            raise UnsafeDispatch("Real new Provider WorkflowRun ID required")
        with self.facts.tx() as c:
            row = c.execute(
                "SELECT run_id,state,from_provider_workflow_id FROM harness_replan_segment_v2 "
                "WHERE command_key=%s FOR UPDATE", (key,),
            ).fetchone()
            if not row or row[1] != "DISPATCHING" or provider_workflow_id == row[2]:
                raise UnsafeDispatch("New Segment needs a distinct confirmed Provider WorkflowRun")
            c.execute("UPDATE harness_replan_segment_v2 SET state='CONFIRMED',"
                      "provider_workflow_id=%s WHERE command_key=%s",
                      (provider_workflow_id,key))
            c.execute("UPDATE harness_plan_snapshot SET provider_workflow_id=%s "
                      "WHERE run_id=%s AND version=2 AND provider_workflow_id IS NULL",
                      (provider_workflow_id, row[0]))
            self.facts.event(c, row[0], "workflow.segment.bound",
                             {"version":2, "provider_workflow_run_id":provider_workflow_id})

    def unknown(self, key: str):
        with self.facts.tx() as c:
            row = c.execute(
                "SELECT run_id,state FROM harness_replan_segment_v2 "
                "WHERE command_key=%s FOR UPDATE", (key,),
            ).fetchone()
            if row and row[1] == "DISPATCHING":
                c.execute("UPDATE harness_replan_segment_v2 SET state='BLOCKED_UNKNOWN' "
                          "WHERE command_key=%s", (key,))
                self.facts.event(c, row[0], "workflow.segment.unknown",
                                 {"command_key":key})

    def segment(self, rid: str) -> dict | None:
        with self.facts.tx() as c:
            r = c.execute(
                "SELECT state,command_key,provider_workflow_id,from_provider_workflow_id "
                "FROM harness_replan_segment_v2 WHERE run_id=%s", (rid,),
            ).fetchone()
        if r is None:
            return None
        return dict(zip(("state","command_key","provider_workflow_id",
                         "from_provider_workflow_id"),r))

    def admit(self, rid: str, expected_version: int, provider_workflow_id: str):
        with self.facts.tx() as c:
            r = c.execute(
                "SELECT plan_version,state FROM harness_run WHERE id=%s FOR UPDATE",
                (rid,),
            ).fetchone()
            segment = c.execute(
                "SELECT state,provider_workflow_id FROM harness_replan_segment_v2 "
                "WHERE run_id=%s", (rid,),
            ).fetchone()
            snapshot = c.execute(
                "SELECT provider_workflow_id FROM harness_plan_snapshot "
                "WHERE run_id=%s AND version=2", (rid,),
            ).fetchone()
            if (r != (2, "RUNNING") or expected_version != 2
                    or segment != ("CONFIRMED",provider_workflow_id)
                    or snapshot != (provider_workflow_id,)):
                raise UnsafeDispatch("Unbound, stale or unauthorized v2 Segment")
