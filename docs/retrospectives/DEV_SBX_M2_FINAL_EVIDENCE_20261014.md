# DEV-SBX SBX-M2 路 Session Attach / onAttach - acceptance evidence

Date: 2026-10-14. **Only frozen SBX-M2 scope.** M3 Execute and M4 holistic E2E untouched. This is not enterprise production GO.

## TDD / implementation

- RED: dedicated Attach tests initially failed importing absent `poc.sandbox.sbx_attach`.
- Implemented Session Attach independent of Run, with actual PostgreSQL authoritative M1 Create Operation READY lookup, unique writable Sandbox-to-Session binding and scope/principal/idempotency protections.
- Enforced separate trusted Session authority, Policy Attach authorization, and server-issued, short-lived `InitializationPermit` scoped to specific Caller, Session, native Sandbox and exact ordered Guest command digest. TTL rechecked before each command.
- `onAttach` uses only Cube guest `commands.run`; no Host Shell fallback. A failed command is FAILED; an ACK-unknown is UNKNOWN, never repeated by reconnection. Reconnect performs actual Cube native connect and **does not** rerun initialization.
- Interrupted INITIALIZING can only be operator-reconciled to UNKNOWN (fail closed), not auto promoted to ACTIVE. Session revocation denies read/reconnect.
- API addition: POST /api/v1/sandbox-bindings, GET /api/v1/sandbox-bindings/{id}, POST /{id}/reconnect, POST /{id}/reconcile. Checked-in separate OpenAPI-sbx-m2 and documentation. No generic Execute API.

## Real local evidence

Existing WSL Cube API, SDK 0.7.3 and actual PostgreSQL 16, M1 real Template `tpl-363306ce3b21432cb1ae6536`.

Real **HTTP Create -> persisted PG Operation -> Cube MicroVM -> onCreate Git seed repository with committed README -> Session Attach via HTTP -> Cube Guest git clone, fetch and rev-parse -> ACTIVE Binding -> same-key retry -> native Cube reconnect -> preserved session file -> cross-Session binding 409, unknown-Session 403 -> native kill cleanup**: PASS.

First real Cube: `dc521ed35fdf48e69e84e01df5d33e66`, create Operation `sbx-op-eb4c27d3d95245aaa134f6e0bff34054`, Binding `sbx-bind-2c2d6be603b24a7297b3599adc02a713`; native kill confirmed.

Revalidated after reconnect code update with new Cube `9dc0371c460647e888f2d37f3e99c366`, create Operation `sbx-op-279c9f9e80d7459fae32a185f899fcfa`, Binding `sbx-bind-5a954db91044454e819254b38528e55b`. Same behavior PASS; native kill confirmed.

## Negative gates

- Another Session (even same trusted Scope) cannot reuse occupied writable Sandbox.
- Cross-Scope ownership and revoked/unknown Session cannot attach, read or reconnect.
- Missing/expired/altered initialization permit denied before Guest side effects.
- Guest nonzero -> FAILED and no replay; Guest ACK ambiguous -> UNKNOWN and no replay.
- Interruption of persistent INITIALIZING requires independently authorized operator reconciliation to UNKNOWN without Guest replay.
- Unsafe noncanonical cwd rejected; Harness never implicitly overwrites Git checkout or pulls dirty files; exact user-supplied authorized commands only.
- M5 Fencing and model-only zero-Cube behavior were not altered and remain covered by official regression.

## Honest limitations

- Actual network packet loss or abrupt native Worker SIGKILL during `onAttach` was not injected. Synthetic/native-error negative contracts plus real PG demonstrate fail-closed, **not exactly-once arbitrary Guest Shell**.
- Authentication/Session authorization/Policy were injected through local synthetic adapters for the smoke. A production Gateway/IdP is **not** delivered or verified.
- Session binding does not grant generic Shell execution; M3 Execute, detach/release, pause/resume, Workspace restore and production load are not included.
- This OpenSpec is the multi-milestone DEV-SBX active change; close M2 tasks only. Do not archive until M4.

## Gate bookkeeping

The final official GitHub PR latest-head Architecture, M5 Cube PG, full PG/Hatchet/SDK/Inspector CI and strict OpenSpec verdicts must be verified before marking M2 CLOSED. See the M2 PR and `docs/DEVELOPMENT_MILESTONES.md`.