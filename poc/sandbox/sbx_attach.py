"""DEV-SBX M2: pre-Run Session Attach to native Cube Sandbox.

No new scheduler/SDK protocol. A Session binding is only an association,
never itself a Shell capability. Agent runtime Execute remains M5-owned.
"""
from __future__ import annotations

from hashlib import sha256
import json
from time import time
from dataclasses import dataclass
from uuid import uuid4

from poc.sandbox.sbx_management import (
    _validate, SandboxConflict, SandboxPermissionDenied, SandboxUnknown,
)


@dataclass(frozen=True)
class InitializationPermit:
    """Trusted server-issued short-lived grant, never supplied by public API."""
    scope: str
    principal: str
    session_ref: str
    sandbox_id: str
    operation_digest: str
    expires_at: float


_FIELDS = ("binding_id", "scope", "principal", "session_ref",
           "create_operation_id", "sandbox_id", "idempotency_key",
           "fingerprint", "state", "exit_code")


class PgSessionBindingStore:
    """Only binding/initialization facts; Cube continues to own the VM."""
    def __init__(self, facts):
        from poc.closed_loop.facts import PgFacts
        if not isinstance(facts, PgFacts):
            raise ValueError("Real PostgreSQL facts are required")
        self.facts = facts
        with facts.tx() as c:
            c.execute("""
              CREATE TABLE IF NOT EXISTS harness_sbx_session_binding (
                binding_id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                principal TEXT NOT NULL,
                session_ref TEXT NOT NULL,
                create_operation_id TEXT NOT NULL,
                sandbox_id TEXT NOT NULL UNIQUE,
                idempotency_key TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN
                  ('PENDING','INITIALIZING','ACTIVE','FAILED','UNKNOWN')),
                exit_code INT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                UNIQUE(scope,principal,idempotency_key),
                UNIQUE(scope,session_ref)
              )
            """)

    @staticmethod
    def _row(row):
        return dict(zip(_FIELDS,row)) if row else None

    def begin(self, *, scope, principal, session_ref, create_operation_id,
              sandbox_id, key, fingerprint):
        with self.facts.tx() as c:
            # No application-specific lookup; only already authenticated M1
            # PG creation facts may become a Session sandbox association.
            creation=c.execute(
                "SELECT sandbox_id, state FROM harness_sbx_create_op "
                "WHERE operation_id=%s AND scope=%s AND principal=%s FOR SHARE",
                (create_operation_id,scope,principal)).fetchone()
            if creation is None:
                raise KeyError(create_operation_id)
            if creation[1]!="READY" or creation[0]!=sandbox_id:
                raise SandboxConflict("Sandbox is not READY or owned by caller")
            c.execute("""
              INSERT INTO harness_sbx_session_binding
                (binding_id,scope,principal,session_ref,create_operation_id,
                 sandbox_id,idempotency_key,fingerprint,state)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'PENDING')
              ON CONFLICT DO NOTHING
            """,( "sbx-bind-"+uuid4().hex, scope, principal, session_ref,
                  create_operation_id, sandbox_id, key, fingerprint))
            # The sandbox's identity is unique. A request cannot attach an
            # already-claimed writable VM to another Session, even same Scope.
            row=c.execute(
                "SELECT "+",".join(_FIELDS)+" FROM harness_sbx_session_binding "
                "WHERE sandbox_id=%s FOR UPDATE",(sandbox_id,)).fetchone()
            if row is None:
                raise SandboxConflict("Sandbox already allocated to another Session")
            b=self._row(row)
            if (b["scope"],b["principal"],b["session_ref"],b["create_operation_id"],
                b["idempotency_key"],b["fingerprint"]) != (
                scope,principal,session_ref,create_operation_id,key,fingerprint):
                raise SandboxConflict("Sandbox already bound or conflicting idempotency")
            return b

    def transition(self, *, binding_id, scope, principal, from_state, to_state,
                   exit_code=None):
        if to_state not in ("INITIALIZING","ACTIVE","FAILED","UNKNOWN"):
            raise ValueError("Invalid Attach state")
        with self.facts.tx() as c:
            row=c.execute(
                "UPDATE harness_sbx_session_binding SET state=%s, exit_code=%s "
                "WHERE binding_id=%s AND scope=%s AND principal=%s AND state=%s "
                "RETURNING "+",".join(_FIELDS),
                (to_state,exit_code,binding_id,scope,principal,from_state)).fetchone()
        if row is None:
            raise SandboxConflict("Stale Session Binding transition")
        return self._row(row)

    def get(self,*,binding_id,scope,principal):
        with self.facts.tx() as c:
            row=c.execute(
                "SELECT "+",".join(_FIELDS)+" FROM harness_sbx_session_binding "
                "WHERE binding_id=%s AND scope=%s AND principal=%s",
                (binding_id,scope,principal)).fetchone()
        if row is None:
            raise KeyError(binding_id)
        return self._row(row)


