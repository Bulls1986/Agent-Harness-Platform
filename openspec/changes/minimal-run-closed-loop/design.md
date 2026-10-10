# Design: PostgreSQL-first Minimum Runnable Loop

## Context

The repository already has independent real Hatchet Embedded and AgentRuntime POCs, but not a single business Run with persisted facts spanning Engine, two SDKs and terminal projection. HC-01/HC-02/HC-03 are DECIDED; their complete production gates remain OPEN. The user explicitly requires PostgreSQL deployed via Docker.

## Goals / Non-Goals

**Goals:**
- Reuse Hatchet Engine v0.110.5 and Python SDK 1.42.1 to perform a real two-stage DAG.
- Persist minimum platform-owned business facts in a PostgreSQL 16 database isolated from the Hatchet engine database.
- Reuse public Pydantic AI 2.54.0 and OpenAI Agents 0.23.1 through existing SPI with local deterministic Models (zero remote model calls).
- Produce visible Provider Binding, event sequences, per-Step results, one business terminal transition, and fail-closed negative tests.
- Provide repeatable local Docker Compose and CI execution instructions.
- **Mandatory local Run Inspector**: browser submits a real Run and reads PG-backed states, per-Step evidence, Workflow Binding and ordered timeline, including browser reload.

**Non-Goals:**
- Production-grade Portal/API, storage schema, HA, queues, CPU capacity, login/SSO, real streaming, approval, non-idempotent Tool execution, Cube/secret integration or PDLC migration. A localhost-only debugging API/Inspector **is** required.
- A second workflow queue/engine, SDK internals monkey-patching, cross-DB 2PC or exact-once side-effect guarantees.

## Decisions

### 1. PostgreSQL in Docker, two independently owned databases
`compose.yaml` launches `postgres:16-alpine`. The default `hatchet_poc` DB is created by PG image initialization; `poc/closed_loop/init_dbs.sql` creates `harness_poc`. Each has an independent connection URL. Hatchet SDK owns/migrates only its DB; `poc/closed_loop/facts.py` owns the prototype Harness schema. A named Compose volume keeps facts across application restarts. No SQLite path is accepted.

### 2. A single business Run with a primary Hatchet Workflow
`poc/closed_loop/hatchet_pg_live.py` creates a UUID Run and two platform Steps (A→B). The initial Plan is Version 1. An atomic PG transaction writes Run+Steps+Outbox. When dispatch starts, the Outbox becomes DISPATCHING; the code submits the real workflow asynchronously, records its opaque Provider ID in Harness PG after ACK, and waits for the real Engine result. A lost ACK becomes BLOCKED_UNKNOWN; manual/engine-side idempotent discovery is a follow-up gate, never a blind resubmit.

### 3. Task execution records platform facts
Each real Hatchet task obtains its own Harness DB connection, checks Step dependencies, invokes existing SPI Adapter with a model-only ExecutionContext, persists the buffered Typed Events and result, then returns a small DAG handoff to Hatchet. This does **not** prove platform-grade worker lease/owner/Fencing and is not an implementation of the final separate Tool Dispatch Boundary. Provider internal Task completion does not directly determine the business Run terminal status; after Workflow completion, Harness checks all Step results and Binding before CAS terminal.

### 4. No Sandbox allocation in model-only POC
Only `model` capability is requested. Model-only is a legitimate HC-03 path with zero Sandbox. OpenCode/Cube integration and trusted Worker grant issuance will be built as separate increments after this smaller full flow passes. The existing runtime SPI rejects privileged FS/Shell/Git calls without a matching SandboxGrant.

### 5. Failure strategy and control over scope
- Duplicate Run ID -> PG primary-key rejection before workflow submission.
- Outbox re-dispatch after DISPATCHING/unknown -> fail closed.
- Parent result absent or inconsistent -> child SDK never executes.
- Completed PURE Step repeated with same input -> return committed result; with different input -> fail.
- Completion attempted without all successful required Steps -> reject.
- Terminal Run cannot reopen; persisted event sequence is monotonic per Run.
- No synthetic claim for non-idempotent Tool side effects or true streaming.
- Native Hatchet query/dedup on lost ACK, post-worker failure recovery, and Cube binding remain explicit later tests.

### 6. Run Inspector: local HTTP API + static UI, no second Control Plane
A small FastAPI adapter serves the Inspector on `127.0.0.1` only. `POST /api/runs` persists Run+Outbox in PG then asynchronously dispatches via a **single shared Hatchet Worker/Engine** (not a process per Session); `GET /api/runs`, `GET /api/runs/{id}`, `GET /api/runs/{id}/events?after=N` query PG Task Facts/Event directly. The page uses lightweight polling for real state updates and can reload after browser/server restart. Render model output as text; do not render raw HTML. Distinguish `runtime.run.completed` from the single authoritative `run.completed` business event. Failure before creation returns a visible HTTP error, while dispatch ACK uncertainty renders `BLOCKED_UNKNOWN` without duplicate submission. Do not call this real Token SSE.

The UI is a debug tool, not a replacement PDLC Portal: no multi-user identity, secrets, arbitrary Shell, external API access or published internet listener. Separate the UI's read/query mechanism from the Hatchet API and keep all platform business facts in `harness_poc`.

## Runtime topology

```text
CLI demo (Host or Docker)
  -> Harness PG (Run + Steps + Outbox, Domain Events)
  -> Hatchet Embedded Engine (own DB, own Worker dispatch/DAG)
  -> Pydantic AI SDK [public local deterministic Model]
  -> Harness PG Step A verified output
  -> OpenAI Agents SDK [public local deterministic Model]
  -> Harness PG Step B verified output
  -> Hatchet Provider result + Harness domain terminal CAS
```

## Risks / Trade-offs

- Docker Hub pulls may fail in the current network. The PostgreSQL container is already healthy; application Docker image can use an alternative image registry or run from Host venv against Docker PG. Such a fallback **does not** change the mandatory PG store.
- Local deterministic model output proves SDK execution and orchestration, not real LLM latency, tokens or LiteLLM network path.
- PG prototype table structures are deliberately minimal; Attempt audit/reconciliation/inbox need strengthening prior to integration/production.
- Hatchet Embedded may spawn subprocesses; isolation/run verification should happen in a dedicated CI/Linux environment. Pin SDK and Engine versions.
- If the Engine returns an indeterminate workflow submission acknowledgment, mark blocked rather than guessing a second execution.

## Validation Approach

- `openspec validate minimal-run-closed-loop --strict`.
- `docker compose up -d postgres`; verify both databases and local PG migrations.
- `docker compose --profile demo run --build --rm loop` when Docker image registry works, or host-installed exact Python SDKs with `HATCHET_POC_DATABASE_URL` and `HARNESS_POC_DATABASE_URL` against Docker PostgreSQL.
- Unit/contract negative tests for Outbox unknown, duplicate Run, missing parent, terminal immutability and zero-Sandbox privileges.
- CI Linux + service PostgreSQL runs the actual two-SDK Hatchet integration; **report actual PASS/FAIL; don't promote independent POC evidence into a single-Run PASS**.
- Run Inspector UI/API smoke: POST real Run → poll same ID until terminal → verify PG Step/Binding/Events → refresh or restart local API → query same data; negative cases for missing Run, unavailable Engine/DB and after-cursor event ordering.