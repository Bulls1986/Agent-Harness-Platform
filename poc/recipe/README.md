# DEV-M6: bounded three-Agent Recipe / native waits and recovery

**One original Recipe only:** plan (Pydantic AI) -> WAITING_INPUT ->
WAITING_APPROVAL -> code (OpenAI Agents SDK) -> verify (Pydantic AI).
Hatchet owns DAG, Queue, Worker and durable waits; canonical Harness
PostgreSQL owns Run/Step/Attempt/Plan, Approval, Evidence and domain terminal.
No second scheduler or parallel Run state machine.

## Actual test evidence

- Real Hatchet embedded Engine + separate PG, three actual public SDK
  invocations with deterministic local models (not synthetic direct function
  calls), persisted structured ArtifactRefs, exact byte/sha256 checks and
  one non-idempotent external PG fixture effect with confirmed M4 Receipt.
- **Live model:** LiteLLM Responses via all three SDK invocations on
  glm-5.3-flash; completed native provider with all 3 domain Steps VERIFIED.
- Negative tests: approval rejection blocks Code and produces zero external
  effects; unverified parent/wrong Scope/cross-Run/duplicate approval and
  stale Attempt fail closed.
- Native Hatchet WAITING_INPUT/APPROVAL events, and real Worker A process
  SIGKILL -> independent B replay of *same Workflow and Run*, three
  verified Steps and one write. This test uses *same-host PG*, not cross-host.
- Real PG contract suite and independent PG fixture tests use disposable
  synthetic project identity. GitHub official CI is independently required.

## Trust and non-goals

`gates.py` is an **internal trusted-service** port and not a consumer HTTP
API. Caller must authenticate Principal and validate Policy. The trusted
Verifier must check real stored bytes/digest/provenance before committing
`verify_step` / `answer_input`; `SyntheticArtifactFixture` is a
**separate PostgreSQL test fixture**, not OSS and not a production Artifact
Store. Same immutable in-memory string is never accepted as proof of an
external Tool write. The actual side-effect test uses M4 ToolReceiptJournal
and an independent external PG ledger with one real DB COMMIT, not a real
enterprise Git/OSS write. HC-03 trusted Cube/Guest contract is owned by M5;
cross-host durability, Enterprise IAM/OSS and Production GO remain M9/external
Owner. Do not infer production readiness from this synthetic Recipe.

## Commands (disposable test infra only)

Use existing docker-compose PostgreSQL. For native three-Agent tests the
container image pins Hatchet 1.42.1, Pydantic AI 2.54.0 and OpenAI Agents
0.23.1. Mount your current project worktree into /app for local changes.

    python -B -m unittest poc.recipe.test_recipe_pg poc.recipe.test_synthetic_artifacts_pg -v
    python -B -m poc.recipe.hatchet_three_agent
    python -B -m poc.recipe.hatchet_three_agent --decision REJECTED
    python -B -m poc.recipe.verify_worker_resume

The last command requires Linux POSIX signals and is designed for CI or
a Linux Docker container, not direct Windows execution. The real model test
requires opt-in HARNESS_MODEL_MODE=live, HARNESS_MODEL_BASE_URL,
HARNESS_MODEL_NAME and the existing supported LiteLLM secret environment
variable. No credential is stored in source. See the original OpenSpec
and docs/retrospectives/DEV_M6_NATIVE_ACCEPTANCE_20261014.md.