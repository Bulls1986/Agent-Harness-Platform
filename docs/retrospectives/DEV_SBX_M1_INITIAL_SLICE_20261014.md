# DEV-SBX M1 initial implementation review (2026-10-14)

## Bounded deliverable

This PR introduces only a pre-Run Cube-native **Create/onCreate** slice:
- an immutable native `tpl-...` template-ID Create adapter; selected native Cube
  parameters and guarded Guest commands, not a new sandbox definition DSL;
- a real PostgreSQL operation table scoped by trusted principal and project,
  unique per Idempotency-Key, with CREATING/INITIALIZING/READY/FAILED/UNKNOWN;
- optional separate HTTP API factory with trusted Gateway/Policy injection
  (`POST /api/v1/sandboxes`, `GET /api/v1/sandbox-operations/{id}`);
- an OpenAPI snapshot and API guide; synthetic Cube transport contract tests,
  HTTP tests and real PostgreSQL operation tests.

## Red / Green

- RED: seven first contract tests failed to import the absent management module.
- GREEN: 10 synthetic Cube / HTTP tests and 3 real PostgreSQL tests pass.
- An initial PG test failed because the FakeCube returned the same
  `cube-1` native Sandbox ID in multiple independent tests while the
  production-like table correctly enforced global uniqueness. The fake now
  generates distinct IDs; retested all 13/13 with actual PostgreSQL 16.
- Shared M5 Code/Runtime facts and Inspector remain untouched.

## Unverified / carry forward

- Local Python has no installed `cubesandbox` SDK and no configured
  `CUBE_API_URL`; **a real Cube Template, Create or Guest command was
  NOT verified** in this implementation slice.
- Native Template build/list/commit/delete and mutable Alias resolution
  remain OPEN for SBX-M1. Only immutable native Template IDs are admitted.
- SDK-specific optional Cube create parameters require native version
  verification; the current bounded allowlist must not be described as
  complete native passthrough.
- The status/Operation API does not yet perform automatic native
  ACK-lost reconciliation. UNKNOWN never re-dispatches Create or Commands.
- This does not implement M2 Attach, M3 Execute / lifecycle, or M9
  production security, deployment, capacity and cross-host gates.

## Reusable safeguard

Never re-run native Create/Guest commands solely because HTTP timed out.
Persist correlation and CREATING before calling Cube; treat ambiguous native
or guest results as UNKNOWN. Freeze immutable template ID in the operation,
and do not accept an arbitrary CubeMaster native parameter as authorized.
No host subprocess fallback or business consumer implementation.