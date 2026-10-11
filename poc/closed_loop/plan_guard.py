"""DEV-M3 HC-01: initial Plan freeze + fail-closed Replan intent (PG).

This is a FIRST DOMAIN SLICE, not a Hatchet dynamic workflow adapter.
No new executable Plan/Segment is created until the existing Provider's
quiescence and HC-02 receipt safety have been verified in a future slice.
"""
from __future__ import annotations

from poc.closed_loop.facts import PgFacts, UnsafeDispatch


class PlanGuard:
    def __init__(self, facts: PgFacts):
        self.facts=facts
        self.init_schema()

    def init_schema(self):
        with self.facts.tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_plan_snapshot (
                    run_id TEXT NOT NULL REFERENCES harness_run(id),
                    version INTEGER NOT NULL,
                    recipe_digest TEXT NOT NULL,
                    provider_workflow_id TEXT NOT NULL,
                    PRIMARY KEY (run_id,version)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_replan_intent (
                    run_id TEXT NOT NULL REFERENCES harness_run(id),
                    from_version INTEGER NOT NULL,
                    intended_recipe_digest TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state='BLOCKED_PROVIDER_QUIESCENCE'),
                    PRIMARY KEY(run_id,from_version)
                )
            """)

    def freeze_initial(self, rid: str, recipe_digest: str) -> None:
        if not recipe_digest or not recipe_digest.startswith("sha256:"):
            raise ValueError("Initial plan must have a frozen recipe digest")
        with self.facts.tx() as c:
            run=c.execute(
                "SELECT state,plan_version,provider_workflow_id FROM harness_run "
                "WHERE id=%s FOR UPDATE",(rid,)).fetchone()
            if run is None or run[0]!="RUNNING" or run[1]!=1 or not run[2]:
                raise UnsafeDispatch("Cannot freeze missing/terminal/unbound initial Run")
            old=c.execute("SELECT recipe_digest,provider_workflow_id "
                          "FROM harness_plan_snapshot WHERE run_id=%s AND version=1",
                          (rid,)).fetchone()
            if old:
                if old!=(recipe_digest,run[2]):
                    raise UnsafeDispatch("Frozen Plan v1 digest or Provider binding drift")
                return
            c.execute("INSERT INTO harness_plan_snapshot "
                      "(run_id,version,recipe_digest,provider_workflow_id) "
                      "VALUES (%s,1,%s,%s)",(rid,recipe_digest,run[2]))
            self.facts.event(c,rid,"plan.frozen",
                             {"version":1,"recipe_digest":recipe_digest})

    def admit(self,rid:str,expected_plan_version:int,provider_workflow_id:str)->None:
        """Admission probe for newly-starting execution. NOT a complete Tool permit."""
        with self.facts.tx() as c:
            run=c.execute("SELECT state,plan_version,provider_workflow_id "
                          "FROM harness_run WHERE id=%s FOR UPDATE",(rid,)).fetchone()
            if (run is None or run[0]!="RUNNING" or
                    run[1]!=expected_plan_version or
                    run[2]!=provider_workflow_id):
                raise UnsafeDispatch("Missing, terminal or stale Run/Plan/Provider binding")
            snapshot=c.execute("SELECT provider_workflow_id FROM harness_plan_snapshot "
                               "WHERE run_id=%s AND version=%s",
                               (rid,expected_plan_version)).fetchone()
            if snapshot!=(provider_workflow_id,):
                raise UnsafeDispatch("Unfrozen Plan/Provider")
            if c.execute("SELECT 1 FROM harness_replan_intent WHERE run_id=%s "
                         "AND from_version=%s",(rid,expected_plan_version)).fetchone():
                raise UnsafeDispatch("Replan intent pending: do not launch old downstream")

    def request_replan(self,rid:str,from_version:int,new_recipe_digest:str,reason:str)->None:
        """Persist desire only; fail-closed until actual Hatchet stop/receipt evidence."""
        if (not new_recipe_digest.startswith("sha256:") or not reason.strip()
                or from_version < 1):
            raise ValueError("Replan requires reason, digest and valid Plan version")
        with self.facts.tx() as c:
            run=c.execute("SELECT state,plan_version,provider_workflow_id "
                          "FROM harness_run WHERE id=%s FOR UPDATE",(rid,)).fetchone()
            if run is None or run[0]!="RUNNING" or run[1]!=from_version:
                raise UnsafeDispatch("Replan cannot change a missing/terminal/stale Run")
            snap=c.execute("SELECT recipe_digest,provider_workflow_id "
                           "FROM harness_plan_snapshot WHERE run_id=%s AND version=%s",
                           (rid,from_version)).fetchone()
            if snap is None or snap[1]!=run[2] or snap[0]==new_recipe_digest:
                raise UnsafeDispatch("Frozen Plan/Provider required; digest must change")
            old=c.execute("SELECT intended_recipe_digest,reason FROM harness_replan_intent "
                          "WHERE run_id=%s AND from_version=%s",(rid,from_version)).fetchone()
            if old:
                if old!=(new_recipe_digest,reason):
                    raise UnsafeDispatch("Conflicting replan intent for frozen Plan")
                return
            c.execute("INSERT INTO harness_replan_intent "
                      "(run_id,from_version,intended_recipe_digest,reason,state) "
                      "VALUES (%s,%s,%s,%s,'BLOCKED_PROVIDER_QUIESCENCE')",
                      (rid,from_version,new_recipe_digest,reason))
            self.facts.event(c,rid,"plan.replan.requested",
                             {"from_version":from_version,"intended_recipe_digest":new_recipe_digest,
                              "state":"BLOCKED_PROVIDER_QUIESCENCE"})

    def inspect(self,rid:str)->dict:
        with self.facts.tx() as c:
            r=c.execute("SELECT plan_version FROM harness_run WHERE id=%s",(rid,)).fetchone()
            if not r:raise KeyError(rid)
            plans=c.execute("SELECT version,recipe_digest FROM harness_plan_snapshot "
                            "WHERE run_id=%s ORDER BY version",(rid,)).fetchall()
            pending=c.execute("SELECT from_version,intended_recipe_digest,reason,state "
                              "FROM harness_replan_intent WHERE run_id=%s ORDER BY from_version DESC "
                              "LIMIT 1",(rid,)).fetchone()
        # The historical intent is intentionally immutable: its original
        # BLOCKED decision remains evidence. Once the Run atomically moves to
        # a newer frozen version, derive COMMITTED for the read projection.
        # This is not evidence that a new Hatchet Workflow was confirmed:
        # Segment PENDING/DISPATCHING/CONFIRMED is tracked separately.
        shown = (dict(zip(("from_version","intended_recipe_digest","reason","state"),pending))
                 if pending else None)
        if shown and r[0] > shown["from_version"]:
            shown["state"] = "COMMITTED"
        return {"active_plan_version":r[0],
                "plans":[{"version":v,"recipe_digest":digest} for v,digest in plans],
                "replan":shown}
