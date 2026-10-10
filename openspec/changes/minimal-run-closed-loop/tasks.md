# Tasks: Minimum Runnable Agent Harness Loop

> Check a task only when its named verification has actually passed. “Code written” alone is not completion. The POC uses **Docker PostgreSQL** (not SQLite). HC-01/02/03 architecture remains the contract; DEV-PDLC-01～05 remain later work.

## 1. Initialize OpenSpec and baseline the scope

- [x] 1.1 Initialize OpenSpec v1.12.0 (`openspec/config.yaml`, `openspec/changes/`) and create `minimal-run-closed-loop`; CLI and directory verified.
- [x] 1.2 Complete proposal, four capability specs (including required Run Inspector), design and task list; `openspec validate minimal-run-closed-loop --strict` PASS on 2026-10-10 (4/4 artifacts complete).
- [x] 1.3 Update repository README and development backlog to link this OpenSpec change and distinguish limited POC from production acceptance.

## 2. Docker PostgreSQL + Harness Task Facts (HC-02)

- [x] 2.1 Start isolated `postgres:16-alpine` using `docker compose up -d postgres` and verify healthy; independently query both `hatchet_poc` and `harness_poc` databases (already verified in current local environment).
- [x] 2.2 Confirm `PgFacts` schema creation against Docker `harness_poc` (local smoke PASS; broader transactional tests still required).
- [ ] 2.3 Verify true PG Run+Steps+Outbox atomic creation, stable command key and separate Hatchet engine DB; automated integration test asserts persisted rows after restart.
- [ ] 2.4 Add and pass negative tests: duplicate Run, invalid dependency, missing Provider Binding, late terminal mutation, monotonic event sequence.
- [ ] 2.5 Add and pass lost workflow creation ACK fault-injection: DISPATCHING→BLOCKED_UNKNOWN and second submission blocked; document provider reconciliation limitation.

## 3. Real Hatchet + real public SDK handoff (HC-01/03 model-only path)

- [ ] 3.1 Pin Hatchet SDK 1.42.1 / Embedded Engine v0.110.5, Pydantic AI 2.54.0 and OpenAI Agents 0.23.1; verify dependency install/build succeeds using a documented reproducible environment (Docker registry error currently BLOCKS application build).
- [ ] 3.2 Run **one real** Hatchet Workflow through two SDK Tasks; verify actual provider WorkflowRun ID persisted separately from platform Run ID.
- [ ] 3.3 Verify Step A Pydantic output is persisted/checked before Step B OpenAI invocation; assert one Attempt per successful Step and zero external model requests.
- [ ] 3.4 Verify business Run cannot become COMPLETED until both persisted Step outcomes and Provider Binding exist; confirm terminal Event and unique ordered Event cursor.
- [ ] 3.5 Verify model-only path does not allocate Cube and privileged Shell/Git without grant fails closed; don't classify as full HC-03 Cube acceptance.

## 4. Run Inspector (mandatory minimum-loop acceptance)

- [ ] 4.1 Add a local-only Inspector HTTP API: create real Run and Outbox, list stored Runs, read one persisted Run and events after a cursor; verify API smoke with Docker PostgreSQL and duplicate/missing Run negatives.
- [ ] 4.2 Implement minimal browser UI for starting a Run, viewing CREATED/RUNNING/COMPLETED/UNKNOWN states, per-Agent Step/Attempt/output and Provider Binding. Verify visually against **real stored data**, not fake fixtures.
- [ ] 4.3 Add chronological durable domain event timeline; distinguish Step-level `runtime.run.completed` from the sole parent `run.completed`. Verify event cursor monotonicity and no duplicate business terminal Event.
- [ ] 4.4 Refresh browser and restart Inspector HTTP process; confirm the Run history, Step outputs and events still load from PostgreSQL. Label local-only POC and NOT_TESTED gates visibly.
- [ ] 4.5 Verify that missing DB/Engine generates an error rather than a successful animation, privileged outputs are text-escaped, and UI never allocates Session-specific Worker processes.

## 5. CI, operational reproducibility and closeout

- [ ] 5.1 Add CI Linux PostgreSQL service job and a local reproducible entry point that executes the actual Hatchet/SPI/PG closed loop, not SDK mocks.
- [ ] 5.2 Run all new unit/negative/integration tests and existing architecture guard; record commands, outputs and authoritative CI run links.
- [ ] 5.3 Record technical coverage explicitly: single-Run Hatchet/PG/2 SDK evidence; real Token SSE/Approval/Receipt UNKNOWN/Cube worker-failover/100 concurrency remain OPEN.
- [ ] 5.4 Review diff, remove secrets/cache/build artifacts, create PR and merge only if CI and negative gates are green.

## 6. Subsequent increments (tracked, not blockers for first model-only closed loop)

- [ ] 6.1 HC-02 production increment: PG Schema review, Provider query/dedup ACK-lost reconciliation, transactional inbox and external non-idempotent Tool Receipt evidence.
- [ ] 6.2 HC-03 production increment: true trusted ExecutionContext issuing, Scope/Lease/Fencing, Cube same-workspace rebind after worker crash, blocked Host Shell paths.
- [ ] 6.3 Protocol/operations: live Token SSE with replay/cancel, durable WAITING_APPROVAL/INPUT, resource density at 100 Active Runs.
- [ ] 6.4 M0–M4 PDLC legacy inventory and migration only via DEV-PDLC-01～05; not part of this minimal loop.