class SessionAttachService:
    def __init__(self, *, store, create_store, native, authorize, authorize_session):
        if not isinstance(store,PgSessionBindingStore):
            raise ValueError("PG session binding facts are mandatory")
        if not callable(authorize) or not callable(authorize_session):
            raise ValueError("Trusted Policy and Session resolver required")
        if not callable(getattr(native,"connect",None)):
            raise ValueError("Native Cube connect port required")
        self.store,self.create_store,self.native=store,create_store,native
        self.authorize,self.authorize_session=authorize,authorize_session

    @staticmethod
    def _identity(*fields):
        if not all(isinstance(x,str) and x and x==x.strip() and len(x)<=256
                   for x in fields):
            raise ValueError("Non-empty trusted scoped identity/key required")

    def attach(self, *, scope, principal, create_operation_id, session_ref,
               idempotency_key, on_attach):
        self._identity(scope,principal,create_operation_id,session_ref,idempotency_key)
        if not isinstance(on_attach,list):
            raise ValueError("onAttach commands required as an ordered list")
        _validate({"template":"tpl-trusted"},on_attach)
        payload={"createOperationId":create_operation_id,
                 "sessionRef":session_ref, "onAttach":on_attach}
        digest=sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if self.authorize_session(scope,principal,session_ref) is not True:
            raise SandboxPermissionDenied("Session access denied")
        creation=self.create_store.get(create_operation_id,scope,principal)
        if creation["state"] != "READY" or not creation["sandbox_id"]:
            raise SandboxConflict("Cannot attach Sandbox without verified READY create")
        payload={**payload,"sandboxId":creation["sandbox_id"],
                 "operationDigest":digest}
        if self.authorize(scope,principal,"attach",payload) is not True:
            raise SandboxPermissionDenied("Attach permission required")
        permit = None
        if on_attach:
            permit=self.authorize(scope,principal,"initialize",payload)
            self._require_permit(permit,scope,principal,session_ref,
                                 creation["sandbox_id"],digest)
        b=self.store.begin(scope=scope,principal=principal,session_ref=session_ref,
                           create_operation_id=create_operation_id,
                           sandbox_id=creation["sandbox_id"],
                           key=idempotency_key,fingerprint=digest)
        if b["state"] != "PENDING":
            return b
        if not on_attach:
            return self.store.transition(binding_id=b["binding_id"],scope=scope,
                principal=principal,from_state="PENDING",to_state="ACTIVE",exit_code=0)
        b=self.store.transition(binding_id=b["binding_id"],scope=scope,
            principal=principal,from_state="PENDING",to_state="INITIALIZING")
        try:
            sandbox=self.native.connect(b["sandbox_id"])
            for step in on_attach:
                self._require_permit(permit,scope,principal,session_ref,
                                     b["sandbox_id"],digest)
                result=sandbox.commands.run(step["command"],
                    cwd=step["cwd"],timeout=step["timeoutSeconds"])
                if type(result.exit_code) is not int:
                    raise SandboxUnknown("Guest exit code missing")
                if result.exit_code != 0:
                    return self.store.transition(binding_id=b["binding_id"],scope=scope,
                        principal=principal,from_state="INITIALIZING",
                        to_state="FAILED",exit_code=result.exit_code)
        except Exception:
            try:
                self.store.transition(binding_id=b["binding_id"],scope=scope,
                    principal=principal,from_state="INITIALIZING",to_state="UNKNOWN")
            except SandboxConflict:
                pass
            raise SandboxUnknown("onAttach guest outcome ambiguous; no replay") from None
        return self.store.transition(binding_id=b["binding_id"],scope=scope,
            principal=principal,from_state="INITIALIZING",to_state="ACTIVE",exit_code=0)

    @staticmethod
    def _require_permit(permit,scope,principal,session_ref,sandbox_id,digest):
        if not isinstance(permit,InitializationPermit) or (
            permit.scope,permit.principal,permit.session_ref,
            permit.sandbox_id,permit.operation_digest) != (
            scope,principal,session_ref,sandbox_id,digest):
            raise SandboxPermissionDenied("Initialization permit scope/command mismatch")
        if not isinstance(permit.expires_at,(int,float)) or (
                permit.expires_at<=time() or permit.expires_at>time()+3600):
            raise SandboxPermissionDenied("Initialization permit expired or excessive TTL")

    def get(self, *, scope, principal, binding_id):
        self._identity(scope,principal,binding_id)
        b=self.store.get(binding_id=binding_id,scope=scope,principal=principal)
        if self.authorize_session(scope,principal,b["session_ref"]) is not True:
            raise SandboxPermissionDenied("Session access revoked")
        return b

    def reconcile(self, *, scope, principal, binding_id):
        """Operator-authorized fail-closed reconciliation of an interrupted Attach.

        Arbitrary Guest Shell cannot be classified as exactly-once from
        a disconnected caller, so no command is replayed or auto-promoted.
        """
        b=self.get(scope=scope,principal=principal,binding_id=binding_id)
        if self.authorize(scope,principal,"reconcile",{
                "bindingId":binding_id,"sessionRef":b["session_ref"],
                "sandboxId":b["sandbox_id"]}) is not True:
            raise SandboxPermissionDenied("Attach reconciliation requires operator")
        if b["state"]!="INITIALIZING":
            return b
        return self.store.transition(binding_id=binding_id,
            scope=scope,principal=principal,from_state="INITIALIZING",
            to_state="UNKNOWN")

    def reconnect(self, *, scope, principal, session_ref, binding_id):
        self._identity(scope,principal,session_ref,binding_id)
        if self.authorize_session(scope,principal,session_ref) is not True:
            raise SandboxPermissionDenied("Session access denied")
        b=self.get(scope=scope,principal=principal,binding_id=binding_id)
        if b["session_ref"]!=session_ref:
            raise SandboxPermissionDenied("Wrong Session")
        if b["state"]!="ACTIVE":
            raise SandboxConflict("Binding not ACTIVE; never replay initialization")
        if self.authorize(scope,principal,"attach",{
                "sessionRef":session_ref,"bindingId":binding_id}) is not True:
            raise SandboxPermissionDenied("Reconnect denied")
        # Reconnect checks the real native instance, without any Guest Shell
        # or re-run of the original onAttach commands.
        try:
            self.native.connect(b["sandbox_id"])
        except Exception:
            raise SandboxUnknown("Native Sandbox unavailable at reconnect") from None
        return b