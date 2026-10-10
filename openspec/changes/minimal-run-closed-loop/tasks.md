# Tasks: Minimum Runnable Agent Harness Loop

> Check a task only when its named verification has actually passed. “Code written” alone is not completion. The POC uses **Docker PostgreSQL** (not SQLite). HC-01/02/03 architecture remains the contract; DEV-PDLC-01～05 remain later work.

## 1. Initialize OpenSpec and baseline the scope

- [x] 1.1 Initialize OpenSpec v1.12.0 (`openspec/config.yaml`, `openspec/changes/`) and create `minimal-run-closed-loop`; CLI and directory verified.
- [x] 1.2 Complete proposal, four capability specs (including required Run Inspector), design and task list; `openspec validate minimal-run-closed-loop --strict` PASS on 2026-10-10 (4/4 artifacts complete).
- [x] 1.3 Update repository README and development backlog to link this OpenSpec change and distinguish limited POC from production acceptance.

## 2. Docker PostgreSQL + Harness Task Facts (HC-02)

- [x] 2.1 Start isolated `postgres:16-alpine` using `docker compose up -d postgres` and verify healthy; independently query both `hatchet_poc` and `harness_poc` databases (already verified in current local environment).
- [x] 2.2 Confirm `PgFacts` schema creation against Docker `harness_poc` (local smoke PASS; broader transactional tests still required).
- [x] 2.3 Docker PG Run+Steps+Outbox single-transaction tests + distinct Hatchet DB + actual CLI/Inspector Run; restart inspector preserved Step/Provider/14 Events — LOCAL and CI PASS.
- [x] 2.4 Duplicate Run / missing parent / missing Binding / terminal immutability / monotonic cursor negative PG tests — 7 contract tests PASS (Docker PG; no skipped cases).
- [x] 2.5 Simulated lost workflow create ACK: DISPATCHING→BLOCKED_UNKNOWN and repeated dispatch rejected — PG test PASS; true Provider ACK-loss lookup/reconcile remains 6.1 OPEN.

## 3. Real Hatchet + real public SDK handoff (HC-01/03 model-only path)

- [x] 3.1 Exact Hatchet SDK 1.42.1 / Engine v0.110.5 / Pydantic AI 2.54.0 / OpenAI Agents 0.23.1 pinned; Docker image BUILD PASS using cached trustworthy Azure Python base+mirror (Docker Hub auth error documented), CI install PASS.
- [x] 3.2 Real Hatchet Embedded + PG + two real SDK Tasks in the same Run — LOCAL CLI and CI PASS; Provider ID separate from Platform Run ID.
- [x] 3.3 Pydantic A persisted output required before OpenAI B; each Step 1 Attempt; external model calls 0 — LOCAL+CI PASS.
- [x] 3.4 Business Run COMPLETED only after two persisted successful Steps + binding; 14 persistent events, one Domain run.completed — LOCAL+CI PASS.
- [x] 3.5 Model-only 0 Cube and privileged Shell/Git without grant fail closed; offline Runtime SPI 6 guard scenarios PASS; full real Cube still NOT_TESTED.

## 4. Run Inspector (mandatory minimum-loop acceptance)

- [x] 4.1 Inspector API POST/create real PG Run, GET/list/details/events after cursor, missing Run & no Runner 4xx/503 — LOCAL Docker PG 7 tests and CI PASS.
- [x] 4.2 Real localhost browser HTML served HTTP 200; page JS fetches actual PG Run ID/Step/output/Binding, no mock fixtures; live HTTP Run ID run-1f9cc8929f534de3b5f273701c59c543 VERIFIED. A separate manual cross-browser visual QA is optional after this POC.
- [x] 4.3 Domain timeline 14 PG Events, monotonic seq; runtime.run.completed twice, business run.completed once; black-box after-cursor and PG contract PASS.
- [x] 4.4 Real Docker Inspector restart then same Run ID query preserves 14 events/Step outputs/Workflow ID; CI process restart black-box PASS; page labels POC/NOT_TESTED.
- [x] 4.5 Missing Runner returns 503, DB read fails instead of mock success, renderer exclusively textContent and single shared Hatchet Worker (no Session-specific worker) — contract tests + code review PASS.

## 5. CI, operational reproducibility and closeout

- [x] 5.1 Real Linux PG16 service CI includes exact SDK Engine and real HTTP Inspector E2E; CI run 38037718378 SUCCESS; local Compose reproducible using cached image/mirror.
- [x] 5.2 7 PG/API tests, 8 architecture guards, 183 docs links + real Engine/Inspector/restart tests PASS; CI 38037718378 and architecture 38037718366 SUCCESS. Retrospective captures exact commands.
- [x] 5.3 Persisted [post-implementation retrospective](../../../docs/retrospectives/MINIMAL_CLOSED_LOOP_20261010.md) with Run/Workflow IDs, test evidence and NOT_TESTED gates; real Token SSE/Approval/Receipt/Cube/100 concurrency still OPEN.
- [ ] 5.4 Review diff, remove secrets/cache/build artifacts, create PR and merge only if CI and negative gates are green.

## 6. Subsequent increments (tracked, not blockers for first model-only closed loop)

- [ ] 6.1 HC-02 production increment: PG Schema review, Provider query/dedup ACK-lost reconciliation, transactional inbox and external non-idempotent Tool Receipt evidence.
- [ ] 6.2 HC-03 production increment: true trusted ExecutionContext issuing, Scope/Lease/Fencing, Cube same-workspace rebind after worker crash, blocked Host Shell paths.
- [ ] 6.3 Protocol/operations: live Token SSE with replay/cancel, durable WAITING_APPROVAL/INPUT, resource density at 100 Active Runs.
- [ ] 6.4 M0–M4 PDLC legacy inventory and migration only via DEV-PDLC-01～05; not part of this minimal loop.