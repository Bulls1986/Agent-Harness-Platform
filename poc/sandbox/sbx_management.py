"""DEV-SBX M1: Cube-native pre-Run sandbox create and durable idempotency.

This is not a second Cube lifecycle engine or a new template DSL.
M5 trusted Run/Execution binding remains independent. Cube native Template admin / alias lookup is delegated to the SDK, not
reimplemented as a Registry.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from uuid import uuid4


class SandboxConflict(RuntimeError):
    pass


class SandboxPermissionDenied(PermissionError):
    pass


class SandboxUnknown(RuntimeError):
    """Provider side effect may have committed; never replay without evidence."""


# Verified known Cube SDK create kwargs. No permissive **kwargs proxy to CubeMaster.
# Extend only after testing a specific native SDK version and Policy decision.
_ALLOWED_NATIVE = frozenset({
    "template", "timeout", "lifecycle", "env_vars", "volume_mounts"
})


def _canonical_workdir(value):
    if (not isinstance(value, str) or
            not (value == "/workspace" or value.startswith("/workspace/")) or
            "//" in value or "\\" in value or
            any(part in (".", "..") for part in value.split("/"))):
        raise ValueError("onCreate cwd must be canonical inside /workspace")
    return value


def _validate(cube, commands, *, allow_alias=False):
    if not isinstance(cube, dict) or set(cube) - _ALLOWED_NATIVE:
        raise ValueError("Unsupported or privileged Cube native create parameter")
    template = cube.get("template")
    if not isinstance(template, str) or not template or len(template) > 128:
        raise ValueError("Native Cube template ID/alias required")
    if not template.startswith("tpl-"):
        import re
        if not allow_alias or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", template):
            raise ValueError("Native Cube Alias requires verified resolver")
    if template in ("latest", "default"):
        raise ValueError("Floating template names cannot become frozen Run identity")
    if ("timeout" in cube and
            (type(cube["timeout"]) is not int or not 1 <= cube["timeout"] <= 86400)):
        raise ValueError("Invalid Cube native timeout")
    for key in ("env_vars", "volume_mounts", "lifecycle"):
        if key in cube and not isinstance(cube[key], dict):
            raise ValueError("Invalid Cube native mapping: " + key)
    if not isinstance(commands, list) or len(commands) > 16:
        raise ValueError("onCreate requires at most 16 commands")
    for step in commands:
        if not isinstance(step, dict) or set(step) != {"command", "cwd", "timeoutSeconds"}:
            raise ValueError("Unknown onCreate command shape")
        cmd, timeout = step["command"], step["timeoutSeconds"]
        if not isinstance(cmd, str) or not cmd.strip() or len(cmd) > 4096 or "\x00" in cmd:
            raise ValueError("Invalid onCreate guest command")
        _canonical_workdir(step["cwd"])
        if type(timeout) is not int or not 1 <= timeout <= 3600:
            raise ValueError("Invalid onCreate timeout")
    return template


class CubeNativeCreateTransport:
    """Native Cube SDK create and Guest commands, never host subprocess.

    The sdk argument is used for deterministic contract tests only. In live
    use SDK connection/credentials come from deployment configuration.
    """

    def __init__(self, sdk=None):
        if sdk is None:
            if not os.getenv("CUBE_API_URL"):
                raise RuntimeError("Real CUBE_API_URL is required")
            from cubesandbox import Sandbox
            sdk = Sandbox
        self.sdk = sdk

    def create(self, cube, metadata):
        sandbox = self.sdk.create(**{**cube, "metadata": metadata})
        if not isinstance(sandbox.sandbox_id, str) or not sandbox.sandbox_id:
            raise SandboxUnknown("Cube create ACK lacks native sandbox ID")
        return sandbox

    def list(self):
        return self.sdk.list()

    def inspect(self, native_sandbox_id):
        return self.sdk.connect(native_sandbox_id).get_info()

    @staticmethod
    def command(sandbox, step):
        return sandbox.commands.run(
            step["command"], cwd=step["cwd"], timeout=step["timeoutSeconds"])


class PgSandboxCreateStore:
    """Minimal durable Operation facts, separate from M5 active-Run binding.

    This table records only create/initialize operations and native correlation;
    it does not mirror Cube VM state or manage template versions.
    """

    FIELDS = ("operation_id", "scope", "principal", "idempotency_key",
              "fingerprint", "template_id", "state", "sandbox_id", "exit_code")

    def __init__(self, facts):
        from poc.closed_loop.facts import PgFacts
        if not isinstance(facts, PgFacts):
            raise ValueError("Actual Harness PG facts required")
        self.facts = facts
        with facts.tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_sbx_create_op (
                    operation_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL, principal TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    template_id TEXT NOT NULL, state TEXT NOT NULL
                        CHECK (state IN
                            ('PENDING','CREATING','INITIALIZING',
                             'READY','FAILED','UNKNOWN')),
                    sandbox_id TEXT UNIQUE,
                    exit_code INT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE(scope,principal,idempotency_key)
                )
            """)

    @classmethod
    def _row(cls, row):
        return dict(zip(cls.FIELDS, row)) if row else None

    def begin(self, *, scope, principal, key, fingerprint, template_id):
        operation_id = "sbx-op-" + uuid4().hex
        with self.facts.tx() as c:
            c.execute("""
                INSERT INTO harness_sbx_create_op
                  (operation_id,scope,principal,idempotency_key,fingerprint,template_id,state)
                VALUES (%s,%s,%s,%s,%s,%s,'PENDING')
                ON CONFLICT (scope,principal,idempotency_key) DO NOTHING
            """, (operation_id,scope,principal,key,fingerprint,template_id))
            row = c.execute(
                "SELECT " + ",".join(self.FIELDS) +
                " FROM harness_sbx_create_op WHERE scope=%s AND principal=%s "
                "AND idempotency_key=%s FOR UPDATE",
                (scope,principal,key)).fetchone()
            result = self._row(row)
            if result["fingerprint"] != fingerprint:
                raise SandboxConflict("Idempotency-Key already used for different request")
            return result

    def lookup(self, *, scope, principal, key):
        with self.facts.tx() as c:
            row = c.execute(
                "SELECT " + ",".join(self.FIELDS) +
                " FROM harness_sbx_create_op WHERE scope=%s AND principal=%s "
                "AND idempotency_key=%s",
                (scope, principal, key)).fetchone()
        return self._row(row)

    def get(self, operation_id, scope, principal):
        with self.facts.tx() as c:
            row = c.execute(
                "SELECT " + ",".join(self.FIELDS) +
                " FROM harness_sbx_create_op WHERE operation_id=%s "
                "AND scope=%s AND principal=%s",
                (operation_id,scope,principal)).fetchone()
        if not row:
            raise KeyError(operation_id)
        return self._row(row)

    def transition(self, operation_id, scope, principal, expected, state, **values):
        if state not in ("CREATING","INITIALIZING","READY","FAILED","UNKNOWN"):
            raise ValueError("Invalid Operation transition")
        if set(values) - {"sandbox_id", "exit_code"}:
            raise ValueError("Unknown Operation field")
        set_clause = ["state=%s"] + [k + "=%s" for k in values]
        params = [state, *values.values(), operation_id, scope, principal, expected]
        with self.facts.tx() as c:
            row = c.execute(
                "UPDATE harness_sbx_create_op SET " + ",".join(set_clause) +
                " WHERE operation_id=%s AND scope=%s AND principal=%s AND state=%s "
                "RETURNING " + ",".join(self.FIELDS), params).fetchone()
        if not row:
            raise SandboxConflict("Stale or unauthorized Sandbox Operation")
        return self._row(row)


