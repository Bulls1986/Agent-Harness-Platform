"""DEV-M3: guarded PostgreSQL Plan v1 → v2 and independent Workflow Segment.

Not a second scheduler. The Hatchet adapter MUST observe the actual prior
WorkflowRun's terminal state; cancellation requests/ACKs never qualify.
This adapter permits synthetic PURE Runs or explicitly reconciled non-PURE
receipts from HC-02. It does not replace the production Tool authority.
"""
from __future__ import annotations

from enum import Enum
from typing import Callable
import json

from poc.closed_loop.facts import sha

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

        with self.facts.tx() as c:
            c.execute("ALTER TABLE harness_replan_segment_v2 ADD COLUMN IF NOT EXISTS "
                      "effect_policy TEXT NOT NULL DEFAULT 'PURE_ONLY'")

        # v2 business facts are not another Engine history. Existing v1 POC
        # Step table stays intact for compatibility with running deployments.
        with self.facts.tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_plan_step (
                    run_id TEXT NOT NULL REFERENCES harness_run(id),
                    plan_version INTEGER NOT NULL CHECK (plan_version >= 2),
                    step_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('PENDING','RUNNING','COMPLETED')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    input_hash TEXT, output TEXT, output_hash TEXT,
                    PRIMARY KEY (run_id,plan_version,step_id)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_plan_step_attempt (
                    run_id TEXT NOT NULL,
                    plan_version INTEGER NOT NULL,
                    step_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL CHECK (ordinal >= 1),
                    attempt_id TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL CHECK (state IN ('RUNNING','COMPLETED')),
                    PRIMARY KEY (run_id,plan_version,step_id,ordinal),
                    FOREIGN KEY (run_id,plan_version,step_id) REFERENCES
                        harness_plan_step(run_id,plan_version,step_id)
                )
            """)

            # Backward compatible M3 v1 Attempt status migration. An old
            # completed Provider may leave an uncommitted PURE Step callback;
            # only verified quiescence can mark that Attempt SUPERSEDED.
            old_check = c.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='harness_step_attempt'::regclass "
                "AND conname='harness_step_attempt_state_check'",
            ).fetchone()
            if old_check and "SUPERSEDED" not in old_check[0]:
                c.execute(
                    "ALTER TABLE harness_step_attempt DROP CONSTRAINT "
                    "harness_step_attempt_state_check"
                )
                c.execute(
                    "ALTER TABLE harness_step_attempt ADD CONSTRAINT "
                    "harness_step_attempt_state_check "
                    "CHECK (state IN ('RUNNING','COMPLETED','SUPERSEDED'))"
                )

    @staticmethod
    def _checked_receipts(c, rid: str, policy: str) -> list[dict]:
        """Read only durable, externally reconciled M4 Receipt facts.

        Never infer external success from Hatchet success or from an
        idempotency key alone. Any UNKNOWN, DISPATCHED, or v2 intent blocks.
        """
        exists = c.execute(
            "SELECT to_regclass('harness_tool_intent') IS NOT NULL",
        ).fetchone()[0]
        rows = (c.execute(
            "SELECT execution_id,plan_version,state,external_reference "
            "FROM harness_tool_intent WHERE run_id=%s ORDER BY execution_id",
            (rid,),
        ).fetchall() if exists else [])
        if policy == "PURE_ONLY":
            if rows:
                raise UnsafeDispatch("Non-PURE Tool Intent forbids PURE Replan")
            return []
        if policy != "CONFIRMED_RECEIPTS_ONLY":
            raise UnsafeDispatch("Unsupported Replan effect policy")
        if not rows or any(pv != 1 or state != "CONFIRMED_SUCCESS" or not ref
                           for _,pv,state,ref in rows):
            raise UnsafeDispatch("Unresolved/non-v1 Tool Receipt blocks non-PURE Replan")
        return [{"execution_id":execution,"external_reference":ref}
                for execution,_,_,ref in rows]

    def promote(self, rid: str, lookup_status: Callable[[str], Enum],
                *, effect_policy: str = "PURE_ONLY",
                resolve_inflight_pure: bool = False) -> str:
        """Only verified terminal Provider + frozen effect policy permits v2.

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
                    "SELECT command_key,effect_policy FROM harness_replan_segment_v2 "
                    "WHERE run_id=%s", (rid,),
                ).fetchone()
                if existing:
                    if existing[1] != effect_policy:
                        raise UnsafeDispatch("Frozen effect policy cannot be changed")
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
            old_running = c.execute(
                "SELECT id,attempts FROM harness_step "
                "WHERE run_id=%s AND state='RUNNING' FOR UPDATE", (rid,),
            ).fetchall()
            inflight_attempts = c.execute(
                "SELECT step_id,ordinal,attempt_id FROM harness_step_attempt "
                "WHERE run_id=%s AND state='RUNNING' FOR UPDATE", (rid,),
            ).fetchall()
            if old_running or inflight_attempts:
                if not resolve_inflight_pure or effect_policy != "PURE_ONLY":
                    raise UnsafeDispatch("Old active Attempt blocks Replan")
                # Under actual old Provider COMPLETED and Run lock, the
                # pure model Step may be abandoned, not retried in place.
                # Missing/mismatched historical facts cannot be inferred.
                pairs = {(step,ordinal) for step,ordinal,_ in inflight_attempts}
                if (len(old_running) != len(inflight_attempts)
                        or any((step,ordinal) not in pairs
                               for step,ordinal in old_running)):
                    raise UnsafeDispatch("Cannot prove original Attempt identity")
            # Provider COMPLETED does not prove an external Tool occurred
            # safely: only an explicit policy and confirmed independent M4
            # receipt facts may release a non-PURE continuation.
            self._checked_receipts(c, rid, effect_policy)
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
            for step_id,ordinal,attempt in inflight_attempts:
                c.execute(
                    "UPDATE harness_step_attempt SET state='SUPERSEDED' "
                    "WHERE run_id=%s AND step_id=%s AND ordinal=%s "
                    "AND attempt_id=%s AND state='RUNNING'",
                    (rid,step_id,ordinal,attempt),
                )
                c.execute(
                    "UPDATE harness_step SET state='SUPERSEDED' "
                    "WHERE run_id=%s AND id=%s AND state='RUNNING'",
                    (rid,step_id),
                )
                self.facts.event(c,rid,"step.superseded",
                    {"step_id":step_id,"attempt_id":attempt,
                     "from_plan_version":1,
                     "evidence":"PROVIDER_COMPLETED_PURE_NO_EXTERNAL_TOOL"})
            key = f"{rid}:segment-1:create:v2"
            c.execute(
                "INSERT INTO harness_plan_snapshot(run_id,version,recipe_digest,provider_workflow_id) "
                "VALUES (%s,2,%s,NULL)", (rid, intent[0]),
            )
            c.execute(
                "INSERT INTO harness_replan_segment_v2 "
                "(run_id,from_provider_workflow_id,recipe_digest,command_key,state,observed_provider_status,effect_policy) "
                "VALUES (%s,%s,%s,%s,'PENDING','COMPLETED',%s)",
                (rid, old_provider_id, intent[0], key, effect_policy),
            )
            c.execute("INSERT INTO harness_plan_step(run_id,plan_version,step_id,state) "
                      "VALUES (%s,2,'verifier','PENDING')", (rid,))
            c.execute("UPDATE harness_run SET plan_version=2 WHERE id=%s", (rid,))
            self.facts.event(c, rid, "plan.replan.committed",
                             {"from_version":1,"to_version":2,
                              "old_provider_workflow_id":old_provider_id,
                              "effect_policy":effect_policy,
                              "new_segment_state":"PENDING"})
        return key

    @staticmethod
    def _lock_live_segment_owner(c, key: str) -> str:
        # Run -> Segment is the global lock order for all M3/M4 writers.
        row = c.execute(
            "SELECT run_id FROM harness_replan_segment_v2 WHERE command_key=%s",
            (key,),
        ).fetchone()
        if not row:
            raise UnsafeDispatch("Unknown Replan Segment")
        run = c.execute(
            "SELECT state,plan_version FROM harness_run WHERE id=%s FOR UPDATE",
            (row[0],),
        ).fetchone()
        if run != ("RUNNING",2):
            raise UnsafeDispatch("Cancelled or stale Run forbids v2 dispatch/binding")
        return row[0]

    def claim(self, key: str):
        with self.facts.tx() as c:
            rid = self._lock_live_segment_owner(c,key)
            row = c.execute(
                "SELECT run_id,state FROM harness_replan_segment_v2 "
                "WHERE command_key=%s FOR UPDATE", (key,),
            ).fetchone()
            if row != (rid, "PENDING"):
                raise UnsafeDispatch("Replan segment dispatch uncertain or already claimed")
            c.execute("UPDATE harness_replan_segment_v2 SET state='DISPATCHING' "
                      "WHERE command_key=%s", (key,))
            self.facts.event(c, row[0], "workflow.segment.dispatching", {"command_key":key})

    def bind(self, key: str, provider_workflow_id: str):
        if not isinstance(provider_workflow_id, str) or not provider_workflow_id.strip():
            raise UnsafeDispatch("Real new Provider WorkflowRun ID required")
        with self.facts.tx() as c:
            rid = self._lock_live_segment_owner(c,key)
            row = c.execute(
                "SELECT run_id,state,from_provider_workflow_id FROM harness_replan_segment_v2 "
                "WHERE command_key=%s FOR UPDATE", (key,),
            ).fetchone()
            if not row or row[0] != rid or row[1] != "DISPATCHING" or provider_workflow_id == row[2]:
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
            identity = c.execute(
                "SELECT run_id FROM harness_replan_segment_v2 WHERE command_key=%s",
                (key,),
            ).fetchone()
            if not identity:
                return
            # Run -> Segment lock ordering is required under competing Cancel,
            # Binding and reconciliation; unknown observations may arrive late.
            run = c.execute(
                "SELECT state FROM harness_run WHERE id=%s FOR UPDATE",
                (identity[0],),
            ).fetchone()
            row = c.execute(
                "SELECT run_id,state FROM harness_replan_segment_v2 "
                "WHERE command_key=%s FOR UPDATE", (key,),
            ).fetchone()
            if row and row[1] == "DISPATCHING":
                c.execute("UPDATE harness_replan_segment_v2 SET state='BLOCKED_UNKNOWN' "
                          "WHERE command_key=%s", (key,))
                # Terminal Run business history is immutable. Persist the
                # uncertain technical Binding without appending business event.
                if run and run[0] not in ("COMPLETED","CANCELLED","FAILED","ABORTED"):
                    self.facts.event(c, row[0], "workflow.segment.unknown",
                                     {"command_key":key})

    def segment(self, rid: str) -> dict | None:
        with self.facts.tx() as c:
            r = c.execute(
                "SELECT state,command_key,provider_workflow_id,from_provider_workflow_id,effect_policy "
                "FROM harness_replan_segment_v2 WHERE run_id=%s", (rid,),
            ).fetchone()
        if r is None:
            return None
        return dict(zip(("state","command_key","provider_workflow_id",
                         "from_provider_workflow_id","effect_policy"),r))

    @staticmethod
    def _check_v2_binding(c, rid: str, version: int, provider: str) -> None:
        # Must be called under the Run row lock; cancellation and provider
        # transitions serialize against every business fact mutation.
        run = c.execute(
            "SELECT state,plan_version FROM harness_run WHERE id=%s FOR UPDATE",
            (rid,),
        ).fetchone()
        segment = c.execute(
            "SELECT state,provider_workflow_id FROM harness_replan_segment_v2 "
            "WHERE run_id=%s", (rid,),
        ).fetchone()
        plan = c.execute(
            "SELECT provider_workflow_id FROM harness_plan_snapshot "
            "WHERE run_id=%s AND version=2", (rid,),
        ).fetchone()
        if (run != ("RUNNING", 2) or version != 2
                or not isinstance(provider, str) or not provider
                or segment != ("CONFIRMED", provider)
                or plan != (provider,)):
            raise UnsafeDispatch("Stale Run/Plan or unconfirmed v2 Provider binding")

    def start_step(self, rid: str, version: int, provider: str,
                   step_id: str, value: str, attempt_id: str) -> str | None:
        self.facts.validate_attempt_id(attempt_id)
        if step_id != "verifier" or not isinstance(value, str):
            raise UnsafeDispatch("Only frozen v2 verifier Step supported")
        with self.facts.tx() as c:
            self._check_v2_binding(c, rid, version, provider)
            row = c.execute(
                "SELECT state,attempts,input_hash,output FROM harness_plan_step "
                "WHERE run_id=%s AND plan_version=2 AND step_id=%s FOR UPDATE",
                (rid, step_id),
            ).fetchone()
            if not row:
                raise UnsafeDispatch("Unknown v2 Step")
            if row[0] == "COMPLETED":
                if row[2] != sha(value):
                    raise UnsafeDispatch("Completed v2 Step input drift")
                return row[3]
            # A Provider native retry must never become a second business
            # Attempt until verified termination + side effects reconciliation.
            if row[0] != "PENDING" or row[1] != 0:
                raise UnsafeDispatch("v2 Step already executing; reconcile first")
            c.execute(
                "INSERT INTO harness_plan_step_attempt "
                "(run_id,plan_version,step_id,ordinal,attempt_id,state) "
                "VALUES (%s,2,%s,1,%s,'RUNNING')",
                (rid,step_id,attempt_id),
            )
            c.execute(
                "UPDATE harness_plan_step SET state='RUNNING',attempts=1,"
                "input_hash=%s WHERE run_id=%s AND plan_version=2 AND step_id=%s",
                (sha(value),rid,step_id),
            )
            self.facts.event(c,rid,"step.started",
                {"step_id":step_id,"plan_version":2,"attempt":1,
                 "attempt_id":attempt_id,"provider_workflow_run_id":provider})
            return None

    def finish_step(self, rid: str, version: int, provider: str,
                    step_id: str, attempt_id: str, output: str) -> None:
        self.facts.validate_attempt_id(attempt_id)
        if step_id != "verifier" or not isinstance(output, str):
            raise UnsafeDispatch("Unsupported v2 Step result")
        with self.facts.tx() as c:
            self._check_v2_binding(c,rid,version,provider)
            step = c.execute(
                "SELECT state,attempts FROM harness_plan_step "
                "WHERE run_id=%s AND plan_version=2 AND step_id=%s FOR UPDATE",
                (rid,step_id),
            ).fetchone()
            if step != ("RUNNING",1):
                raise UnsafeDispatch("v2 Step not running or already complete")
            active = c.execute(
                "SELECT attempt_id,state FROM harness_plan_step_attempt "
                "WHERE run_id=%s AND plan_version=2 AND step_id=%s "
                "AND ordinal=1 FOR UPDATE", (rid,step_id),
            ).fetchone()
            if active != (attempt_id,"RUNNING"):
                raise UnsafeDispatch("Stale or mismatched v2 Attempt")
            c.execute(
                "UPDATE harness_plan_step_attempt SET state='COMPLETED' "
                "WHERE run_id=%s AND plan_version=2 AND step_id=%s AND ordinal=1",
                (rid,step_id),
            )
            c.execute(
                "UPDATE harness_plan_step SET state='COMPLETED',output=%s,output_hash=%s "
                "WHERE run_id=%s AND plan_version=2 AND step_id=%s",
                (output,sha(output),rid,step_id),
            )
            self.facts.event(c,rid,"step.completed",
                {"step_id":step_id,"plan_version":2,
                 "attempt_id":attempt_id,"output_digest":sha(output)})

    def complete(self, rid: str, version: int, provider: str,
                 *, verified_outputs: dict[str,str]) -> dict:
        """Terminal only after native success AND matching persisted verifier."""
        with self.facts.tx() as c:
            self._check_v2_binding(c,rid,version,provider)
            run = c.execute(
                "SELECT model_mode,model_id FROM harness_run WHERE id=%s",
                (rid,),
            ).fetchone()
            if run is None or run[0] != "deterministic_local_model":
                raise UnsafeDispatch("Only model-only v2 completion is supported")
            segment = c.execute(
                "SELECT effect_policy FROM harness_replan_segment_v2 WHERE run_id=%s",
                (rid,),
            ).fetchone()
            if not segment:
                raise UnsafeDispatch("Missing frozen Replan effect policy")
            receipt_refs = self._checked_receipts(c,rid,segment[0])
            steps = c.execute(
                "SELECT step_id,state,output,attempts FROM harness_plan_step "
                "WHERE run_id=%s AND plan_version=2 ORDER BY step_id", (rid,),
            ).fetchall()
            if (len(steps)!=1 or steps[0][0]!="verifier"
                    or steps[0][1]!="COMPLETED" or steps[0][3]!=1
                    or not isinstance(verified_outputs,dict)
                    or verified_outputs!={"verifier":steps[0][2]}):
                raise UnsafeDispatch("Missing or inconsistent verified v2 Step result")
            accepted = c.execute(
                "SELECT attempt_id,state FROM harness_plan_step_attempt "
                "WHERE run_id=%s AND plan_version=2 AND step_id='verifier'",
                (rid,),
            ).fetchall()
            if len(accepted)!=1 or accepted[0][1]!="COMPLETED":
                raise UnsafeDispatch("v2 terminal missing persisted Attempt receipt")
            result = {"final_output":steps[0][2],"plan_version":2,
                      "result_source_step":"verifier",
                      "provider_workflow_run_id":provider,
                      "step_outputs":{"verifier":steps[0][2]},
                      "mode":run[0],"model_id":run[1],
                      "side_effect_policy":segment[0],
                      "reconciled_receipts":receipt_refs}
            c.execute("UPDATE harness_run SET state='COMPLETED',result_json=%s::jsonb "
                      "WHERE id=%s", (json.dumps(result),rid))
            self.facts.event(c,rid,"run.completed",
                             {"plan_version":2,"provider_workflow_run_id":provider,
                              "result_source_step":"verifier"})
            return result

    def step_facts(self, rid: str, version: int) -> dict:
        if version != 2:
            raise ValueError("Only v2 Segment facts supported")
        with self.facts.tx() as c:
            records = c.execute(
                "SELECT step_id,state,output,attempts FROM harness_plan_step "
                "WHERE run_id=%s AND plan_version=%s ORDER BY step_id", (rid,version),
            ).fetchall()
            attempts = c.execute(
                "SELECT step_id,attempt_id,ordinal,plan_version,state "
                "FROM harness_plan_step_attempt WHERE run_id=%s AND plan_version=%s "
                "ORDER BY step_id,ordinal", (rid,version),
            ).fetchall()
        grouped = {step:{"state":state,"output":output,"attempt_count":count,
                         "attempts":[]} for step,state,output,count in records}
        for step,aid,ordinal,pv,state in attempts:
            if step in grouped:
                grouped[step]["attempts"].append(
                    {"attempt_id":aid,"ordinal":ordinal,"plan_version":pv,"state":state})
        return grouped

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