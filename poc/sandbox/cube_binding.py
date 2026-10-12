"""DEV-M5 synthetic-run real PostgreSQL Cube Sandbox binding/fencing.

Harness PG owns Scope/Workspace/Environment/Owner, Cube manages actual
MicroVM lifecycle. No independent worker scheduler, no host-files fallback.
The transport may be a Fake ONLY in this contract test; real Cube requires
the separate explicit live MicroVM script and an actual configured endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
import os

from poc.closed_loop.facts import PgFacts, UnsafeDispatch


@dataclass(frozen=True)
class Binding:
    execution_id: str
    run_id: str
    scope: str
    workspace: str
    environment_digest: str
    owner_id: str
    fencing_epoch: int
    sandbox_id: str | None
    generation: int
    state: str


class CubeBinding:
    FIELDS=("execution_id","run_id","isolation_scope","workspace_ref",
            "environment_digest","owner_id","fencing_epoch",
            "provider_sandbox_id","binding_generation","state")

    def __init__(self,facts:PgFacts):
        if not isinstance(facts,PgFacts):
            raise ValueError("Authoritative Harness PostgreSQL facts required")
        self.facts=facts
        with self.facts.tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_cube_binding(
                  execution_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL REFERENCES harness_run(id),
                  isolation_scope TEXT NOT NULL,
                  workspace_ref TEXT NOT NULL,
                  environment_digest TEXT NOT NULL,
                  owner_id TEXT NOT NULL,
                  fencing_epoch BIGINT NOT NULL CHECK(fencing_epoch>=1),
                  lease_expires_at TIMESTAMPTZ NOT NULL,
                  provider_sandbox_id TEXT UNIQUE,
                  binding_generation BIGINT NOT NULL DEFAULT 1,
                  state TEXT NOT NULL CHECK(state IN
                     ('ALLOCATING','CREATING','ACTIVE','BLOCKED_UNKNOWN','RELEASING','RELEASED'))
                )
            """)

    @staticmethod
    def _text(*values):
        if not all(isinstance(v,str) and v and v==v.strip() for v in values):
            raise ValueError("Frozen scope/owner/workspace identity required")

    @staticmethod
    def _valid_epoch(epoch):
        if type(epoch) is not int or epoch < 1:
            raise ValueError("Invalid fencing epoch")

    @staticmethod
    def _binding(row):
        return Binding(*row) if row else None

    def get(self,execution_id:str)->Binding:
        with self.facts.tx() as c:
            row=c.execute(
                "SELECT "+",".join(self.FIELDS)+" FROM harness_cube_binding "
                "WHERE execution_id=%s",(execution_id,),
            ).fetchone()
        if not row: raise KeyError(execution_id)
        return self._binding(row)

    @staticmethod
    def _metadata(row:Binding)->dict[str,str]:
        """Correlation metadata, never a bearer token or SDK authorization."""
        return {
            "harness_execution_id":row.execution_id,
            "harness_run_id":row.run_id,
            "harness_scope":row.scope,
            "harness_workspace_ref":row.workspace,
            "harness_environment_digest":row.environment_digest,
            # Allocation identity remains immutable while binding_generation
            # advances with A -> B fencing. No second create is permitted.
            "harness_generation":"1",
        }

    def correlation(self,execution_id)->dict[str,str]:
        fact=self.get(execution_id)
        if fact.state not in ("ALLOCATING","BLOCKED_UNKNOWN","ACTIVE"):
            raise UnsafeDispatch("No live Cube allocation identity")
        return self._metadata(fact)

    def begin(self,*,execution_id,run_id,scope,workspace,
              environment_digest,owner_id,fencing_epoch,lease_seconds=60):
        self._text(execution_id,run_id,scope,workspace,environment_digest,owner_id)
        self._valid_epoch(fencing_epoch)
        if type(lease_seconds) is not int or not 1<=lease_seconds<=3600:
            raise ValueError("Invalid lease TTL")
        with self.facts.tx() as c:
            run=c.execute("SELECT state,provider_workflow_id FROM harness_run "
                          "WHERE id=%s FOR UPDATE",(run_id,)).fetchone()
            if not run or run[0]!="RUNNING" or not run[1]:
                raise UnsafeDispatch("Sandbox binding requires trusted active Provider Run")
            if c.execute("SELECT 1 FROM harness_cube_binding WHERE execution_id=%s",
                         (execution_id,)).fetchone():
                raise UnsafeDispatch("Cannot replace existing Sandbox binding")
            c.execute(
                "INSERT INTO harness_cube_binding("
                "execution_id,run_id,isolation_scope,workspace_ref,"
                "environment_digest,owner_id,fencing_epoch,lease_expires_at,"
                "state) VALUES (%s,%s,%s,%s,%s,%s,%s,"
                "now()+(%s * interval '1 second'),'ALLOCATING')",
                (execution_id,run_id,scope,workspace,environment_digest,
                 owner_id,fencing_epoch,lease_seconds),
            )
            PgFacts.event(c,run_id,"sandbox.binding.requested",
                          {"execution_id":execution_id,"scope":scope,
                           "workspace_ref":workspace,"epoch":fencing_epoch})
        return self.get(execution_id)

    def _check(self,c,execution_id,owner,epoch,required_state):
        row=c.execute("SELECT "+",".join(self.FIELDS)+",lease_expires_at>now() "
                      "FROM harness_cube_binding WHERE execution_id=%s FOR UPDATE",
                      (execution_id,)).fetchone()
        if (not row or row[5]!=owner or row[6]!=epoch
                or row[9]!=required_state or row[10] is not True):
            raise UnsafeDispatch("STALE_EXECUTION_OWNER / LEASE_EXPIRED / INVALID_BINDING")
        run=c.execute("SELECT state FROM harness_run WHERE id=%s", (row[1],)).fetchone()
        if run!=("RUNNING",):
            raise UnsafeDispatch("Sandbox Run not active")
        return self._binding(row[:-1])

    def assert_active(self,execution_id,owner_id,epoch):
        self._valid_epoch(epoch)
        with self.facts.tx() as c:
            return self._check(c,execution_id,owner_id,epoch,"ACTIVE")

    def assert_unknown(self,execution_id,owner_id,epoch):
        self._valid_epoch(epoch)
        with self.facts.tx() as c:
            return self._check(c,execution_id,owner_id,epoch,"BLOCKED_UNKNOWN")

    def allocate_permitted(self,execution_id,owner_id,epoch):
        with self.facts.tx() as c:
            return self._check(c,execution_id,owner_id,epoch,"ALLOCATING")

    def claim_create(self,execution_id,owner_id,epoch):
        """Durably mark native creation in-flight BEFORE contacting Cube.

        A client retry may not call create again when the ACK is uncertain.
        """
        with self.facts.tx() as c:
            fact=self._check(c,execution_id,owner_id,epoch,"ALLOCATING")
            c.execute(
                "UPDATE harness_cube_binding SET state='CREATING' "
                "WHERE execution_id=%s",(execution_id,))
            PgFacts.event(c,fact.run_id,"sandbox.binding.creation_dispatched",{
                "execution_id":execution_id,"generation":fact.generation})
        return self._metadata(fact)

    def confirm(self,execution_id,owner_id,epoch,sandbox_id):
        self._text(sandbox_id)
        with self.facts.tx() as c:
            row=self._check(c,execution_id,owner_id,epoch,"CREATING")
            c.execute(
                "UPDATE harness_cube_binding SET provider_sandbox_id=%s,state='ACTIVE' "
                "WHERE execution_id=%s",(sandbox_id,execution_id),
            )
            PgFacts.event(c,row.run_id,"sandbox.binding.confirmed",
                          {"execution_id":execution_id,"generation":row.generation})
        return self.get(execution_id)

    def unknown(self,execution_id,owner_id,epoch):
        with self.facts.tx() as c:
            # ALLOCATING direct transition remains test-only for confirmed
            # creation ACK simulation; CREATING is the real dispatch phase.
            try:
                row=self._check(c,execution_id,owner_id,epoch,"CREATING")
            except UnsafeDispatch:
                row=self._check(c,execution_id,owner_id,epoch,"ALLOCATING")
            c.execute("UPDATE harness_cube_binding SET state='BLOCKED_UNKNOWN' "
                      "WHERE execution_id=%s",(execution_id,))
            PgFacts.event(c,row.run_id,"sandbox.binding.unknown",
                          {"execution_id":execution_id})

    def recover_unknown(self,execution_id,owner,epoch,sandbox_id):
        """Persist an existing provider sandbox, never create a new instance."""
        self._text(sandbox_id)
        self._valid_epoch(epoch)
        with self.facts.tx() as c:
            row=self._check(c,execution_id,owner,epoch,"BLOCKED_UNKNOWN")
            if row.sandbox_id is not None:
                raise UnsafeDispatch("UNKNOWN binding already has a provider ID")
            c.execute(
                "UPDATE harness_cube_binding "
                "SET state='ACTIVE',provider_sandbox_id=%s "
                "WHERE execution_id=%s",
                (sandbox_id,execution_id),
            )
            PgFacts.event(c,row.run_id,"sandbox.binding.reconciled",{
                "execution_id":execution_id,
                "sandbox_id":sandbox_id,
                "correlation":"native_unique_metadata_confirmed",
            })
        return self.get(execution_id)

    def takeover(self,execution_id,expected_epoch,new_owner,scope,workspace,
                 environment_digest,lease_seconds=60):
        self._text(execution_id,new_owner,scope,workspace,environment_digest)
        self._valid_epoch(expected_epoch)
        if type(lease_seconds) is not int or not 1<=lease_seconds<=3600:
            raise ValueError("Invalid lease TTL")
        with self.facts.tx() as c:
            row=c.execute("SELECT "+",".join(self.FIELDS)+",lease_expires_at<=now() "
                          "FROM harness_cube_binding WHERE execution_id=%s FOR UPDATE",
                          (execution_id,)).fetchone()
            # An UNKNOWN creation ACK can be reconciled by B after
            # the expired A lease; it is NEVER permission to create again.
            if (not row or row[9] not in ("ACTIVE","BLOCKED_UNKNOWN","CREATING")
                    or row[10] is not True
                    or row[6]!=expected_epoch or row[5]==new_owner
                    or row[2:5]!=(scope,workspace,environment_digest)
                    or (row[9]=="ACTIVE" and not row[7])
                    or (row[9] in ("BLOCKED_UNKNOWN","CREATING")
                        and row[7] is not None)):
                raise UnsafeDispatch("Sandbox takeover requires expired matching Scope/Workspace")
            run=c.execute("SELECT state FROM harness_run WHERE id=%s FOR UPDATE",
                          (row[1],)).fetchone()
            if run!=("RUNNING",):
                raise UnsafeDispatch("Stale Run cannot take over Sandbox")
            c.execute(
                "UPDATE harness_cube_binding SET owner_id=%s,fencing_epoch=%s,"
                "lease_expires_at=now()+(%s * interval '1 second'),"
                "binding_generation=binding_generation+1,"
                "state=CASE WHEN state='CREATING' THEN 'BLOCKED_UNKNOWN' "
                "ELSE state END "
                "WHERE execution_id=%s",
                (new_owner,expected_epoch+1,lease_seconds,execution_id),
            )
            PgFacts.event(c,row[1],"sandbox.binding.transferred",{
                "execution_id":execution_id,
                "old_epoch":expected_epoch,
                "new_epoch":expected_epoch+1,
                "workspace_ref":workspace})
        return self.get(execution_id)

    def mark_releasing(self,execution_id,owner,epoch):
        with self.facts.tx() as c:
            row=self._check(c,execution_id,owner,epoch,"ACTIVE")
            c.execute("UPDATE harness_cube_binding SET state='RELEASING' "
                      "WHERE execution_id=%s",(execution_id,))
            return row.sandbox_id

    def mark_released(self,execution_id,owner,epoch):
        with self.facts.tx() as c:
            row=c.execute(
                "SELECT run_id,owner_id,fencing_epoch,state "
                "FROM harness_cube_binding WHERE execution_id=%s FOR UPDATE",
                (execution_id,),
            ).fetchone()
            if not row or row[1:]!=(owner,epoch,"RELEASING"):
                raise UnsafeDispatch("Sandbox destroy ACK missing/stale")
            c.execute("UPDATE harness_cube_binding SET state='RELEASED' "
                      "WHERE execution_id=%s",(execution_id,))
            PgFacts.event(c,row[0],"sandbox.binding.released",
                          {"execution_id":execution_id})