class SandboxCreateService:
    def __init__(self, store, native: CubeNativeCreateTransport, *, authorize, template_resolver=None):
        if not callable(authorize) or not isinstance(native, CubeNativeCreateTransport):
            raise ValueError("Explicit Policy and real Cube Transport port required")
        self.store, self.native, self.authorize = store, native, authorize
        self.template_resolver = template_resolver

    def create(self, *, scope, principal, idempotency_key, cube, on_create):
        if not all(isinstance(v, str) and v and v == v.strip()
                   for v in (scope, principal, idempotency_key)):
            raise ValueError("Trusted scope, principal, Idempotency-Key required")
        if len(idempotency_key) > 256:
            raise ValueError("Idempotency-Key too long")
        # Trusted caller/Policy is server-side, never taken from cube metadata.
        if self.authorize(scope, principal, "create", cube) is not True:
            raise SandboxPermissionDenied("Sandbox Create denied")
        selected_template = _validate(cube, on_create,
                                      allow_alias=self.template_resolver is not None)
        # Fingerprint the request BEFORE alias resolution; retries must not
        # depend on whatever Cube alias happens to point to later.
        payload = json.dumps({"cube": cube, "onCreate": on_create},
                             sort_keys=True, separators=(",",":"), ensure_ascii=True)
        fingerprint = sha256(payload.encode("utf-8")).hexdigest()
        prior = self.store.lookup(scope=scope, principal=principal, key=idempotency_key)
        if prior is not None:
            if prior["fingerprint"] != fingerprint:
                raise SandboxConflict("Idempotency-Key already used for another request")
            return prior
        template_id = (self.template_resolver(selected_template)
                       if self.template_resolver is not None else selected_template)
        if not isinstance(template_id, str) or not template_id.startswith("tpl-"):
            raise ValueError("Resolved native Template ID missing")
        op = self.store.begin(scope=scope, principal=principal,
                              key=idempotency_key, fingerprint=fingerprint,
                              template_id=template_id)
        if op["state"] != "PENDING":
            return op  # replay is read-only even after UNKNOWN
        op = self.store.transition(op["operation_id"], scope, principal,
                                   "PENDING", "CREATING")
        correlation = {
            "harness_sbx_operation_id": op["operation_id"],
            "harness_sbx_scope_digest": sha256(scope.encode()).hexdigest(),
        }
        try:
            sandbox = self.native.create({**cube, "template": op["template_id"]}, correlation)
        except Exception:
            self._unknown(op["operation_id"], scope, principal, "CREATING")
            raise SandboxUnknown("Cube create outcome unknown; reconcile before retry") from None
        target = "INITIALIZING" if on_create else "READY"
        try:
            op = self.store.transition(op["operation_id"], scope, principal,
                                       "CREATING", target, sandbox_id=sandbox.sandbox_id)
        except Exception:
            self._unknown(op["operation_id"], scope, principal, "CREATING")
            raise SandboxUnknown("Cube create PG ACK unknown; no blind reallocation") from None
        if not on_create:
            return op
        for step in on_create:
            try:
                result = self.native.command(sandbox, step)
            except Exception:
                self._unknown(op["operation_id"], scope, principal, "INITIALIZING")
                raise SandboxUnknown("Guest initialization outcome unknown; no blind replay") from None
            if type(result.exit_code) is not int:
                self._unknown(op["operation_id"], scope, principal, "INITIALIZING")
                raise SandboxUnknown("Guest command result lacks exit code") from None
            if result.exit_code != 0:
                return self.store.transition(op["operation_id"], scope, principal,
                                             "INITIALIZING", "FAILED",
                                             exit_code=result.exit_code)
        return self.store.transition(op["operation_id"], scope, principal,
                                     "INITIALIZING", "READY", exit_code=0)

    def _unknown(self, op, scope, principal, expected):
        try:
            self.store.transition(op, scope, principal, expected, "UNKNOWN")
        except Exception:
            pass  # durable in-flight state remains; do not redispatch

    def reconcile(self, *, scope, principal, operation_id):
        """Read-only native evidence can identify an UNKNOWN VM, never replay Guest.

        We deliberately do NOT change UNKNOWN to READY: onCreate may have
        committed before losing its ACK. A recovered sandbox still requires
        explicit remediation/cleanup, not silent reuse as clean Workspace.
        """
        op = self.store.get(operation_id, scope, principal)
        if op["state"] != "UNKNOWN":
            return op
        expected = {
            "harness_sbx_operation_id": op["operation_id"],
            "harness_sbx_scope_digest": sha256(scope.encode()).hexdigest(),
        }
        try:
            if op["sandbox_id"]:
                matches=[op["sandbox_id"]]
            else:
                rows=self.native.list()
                if not isinstance(rows, list) or len(rows)>1000:
                    raise ValueError("Native list incomplete")
                matches=[]
                for row in rows:
                    if not isinstance(row, dict):
                        raise ValueError("Invalid Cube listing")
                    if row.get("metadata")==expected:
                        sid=row.get("sandboxID") or row.get("sandbox_id")
                        if not isinstance(sid,str) or not sid:
                            raise ValueError("Missing native Cube ID")
                        matches.append(sid)
            if len(matches)!=1:
                raise ValueError("Native Cube correlation absent or ambiguous")
            native_id=matches[0]
            detail=self.native.inspect(native_id)
            metadata=(detail.get("metadata") if isinstance(detail,dict)
                      else getattr(detail,"metadata",None))
            detail_id=(detail.get("sandboxID",detail.get("sandbox_id"))
                       if isinstance(detail,dict)
                       else getattr(detail,"sandbox_id",None))
            template=(detail.get("templateID",detail.get("template_id"))
                      if isinstance(detail,dict)
                      else getattr(detail,"template_id",None))
            if (metadata!=expected or detail_id!=native_id
                    or template!=op["template_id"]):
                raise ValueError("Native Cube metadata/template mismatch")
            if op["sandbox_id"] is None:
                op=self.store.transition(op["operation_id"],scope,principal,
                                         "UNKNOWN","UNKNOWN",sandbox_id=native_id)
        except Exception:
            raise SandboxUnknown("Native evidence not unique/verified; remains UNKNOWN") from None
        return op

    def get(self, *, scope, principal, operation_id):
        return self.store.get(operation_id, scope, principal)