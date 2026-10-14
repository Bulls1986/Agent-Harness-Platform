# DEV-SBX M1: native Cube Template and live Cube validation (2026-10-14)

Status: **SBX-M1 IN PROGRESS / Production NO-GO**. This is an implementation increment, not final acceptance.

## Frozen scope

Use Cube Python SDK 0.7.3 Template.list/get/build/set_alias/delete and native Cube Sandbox.create / Guest commands. No SandboxDefinition DSL, Registry, project model, Session Attach or separate execution engine. Native OCI image remains the template build input; raw Dockerfile is not supported by the current Cube Python Template.build API.

## Actual local validation

- WSL Ubuntu existing CubeAPI port 3000 and CubeMaster 8089, 7 native templates, 4 READY.
- SDK Template.list and Template.get of native tpl-363306ce3b21432cb1ae6536 succeeded.
- Raw SDK created Cube Sandbox 19655dc0fe2b4d63929eb596b128b544; guest git --version exit 0; killed.
- HTTP FastAPI TestClient -> actual PostgreSQL 16 -> native Template.get -> SDK Sandbox.create -> onCreate Guest git --version -> READY -> same Idempotency-Key replay -> GET Operation -> direct native detail -> kill: PASS. Real Sandbox 9751ec5a091e4bc3989987fc8a888de6; PG Operation sbx-op-1f57ca70fdb641489d501ce20aab4b55. Guest Git 2.39.5, exit code 0. Native template ID confirmed.
- Template/alias admin and negative tests RED then GREEN. Alias becomes a frozen tpl-* identity; retries use original PG Operation without resolving moved/deleted aliases.
- Lost ACK / ambiguous provider metadata tests RED then GREEN: a unique native Sandbox correlation must be verified against Template ID and metadata; UNKNOWN is never blindly retried or promoted to READY. Tests simulate lost ACK using SDK fake; not real Cube fault injection.
- All test resources were native-killed. CubeSDK was installed into a sibling scratch directory, never committed in repo.

## What has NOT passed

- Actual native Template.build, set_alias or delete against an isolated disposable template (the existing shared READY templates were NOT modified).
- Real Cube post-commit ACK loss injection and native Template admin mutation idempotency are not yet live verified.
- The final SBX-M1 full scope and latest PR-head CI/merge are not closed here. Do not mark M1 closed.
- M2 Attach, M3 Execute and M9 production deployment and load tests remain outside this increment.

## Retrospective and guardrail

Keep Template administration separate from normal Session permissions. Native metadata must be verified, and side effects must not be repeated after ambiguous results. TDD cannot substitute for actual Cube Guest evidence; prefer separate explicit local smoke scripts. No private consumer code, secrets or URLs.