class CubeWorkspaceGateway:
    def __init__(self,binding:CubeBinding,transport):
        self.binding=binding
        self.transport=transport

    @staticmethod
    def _path(path):
        if (not isinstance(path,str) or not path.startswith("/workspace/")
                or len(path)<=len("/workspace/")
                or "\\" in path or "//" in path
                or any(s in (".","..") for s in path.split("/"))):
            raise UnsafeDispatch("Only canonical paths within /workspace are allowed")
        return path

    def allocate(self,execution_id,owner,epoch):
        metadata=self.binding.claim_create(execution_id,owner,epoch)
        try:
            sbid=self.transport.create(metadata=metadata)
        except Exception:
            self.binding.unknown(execution_id,owner,epoch)
            raise UnsafeDispatch("Cube create outcome unknown; no blind reallocation") from None
        try:
            self.binding.confirm(execution_id,owner,epoch,sbid)
        except Exception:
            # The native sandbox exists; even a lost PG ACK can never
            # re-enter ALLOCATING after the durable CREATING transition.
            try:
                self.binding.unknown(execution_id,owner,epoch)
            except Exception:
                pass  # PG may have committed ACTIVE despite a lost ACK.
            raise UnsafeDispatch("Cube bind ACK unknown; reconcile existing sandbox") from None
        return sbid

    def reconcile_unknown(self,execution_id,owner,epoch):
        """Only one native, fully verified Cube can recover a lost create ACK.

        If the provider list is unavailable/incomplete, or zero/multiple
        correlations match, never conclude sandbox absence or allocate again.
        """
        fact=self.binding.get(execution_id)
        if fact.state=="ACTIVE":
            active=self.binding.assert_active(execution_id,owner,epoch)
            return active.sandbox_id
        unknown=self.binding.assert_unknown(execution_id,owner,epoch)
        expected=self.binding.correlation(execution_id)
        try:
            rows=self.transport.list()
            if not isinstance(rows,list) or len(rows)>1000:
                raise ValueError("Cube listing unavailable or too large to trust")
            matches=[]
            for row in rows:
                if not isinstance(row,dict):
                    raise ValueError("Malformed native Cube listing")
                if row.get("metadata") == expected:
                    sid=row.get("sandboxID")
                    if not isinstance(sid,str) or not sid.strip():
                        raise ValueError("Native Cube ID absent")
                    matches.append(sid)
            if len(matches)!=1:
                raise ValueError("Ambiguous/absent native Cube correlation")
            sid=matches[0]
            sb=self.transport.connect(sid)
            actual=self.transport.inspect(sb)
            if (not isinstance(actual,dict)
                    or actual.get("sandboxID")!=sid
                    or actual.get("metadata")!=expected):
                raise ValueError("Native Cube detail does not match frozen binding")
        except Exception:
            raise UnsafeDispatch("Native Cube evidence not unique/verified; stay BLOCKED_UNKNOWN") from None
        recovered=self.binding.recover_unknown(execution_id,owner,epoch,sid)
        if recovered.sandbox_id!=sid or recovered.generation!=unknown.generation:
            raise UnsafeDispatch("Concurrent Cube binding changed")
        return sid

    def _attach(self,execution_id,owner,epoch):
        fact=self.binding.assert_active(execution_id,owner,epoch)
        try:
            sb=self.transport.connect(fact.sandbox_id)
        except Exception:
            raise UnsafeDispatch("Cube connect unavailable: cannot fabricate a replacement Workspace") from None
        # A real provider call can race an Owner change. Recheck PG authority
        # before each operation; full revoke-in-flight requires guest fencing.
        fresh=self.binding.assert_active(execution_id,owner,epoch)
        if (fresh.sandbox_id != fact.sandbox_id
                or fresh.generation!=fact.generation):
            raise UnsafeDispatch("Sandbox Binding generation changed during connect")
        return sb

    def read(self,execution_id,owner,epoch,path):
        self._path(path)
        sb=self._attach(execution_id,owner,epoch)
        return self.transport.read(sb,path)

    def write(self,execution_id,owner,epoch,path,content):
        self._path(path)
        sb=self._attach(execution_id,owner,epoch)
        return self.transport.write(sb,path,content)

    def release(self,execution_id,owner,epoch):
        sbid=self.binding.mark_releasing(execution_id,owner,epoch)
        try:
            sb=self.transport.connect(sbid)
            self.transport.kill(sb)
        except Exception:
            # RELEASING is not an ACK: remain blocked, never make a second
            # sandbox while destroy confirmation is uncertain.
            raise UnsafeDispatch("Cube destroy ACK unknown; explicit reconciliation required") from None
        self.binding.mark_released(execution_id,owner,epoch)


