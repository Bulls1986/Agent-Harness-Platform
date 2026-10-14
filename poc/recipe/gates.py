"""DEV-M6 frozen three-Agent Recipe overlay on canonical Harness Run/Step facts.

No parallel Run/Step kernel, engine scheduler, or provider-owned domain state.
Trusted application services own principal validation and actual Artifact verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re

from poc.closed_loop.facts import PgFacts, sha


class RecipeBlocked(RuntimeError):
    """Fail closed; retry only after authoritative reconciliation."""


@dataclass(frozen=True)
class ArtifactRef:
    ref: str
    digest: str
    scope: str

    def validate(self, scope: str) -> None:
        if (not isinstance(self.ref, str) or not self.ref.startswith("oss://")
                or not isinstance(self.digest, str)
                or re.fullmatch(r"sha256:[0-9a-f]{64}", self.digest) is None
                or self.scope != scope):
            raise RecipeBlocked("Invalid or cross-scope ArtifactRef")


class RecipeGate:
    """M6 Recipe metadata + admission; core Run/Step/Attempt remains authoritative."""

    def __init__(self, url: str):
        self.db = PgFacts(url)
        self.init_schema()

    def init_schema(self):
        with self.db.tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_recipe_frozen (
                    run_id TEXT PRIMARY KEY REFERENCES harness_run(id),
                    version TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    scope TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_recipe_step_meta (
                    run_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    runtime TEXT NOT NULL,
                    effect TEXT NOT NULL,
                    input_ref TEXT,
                    output_ref TEXT,
                    output_digest TEXT,
                    verifier_evidence_ref TEXT,
                    PRIMARY KEY(run_id, name),
                    UNIQUE(run_id, ordinal),
                    FOREIGN KEY(run_id, name) REFERENCES harness_step(run_id, id)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_recipe_step_approval (
                    run_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    requester TEXT NOT NULL,
                    action_digest TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    actor TEXT,
                    PRIMARY KEY(run_id, step_name),
                    FOREIGN KEY(run_id, step_name)
                        REFERENCES harness_recipe_step_meta(run_id, name)
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_recipe_input (
                    run_id TEXT PRIMARY KEY REFERENCES harness_recipe_frozen(run_id),
                    requester TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('PENDING','RESOLVED')),
                    actor TEXT,
                    response_ref TEXT,
                    response_digest TEXT,
                    verifier_evidence_ref TEXT
                )
            """)

    @staticmethod
    def _recipe(recipe: dict) -> tuple[str, str]:
        if not isinstance(recipe, dict) or not isinstance(recipe.get("version"), str):
            raise RecipeBlocked("Frozen Recipe version missing")
        version = recipe["version"]
        steps = recipe.get("steps")
        if (not version.strip() or not isinstance(steps, list) or
                len(steps) != 3 or any(not isinstance(x, dict) for x in steps) or
                [(x.get("name"), x.get("runtime"), x.get("effect")) for x in steps]
                != [("plan", "pydantic", "PURE"), ("code", "openai", "WRITE"),
                    ("verify", "pydantic", "PURE")]):
            raise RecipeBlocked("Only the existing M6 plan→code→verify Recipe is supported")
        canonical = json.dumps(recipe, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False)
        return version, "sha256:" + sha256(canonical.encode("utf8")).hexdigest()

    @staticmethod
    def _run(c, rid: str) -> dict:
        row = c.execute(
            "SELECT r.state,r.plan_version,r.provider_workflow_id,r.project_scope,"
            "f.version,f.digest,f.scope FROM harness_run r "
            "JOIN harness_recipe_frozen f ON f.run_id=r.id "
            "WHERE r.id=%s FOR UPDATE OF r", (rid,)).fetchone()
        if not row:
            raise RecipeBlocked("Unknown frozen Recipe Run")
        result = dict(zip(("state","plan_version","provider","owner_scope",
                           "version","digest","scope"), row))
        if result["plan_version"] != 1 or result["owner_scope"] != result["scope"]:
            raise RecipeBlocked("Stale plan or owner scope drift")
        return result

    @staticmethod
    def _step(c, rid: str, name: str) -> dict:
        row = c.execute(
            "SELECT m.ordinal,m.runtime,m.effect,m.input_ref,m.output_ref,"
            "m.output_digest,m.verifier_evidence_ref,s.state,s.attempts "
            "FROM harness_recipe_step_meta m JOIN harness_step s "
            "ON s.run_id=m.run_id AND s.id=m.name "
            "WHERE m.run_id=%s AND m.name=%s", (rid, name)).fetchone()
        if not row:
            raise RecipeBlocked("Unknown Recipe Step")
        return dict(zip(("ordinal","runtime","effect","input_ref","output_ref",
                         "output_digest","verifier_ref","state","attempts"), row))

    def freeze(self, rid: str, recipe: dict, *, scope: str, principal: str) -> str:
        version, digest = self._recipe(recipe)
        if (not rid or not scope or scope != scope.strip()
                or not principal or principal != principal.strip()):
            raise RecipeBlocked("Authenticated owner and canonical scope required")
        with self.db.tx() as c:
            inserted = c.execute(
                "INSERT INTO harness_run(id,plan_version,state,project_scope,"
                "initiator_principal_id) VALUES (%s,1,'CREATED',%s,%s) "
                "ON CONFLICT (id) DO NOTHING", (rid, scope, principal)).rowcount
            if inserted:
                c.execute(
                    "INSERT INTO harness_recipe_frozen VALUES (%s,%s,%s,%s)",
                    (rid,version,digest,scope))
                for i, step in enumerate(recipe["steps"]):
                    c.execute("INSERT INTO harness_step(run_id,id,state) "
                              "VALUES (%s,%s,'PENDING')", (rid,step["name"]))
                    c.execute(
                        "INSERT INTO harness_recipe_step_meta"
                        "(run_id,name,ordinal,runtime,effect) VALUES (%s,%s,%s,%s,%s)",
                        (rid,step["name"],i,step["runtime"],step["effect"]))
                c.execute("INSERT INTO harness_outbox VALUES (%s,%s,'PENDING')",
                          (f"{rid}:segment-0:create:v1", rid))
                self.db.event(c, rid, "recipe.frozen",
                              {"digest":digest,"version":version,"steps":3})
            run = self._run(c,rid)
            owner = c.execute(
                "SELECT initiator_principal_id FROM harness_run WHERE id=%s",
                (rid,)).fetchone()[0]
            if (run["version"],run["digest"],run["scope"],owner) != (
                    version,digest,scope,principal):
                raise RecipeBlocked("Frozen Recipe or owner identity drift")
        return digest

    def request_input(self, rid: str, requester: str,
                      request_digest: str) -> None:
        """Persist missing information as original Run's WAITING_INPUT."""
        if (not requester or requester != requester.strip()
                or re.fullmatch(r"sha256:[0-9a-f]{64}", request_digest) is None):
            raise RecipeBlocked("Validated input requester and frozen request required")
        with self.db.tx() as c:
            run = self._run(c, rid)
            plan = self._step(c, rid, "plan")
            code = self._step(c, rid, "code")
            if (plan["state"] != "COMPLETED" or not plan["verifier_ref"]
                    or code["state"] != "PENDING"):
                raise RecipeBlocked("Cannot request input outside verified pending boundary")
            if c.execute("SELECT 1 FROM harness_recipe_step_approval WHERE run_id=%s",
                         (rid,)).fetchone():
                raise RecipeBlocked("Cannot introduce input after approval request")
            existing=c.execute(
                "SELECT requester,request_digest,state FROM harness_recipe_input "
                "WHERE run_id=%s",(rid,)).fetchone()
            if existing:
                if ((existing==(requester,request_digest,"PENDING")
                     and run["state"]=="WAITING_INPUT")
                    or (existing==(requester,request_digest,"RESOLVED")
                        and run["state"]=="RUNNING")):
                    return  # trusted Hatchet retry, no second business request
                raise RecipeBlocked("Frozen input request drift or illegal replay")
            if run["state"]!="RUNNING":
                raise RecipeBlocked("New input requires an executing original Run")
            c.execute(
                "INSERT INTO harness_recipe_input "
                "(run_id,requester,request_digest,state) "
                "VALUES (%s,%s,%s,'PENDING')",
                (rid,requester,request_digest))
            c.execute("UPDATE harness_run SET state='WAITING_INPUT' WHERE id=%s",
                      (rid,))
            self.db.event(c,rid,"input.requested",
                          {"request_digest":request_digest})

    def answer_input(self, rid: str, actor: str, artifact: ArtifactRef,
                     verifier_evidence_ref: str) -> None:
        """Trusted verifier confirms the external response before Run resumes."""
        if (not actor or actor != actor.strip()
                or not verifier_evidence_ref or not verifier_evidence_ref.strip()):
            raise RecipeBlocked("Verified response actor and evidence required")
        with self.db.tx() as c:
            run = self._run(c,rid)
            artifact.validate(run["scope"])
            row=c.execute(
                "SELECT requester,state FROM harness_recipe_input WHERE run_id=%s",
                (rid,)).fetchone()
            if (run["state"] != "WAITING_INPUT" or not row
                    or row[1] != "PENDING" or actor == row[0]):
                raise RecipeBlocked("No pending independent input response")
            c.execute(
                "UPDATE harness_recipe_input SET state='RESOLVED',actor=%s,"
                "response_ref=%s,response_digest=%s,verifier_evidence_ref=%s "
                "WHERE run_id=%s",
                (actor,artifact.ref,artifact.digest,verifier_evidence_ref,rid))
            c.execute("UPDATE harness_run SET state='RUNNING' WHERE id=%s",(rid,))
            self.db.event(c,rid,"input.resolved",
                          {"response_ref":artifact.ref,
                           "digest":artifact.digest,
                           "evidence_ref":verifier_evidence_ref})

    def request_approval(self, rid: str, step_name: str,
                         requester: str, action_digest: str) -> None:
        if (not requester or requester != requester.strip()
                or re.fullmatch(r"sha256:[0-9a-f]{64}", action_digest) is None):
            raise RecipeBlocked("Frozen action and approval principal required")
        with self.db.tx() as c:
            run = self._run(c,rid)
            step = self._step(c,rid,step_name)
            if (step["effect"]!="WRITE" or step["state"]!="PENDING"):
                raise RecipeBlocked("Only pending write Step can request approval")
            parent = c.execute(
                "SELECT s.state,m.verifier_evidence_ref FROM harness_step s "
                "JOIN harness_recipe_step_meta m ON m.run_id=s.run_id AND m.name=s.id "
                "WHERE s.run_id=%s AND m.ordinal=%s",
                (rid,step["ordinal"]-1)).fetchone()
            if not parent or parent[0] != "COMPLETED" or not parent[1]:
                raise RecipeBlocked("Unverified parent Step")
            old = c.execute(
                "SELECT requester,action_digest,decision FROM harness_recipe_step_approval "
                "WHERE run_id=%s AND step_name=%s", (rid,step_name)).fetchone()
            if old:
                if (old==(requester,action_digest,"PENDING")
                    and run["state"]=="WAITING_APPROVAL"):
                    return  # same frozen approval; native Worker B replay
                if (old==(requester,action_digest,"APPROVED")
                    and run["state"]=="RUNNING"):
                    return  # identical approved request after durable wakeup
                raise RecipeBlocked("Frozen approval drift, rejection or illegal replay")
            if run["state"]!="RUNNING":
                raise RecipeBlocked("New approval requires original running Run")
            c.execute("INSERT INTO harness_recipe_step_approval VALUES "
                      "(%s,%s,%s,%s,'PENDING',NULL)",
                      (rid,step_name,requester,action_digest))
            c.execute("UPDATE harness_run SET state='WAITING_APPROVAL' WHERE id=%s",
                      (rid,))
            self.db.event(c,rid,"approval.requested",
                          {"step":step_name,"action_digest":action_digest})

    def decide_approval(self, rid: str, step_name: str,
                        actor: str, decision: str) -> None:
        if (decision not in ("APPROVED","REJECTED") or not actor
                or actor != actor.strip()):
            raise RecipeBlocked("Invalid decision or principal")
        with self.db.tx() as c:
            run=self._run(c,rid)
            row=c.execute(
                "SELECT requester,decision FROM harness_recipe_step_approval "
                "WHERE run_id=%s AND step_name=%s", (rid,step_name)).fetchone()
            if (not row or row[1]!="PENDING" or run["state"]!="WAITING_APPROVAL"
                    or actor==row[0]):
                raise RecipeBlocked("No pending independent approval")
            c.execute(
                "UPDATE harness_recipe_step_approval SET decision=%s,actor=%s "
                "WHERE run_id=%s AND step_name=%s",
                (decision,actor,rid,step_name))
            c.execute("UPDATE harness_run SET state=%s WHERE id=%s",
                      ("RUNNING" if decision=="APPROVED" else "BLOCKED",rid))
            self.db.event(c,rid,"approval.decided",
                          {"step":step_name,"actor":actor,"decision":decision})

    def claim_step(self, rid: str, name: str, attempt_id: str) -> ArtifactRef | None:
        self.db.validate_attempt_id(attempt_id)
        with self.db.tx() as c:
            run=self._run(c,rid)
            step=self._step(c,rid,name)
            # The confirmed Provider binding is mandatory; this is not a
            # self-hosted task engine or an unbound local retry path.
            confirmed=c.execute(
                "SELECT 1 FROM harness_outbox WHERE run_id=%s AND state='CONFIRMED'",
                (rid,)).fetchone()
            if (run["state"]!="RUNNING" or not run["provider"] or not confirmed
                    or step["state"]!="PENDING" or step["attempts"]!=0):
                raise RecipeBlocked("Unbound, terminal or prior Attempt; reconcile first")
            parent=None
            if step["ordinal"]:
                parent=c.execute(
                    "SELECT s.state,m.output_ref,m.output_digest,m.verifier_evidence_ref "
                    "FROM harness_step s JOIN harness_recipe_step_meta m "
                    "ON m.run_id=s.run_id AND m.name=s.id "
                    "WHERE s.run_id=%s AND m.ordinal=%s",
                    (rid,step["ordinal"]-1)).fetchone()
                if (not parent or parent[0]!="COMPLETED" or not parent[3]):
                    raise RecipeBlocked("Parent not independently verified")
            if step["effect"]=="WRITE":
                approved=c.execute(
                    "SELECT decision FROM harness_recipe_step_approval "
                    "WHERE run_id=%s AND step_name=%s",
                    (rid,name)).fetchone()
                if not approved or approved[0]!="APPROVED":
                    raise RecipeBlocked("Write must be approved before Tool dispatch")
            value=parent[1] if parent else ""
            c.execute("UPDATE harness_step SET state='RUNNING',attempts=1,"
                      "input_hash=%s WHERE run_id=%s AND id=%s",
                      (sha(value),rid,name))
            c.execute(
                "INSERT INTO harness_step_attempt"
                "(run_id,step_id,ordinal,attempt_id,plan_version,state) "
                "VALUES (%s,%s,1,%s,1,'RUNNING')", (rid,name,attempt_id))
            c.execute("UPDATE harness_recipe_step_meta SET input_ref=%s "
                      "WHERE run_id=%s AND name=%s",
                      (value or None,rid,name))
            self.db.event(c,rid,"step.started",
                          {"step_id":name,"attempt_id":attempt_id,
                           "input_ref":value or None})
            return ArtifactRef(parent[1],parent[2],run["scope"]) if parent else None

    def require_write_permit(self, rid: str, name: str, attempt_id: str) -> str:
        """PG approval check for trusted Tool Bridge, not an execution capability.

        The Tool Bridge must separately validate HC-03 fencing/capabilities
        and register the frozen HC-02 side-effect intent before dispatch.
        """
        self.db.validate_attempt_id(attempt_id)
        with self.db.tx() as c:
            run = self._run(c, rid)
            step = self._step(c, rid, name)
            outbox = c.execute(
                "SELECT 1 FROM harness_outbox WHERE run_id=%s AND state='CONFIRMED'",
                (rid,)).fetchone()
            attempt = c.execute(
                "SELECT attempt_id,plan_version,state FROM harness_step_attempt "
                "WHERE run_id=%s AND step_id=%s AND ordinal=1",
                (rid,name)).fetchone()
            approval = c.execute(
                "SELECT decision FROM harness_recipe_step_approval "
                "WHERE run_id=%s AND step_name=%s", (rid,name)).fetchone()
            if (run["state"] != "RUNNING" or not run["provider"] or not outbox
                    or step["effect"] != "WRITE" or step["state"] != "RUNNING"
                    or attempt != (attempt_id,1,"RUNNING")
                    or not approval or approval[0] != "APPROVED"):
                raise RecipeBlocked("Missing approval, current Attempt or Provider binding")
        return "APPROVED"

    @staticmethod
    def _require_confirmed_receipts(c, rid: str, name: str, attempt_id: str):
        if not c.execute(
            "SELECT to_regclass('harness_tool_intent') IS NOT NULL"
        ).fetchone()[0]:
            raise RecipeBlocked("Missing M4 SideEffectReceipt journal")
        count,confirmed = c.execute(
            "SELECT count(*),count(*) FILTER (WHERE state='CONFIRMED_SUCCESS' "
            "AND external_reference IS NOT NULL) FROM harness_tool_intent "
            "WHERE run_id=%s AND plan_version=1 AND step_id=%s AND attempt_id=%s",
            (rid,name,attempt_id)).fetchone()
        if count < 1 or count != confirmed:
            raise RecipeBlocked("Write cannot verify without confirmed external Receipt")

    def verify_step(self, rid: str, name: str, attempt_id: str,
                    artifact: ArtifactRef, verifier_evidence_ref: str) -> None:
        # Trusted verifier must check actual artifact bytes against digest.
        # Arbitrary callers must never be exposed to this domain write port.
        if not verifier_evidence_ref or not verifier_evidence_ref.strip():
            raise RecipeBlocked("Independent verification evidence required")
        self.db.validate_attempt_id(attempt_id)
        with self.db.tx() as c:
            run=self._run(c,rid)
            step=self._step(c,rid,name)
            artifact.validate(run["scope"])
            attempt=c.execute(
                "SELECT attempt_id,plan_version,state FROM harness_step_attempt "
                "WHERE run_id=%s AND step_id=%s AND ordinal=1",
                (rid,name)).fetchone()
            if (run["state"]!="RUNNING" or step["state"]!="RUNNING"
                    or attempt!=(attempt_id,1,"RUNNING")):
                raise RecipeBlocked("Wrong, stale, or already committed Attempt")
            if step["effect"] == "WRITE":
                self._require_confirmed_receipts(c, rid, name, attempt_id)
            c.execute("UPDATE harness_step_attempt SET state='COMPLETED' "
                      "WHERE run_id=%s AND step_id=%s AND ordinal=1",
                      (rid,name))
            c.execute(
                "UPDATE harness_step SET state='COMPLETED',output=%s,"
                "output_hash=%s WHERE run_id=%s AND id=%s",
                (artifact.ref,sha(artifact.ref),rid,name))
            c.execute(
                "UPDATE harness_recipe_step_meta SET output_ref=%s,output_digest=%s,"
                "verifier_evidence_ref=%s WHERE run_id=%s AND name=%s",
                (artifact.ref,artifact.digest,verifier_evidence_ref,rid,name))
            self.db.event(c,rid,"step.verified",
                          {"step":name,"artifact_ref":artifact.ref,
                           "digest":artifact.digest,"evidence_ref":verifier_evidence_ref})
            remaining=c.execute(
                "SELECT count(*) FROM harness_step s "
                "JOIN harness_recipe_step_meta m ON m.run_id=s.run_id AND m.name=s.id "
                "WHERE s.run_id=%s AND (s.state!='COMPLETED' "
                "OR m.verifier_evidence_ref IS NULL)", (rid,)).fetchone()[0]
            if remaining==0:
                if c.execute("SELECT to_regclass('harness_tool_intent') IS NOT NULL").fetchone()[0]:
                    unresolved = c.execute(
                        "SELECT 1 FROM harness_tool_intent WHERE run_id=%s "
                        "AND (state!='CONFIRMED_SUCCESS' OR external_reference IS NULL) LIMIT 1",
                        (rid,)).fetchone()
                    if unresolved:
                        raise RecipeBlocked("Unreconciled Tool Receipt blocks Run terminal")
                result={"final_output":artifact.ref,"result_source_step":name,
                        "recipe_digest":run["digest"]}
                c.execute("UPDATE harness_run SET state='COMPLETED',"
                          "result_json=%s::jsonb WHERE id=%s",
                          (json.dumps(result),rid))
                self.db.event(c,rid,"recipe.completed",
                              {"recipe_digest":run["digest"],"result_ref":artifact.ref})
                self.db.event(c,rid,"run.completed",
                              {"provider_workflow_run_id":run["provider"],
                               "result_source_step":name})

    def snapshot(self, rid: str) -> dict:
        with self.db.tx() as c:
            run=self._run(c,rid)
            rows=c.execute(
                "SELECT m.name,m.runtime,m.effect,s.state,m.input_ref,"
                "m.output_ref,m.output_digest,m.verifier_evidence_ref "
                "FROM harness_recipe_step_meta m JOIN harness_step s "
                "ON s.run_id=m.run_id AND s.id=m.name "
                "WHERE m.run_id=%s ORDER BY m.ordinal", (rid,)).fetchall()
            approvals=c.execute(
                "SELECT step_name,requester,decision,actor FROM harness_recipe_step_approval "
                "WHERE run_id=%s", (rid,)).fetchall()
            inputs=c.execute(
                "SELECT requester,request_digest,state,actor,response_ref,"
                "response_digest,verifier_evidence_ref FROM harness_recipe_input "
                "WHERE run_id=%s",(rid,)).fetchall()
            events=c.execute(
                "SELECT seq,type,data FROM harness_event "
                "WHERE run_id=%s ORDER BY seq", (rid,)).fetchall()
        names=("name","runtime","effect","state","input_ref","output_ref",
               "output_digest","verifier_evidence_ref")
        steps=[dict(zip(names,row)) for row in rows]
        for step in steps:
            if step["state"]=="COMPLETED" and step["verifier_evidence_ref"]:
                step["state"]="VERIFIED"  # derived projection, not parallel state
        return {"run_id":rid,"version":run["version"],"digest":run["digest"],
                "scope":run["scope"],"state":run["state"],"steps":steps,
                "approvals":[dict(zip(("step","requester","decision","actor"),row))
                             for row in approvals],
                "inputs":[dict(zip(("requester","request_digest","state","actor",
                                    "response_ref","response_digest","verifier_evidence_ref"),row))
                          for row in inputs],
                "events":[{"seq":seq,"type":kind,"data":data}
                          for seq,kind,data in events]}