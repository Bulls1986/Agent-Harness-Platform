"""DEV-M5 HC-03: provider-neutral, **pure** tool admission against trusted facts.

An ExecutionClaim is UNTRUSTED. Callers must load ExecutionRecord and
SandboxRecord from the trusted Harness persistence/Provider binding, never
from workflow payload, User Prompt, Agent SDK session or raw sandbox ID.

This validates an authority boundary only, and DOES NOT claim actual Cube
guest, native OpenCode paths or worker failover are integrated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


class GateDenied(PermissionError):
    pass


@dataclass(frozen=True)
class ExecutionRecord:
    run_id: str
    step_id: str
    attempt_id: str
    execution_id: str
    plan_version: int
    provider_binding_ref: str
    principal_ref: str
    isolation_scope: str
    workspace_ref: str
    runtime_adapter_version: str
    environment_digest: str
    owner_id: str
    fencing_epoch: int
    lease_expires_at: float
    capabilities: FrozenSet[str]


@dataclass(frozen=True)
class ExecutionClaim:
    run_id: str
    step_id: str
    attempt_id: str
    execution_id: str
    plan_version: int
    provider_binding_ref: str
    principal_ref: str
    isolation_scope: str
    workspace_ref: str
    runtime_adapter_version: str
    environment_digest: str
    owner_id: str
    fencing_epoch: int

    @classmethod
    def from_record(cls, record: ExecutionRecord) -> "ExecutionClaim":
        return cls(**{name:getattr(record,name) for name in cls.__dataclass_fields__})


@dataclass(frozen=True)
class SandboxRecord:
    sandbox_id: str
    isolation_scope: str
    workspace_ref: str
    environment_digest: str
    binding_generation: int
    owner_id: str
    fencing_epoch: int


@dataclass(frozen=True)
class VerifiedAdmission:
    execution_id: str
    action: str
    sandbox_ref: str | None


class TrustedExecutionGate:
    """A deterministic checker, not a sandbox authority or execution backend."""

    def authorize(self,claim: ExecutionClaim,
                  authority: ExecutionRecord | None,
                  action: str, *,
                  now: float, sandbox: SandboxRecord | None=None) -> VerifiedAdmission:
        if authority is None or claim is None:
            raise GateDenied("UNAUTHORIZED: missing trusted execution authority")
        if authority.lease_expires_at<=now:
            raise GateDenied("LEASE_EXPIRED")
        if authority.fencing_epoch<1 or authority.plan_version<1:
            raise GateDenied("STALE_EXECUTION_OWNER")
        for key in ExecutionClaim.__dataclass_fields__:
            claim_value=getattr(claim,key)
            expected=getattr(authority,key)
            if not claim_value or claim_value!=expected:
                raise GateDenied("UNAUTHORIZED: "+key+" mismatch")
        if not action or action not in authority.capabilities:
            raise GateDenied("CAPABILITY_NOT_GRANTED")
        requires_guest=action.startswith(("files.","shell.","git."))
        if not requires_guest:
            # Pure/remote-model runs never silently allocate a Cube sandbox.
            return VerifiedAdmission(authority.execution_id,action,None)
        if sandbox is None:
            raise GateDenied("SANDBOX_REQUIRED: no Host Shell fallback")
        if (not sandbox.sandbox_id or sandbox.binding_generation<1
                or sandbox.isolation_scope!=authority.isolation_scope
                or sandbox.workspace_ref!=authority.workspace_ref
                or sandbox.environment_digest!=authority.environment_digest
                or sandbox.owner_id!=authority.owner_id
                or sandbox.fencing_epoch!=authority.fencing_epoch):
            raise GateDenied("SCOPE_MISMATCH / STALE_EXECUTION_OWNER / ENVIRONMENT_DRIFT")
        return VerifiedAdmission(authority.execution_id,action,sandbox.sandbox_id)