class NativeCubeTransport:
    """Production-shaped Cube SDK port; requires real configured Cube API.

    Import is deferred so PG guardrail contract tests need no running
    MicroVM or Cube installation. Sandbox IDs only ever come from PG fact.
    """
    def __init__(self):
        if not os.environ.get("CUBE_API_URL") or not os.environ.get("CUBE_TEMPLATE_ID"):
            raise RuntimeError("Real CUBE_API_URL and CUBE_TEMPLATE_ID required")
        from cubesandbox import Sandbox
        self.sdk=Sandbox
        # Freeze the real, pre-approved template at Adapter construction.
        # Do not rely on SDK defaults or mutable process environment at create.
        self.template=os.environ["CUBE_TEMPLATE_ID"]

    def create(self,*,metadata):
        sandbox=self.sdk.create(
            template=self.template,timeout=300,metadata=dict(metadata))
        return sandbox.sandbox_id

    def list(self):
        return self.sdk.list()

    def inspect(self,sandbox):
        info=sandbox.get_info()
        return {
            "sandboxID":info.sandbox_id if hasattr(info,"sandbox_id") else info["sandboxID"],
            "metadata":info.metadata if hasattr(info,"metadata") else info["metadata"],
        }

    def connect(self,sandbox_id):
        return self.sdk.connect(sandbox_id)

    def read(self,sandbox,path):
        return sandbox.files.read(path)

    def write(self,sandbox,path,data):
        return sandbox.files.write(path,data)

    def kill(self,sandbox):
        return sandbox.kill()
