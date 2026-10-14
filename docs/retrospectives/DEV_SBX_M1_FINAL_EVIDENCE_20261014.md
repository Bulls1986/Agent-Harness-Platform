# DEV-SBX SBX-M1 - Final evidence and bounded acceptance

Date: 2026-10-14. **Latest-head CI and PR merge pending at the time of this draft.**

## Frozen scope and real acceptance

Cube-native Template management through the installed `cubesandbox==0.7.3`
SDK: `Template.list/get/build/set_alias/delete`, READY alias resolution
to a real immutable native Template ID, and pre-Run Create with optional
`onCreate` Guest commands, PostgreSQL Operation identity and idempotency.
No custom Template DSL/Registry, provider-agnostic template builder, user
project/skills/agent manager, Session Attach, M3 Execute or M9 production
deployment.

### Real provider evidence

- Existing local WSL Cube API port 3000 / CubeMaster port 8089;
  SDK Template.list returned 7 templates, of which 4 were READY.
- Harness `POST /api/v1/sandboxes` via FastAPI TestClient -> actual
  PostgreSQL 16 -> Cube Template.get READY -> actual MicroVM ->
  guest `git --version` exit 0 -> READY -> identical Idempotency-Key
  returns the same Operation -> GET Operation -> native get_info template
  matches -> native test VM kill: PASS, independently verified twice in
  preceding PR #100. Test Cube IDs
  `9751ec5a091e4bc3989987fc8a888de6` and
  `a548e01f7a8345fda8eef5c3fd91467f` were cleaned.
- First isolated Template Build against obsolete local registry
  failed to pull the OCI image. The failed template
  `tpl-504732e329884e5584a117c2` was explicitly deleted and its
  absence confirmed. No existing READY template was touched.
- Second isolated native Build request accepted Template
  `tpl-08175407f9fa4d859c26464f`, build job
  `402b7e10-5839-4526-9f10-1287d64d71df`. The asynchronous build
  initially reported `BUILDING_EXT4 / 40%`; SDK Template.get
  transiently returned 404, and the test caller reached its own
  120-second timeout. **Cube's native job continued** and ultimately
  returned `ready / progress 100 / message READY`; native Template.get
  confirmed READY.
- The authorized CubeTemplateGateway performed an actual native Alias
  change to `sbxm1-validation-1014`; native resolver returned exactly
  `tpl-08175407f9fa4d859c26464f`. Native `delete` then succeeded;
  post-delete Cube inventory returned to exactly 7 templates. No
  disposable Template remains.
- Async verification script fixed to use native
  `Template.get_build_status` for PENDING/RUNNING stages and to
  avoid deleting an in-progress build. It requires explicit
  temporary-template-mutation opt-in and does not alter shared templates.

### Contract and regression evidence

- SBX isolated unit/HTTP and **real PostgreSQL** tests: 22/22 passed
  before closeout changes. Covers native Template admin policy and
  invalid options; Alias replay/freeze; blocked crossing Scope; Create
  idempotency; Guest nonzero and UNKNOWN; uniquely verified native
  metadata-based UNKNOWN reconciliation without a replay.
- Top-level repository regression 28/28 passed;
  OpenSpec Strict, checked-in OpenAPI semantic contract, and
  architecture guard passed.
- Final latest-head official CI URLs and verdicts must be recorded
  after the closeout PR is green; a previous head alone is not evidence
  for an edited head.

### Explicit limits, not silent passes

- Native lost HTTP/SDK **post-commit ACK** and network packet faults
  were **not exercised against the live Cube VM**. Failure-injection
  contract tests used synthetic Cube SDK with PG where applicable;
  UNKNOWN remains blocked, no claim of exactly-once Shell side effects.
- Template administrator Build/Alias/Delete operations follow the
  Cube native API; they do not gain a new Harness-owned exactly-once
  guarantee. A lost native admin ACK requires inspecting the native
  job/template before any resubmit. This is a declared
  production-operational limitation, **not a new V1 feature**.
- Enterprise Gateway/IdP, cross-host isolation, production capacity,
  durable consumer Workspace recovery and M9 GO remain unverified.
- SBX-M2 Attach, SBX-M3 Execute, SBX-M4 full E2E have not started.
  Closing M1 must not imply the full DEV-SBX is CLOSED.

## Retrospective

Cube Template Build is asynchronous. A successful Build acceptance
precedes Template.get visibility; a transient 404 must not be treated
as proof of no native effect, and deleting a RUNNING build is
rejected by Cube. The correct progress source is the native job ID and
`Template.get_build_status`. Execute only the frozen Template/Instance
operations and test against isolated disposable assets. Do not expand
scope to Registry, custom template orchestration, or production
cluster deployment.