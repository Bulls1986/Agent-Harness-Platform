# POC-A: Microsoft Agent Framework implementation

> Status: **A00–A04 have offline/infrastructure evidence; A06/A07 and A11 public SDK probes added; A05 real provider, A07 Compaction, A11 full lifecycle and Durable recovery NOT RUN.**  
> This is a framework evaluation harness, **not** a production Harness Control Plane.

## Current slices

| ID | Implemented | Evidence needed before PASS |
|---|---|---|
| A00 | Original MAF streaming smoke + offline CI | Offline public imports and unit tests already passed |
| A01 | Pinned direct packages + public API/optional capability probe | CI must install exact versions and run `api_probe.py`; transitive `pip freeze` captured per run |
| A02 | Versioned Coding/Document broken/reference fixtures + independent verifier | CI must prove known-good passes and broken cases fail |
| A03 | PostgreSQL/OTLP Compose + optional external S3-compatible store + isolated model runtime image | CI verifies Compose validation, MAF image build, Postgres SELECT 1 and collector startup; no hosted API/OSS adapter |
| A04 | Evidence template with Gate and scenario IDs | Every later case must record real exit status, version, and evidence refs |
| A05 | Live two-turn memory/streaming probe | Requires real provider credential and successful model response; no CI secrets assumed |
| A31 | Durable feasibility memo | Python MAF + Functions/MSSQL in private cluster and cross-worker recovery NOT tested |

Verified in [GitHub Actions run #37715048965](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37715048965): pinned public SDK imports, actual HarnessAgent+native Session construction (no network model call), dependency freeze artifact, positive and negative acceptance fixtures, runtime image build, and Postgres/OTLP startup checks. These checks must not be counted as G1/G2/G3/G6 PASS.

## 0.1 A06/A07 native provider and A11 Workflow probes

The following commands **run actual MAF Python SDK code** without a model
endpoint, Foundry, file-memory persistence, shell or web tools:

```bash
python poc/maf/harness_capabilities.py
python poc/maf/workflow_probe.py
python poc/maf/document_workflow.py
python -m unittest discover -s poc/maf/tests -p "test_*.py" -v
```

- A06: checks native `TodoProvider`, `AgentModeProvider`, session serialization,
  and a custom `ContextProvider` wired through documented APIs.
- A07: exercises custom `before_run/after_run` hook contract with fixture context.
  **This is not evidence of real conversation history, compaction, or durable
  cross-process session restore.** Compaction is explicitly disabled in these
  probes pending separate token-budget validation.
- A11: executes MAF `WorkflowBuilder` + custom public `Executor/handler` chain
  with platform-owned Run/Plan/Step/Attempt identity, and a deterministic
  terminal decision requiring verified outcome **and** evidence reference.
  Failure, missing evidence and invalid plan version are negative cases.
  **No actual Planner/Executor tool invocation, PostgreSQL state transaction,
  Retry/Replan, or crash recovery** is claimed.
- A12 (bounded Document case): uses an actual MAF Workflow Executor to call the
  **independent fixture verifier**; correct summary finishes, deliberately wrong
  summary fails. This is a trusted fixture test, not Agent-produced code,
  production sandbox execution, or permanent OSS-backed Evidence. The
  `poc-fixture://` URI is deliberately a local test marker, not a storage reference.
- A05 now creates a restricted HarnessAgent using the same public factory:
  host File Memory/Web Search/Tool Auto Approval are disabled for the live
  probe until real sandbox, authorization and persistence are integrated.

The above public API extensions use documented behavior; they cannot be
interpreted as completion of the S03/S06/S07/G2/G6 end-to-end gates.

## 0.2 A23 PostgreSQL task facts (integration slice)

**Validated in [GitHub Actions #37717839849](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37717839849):** native MAF Workflow, 4 PostgreSQL integration tests, rejected terminal/Attempt mutations and stale Plan results, and separate-process readback for both completed and failed Runs. The generic no-DB unit-test job skips the four DB-only tests; the dedicated database step runs and passes all four. No Recovery/OSS gate is implied.



The platform-owned ledger uses the same identity supplied to native MAF
Document Workflow, never a generated MAF session ID as the platform Run ID.

```bash
# Install pinned SDK + psycopg in a virtualenv, then start POC Postgres:
python -m pip install -r poc/maf/requirements.txt
docker compose --env-file poc/maf/.env -f poc/maf/compose.yml up -d postgres
export POC_POSTGRES_DSN="postgresql://poc:<local-password>@127.0.0.1:54329/poc_harness"

python poc/maf/persisted_document.py --case expected
python poc/maf/persisted_document.py --case buggy
python poc/maf/persisted_document.py --inspect "<run-id-from-first-command>"
python -m unittest discover -s poc/maf/tests -p "test_task_ledger_pg.py" -v
```

The schema is in `sql/001_task_facts.sql`. It stores Conversation/Turn/Run,
versioned Plan, Step, Attempt, Execution, Verification, typed Event, and
opaque RuntimeBinding/RecoveryPoint *references*. It does not store large
Artifact or Evidence payloads, real MAF checkpoint internals, or a new
scheduler. A trusted document verifier runs inside the native MAF Workflow;
completion and verification facts are committed in **one** PostgreSQL
transaction afterward. The process can exit, and a new Python process can
read all of the persisted task facts.

Database-enforced negative cases include terminal Run mutation, finalized
Attempt rewriting, Plan history mutation, stale Plan finalization, and
mismatched identity. A failure during native Workflow execution can leave
the Run in RUNNING before the terminal fact transaction; interpreting and
safely recovering such a Run belongs to A27–A30, **not** this slice.

**Critical limitations:**

- `poc-fixture://` evidence refs represent committed trusted test fixtures,
  not OSS-backed Evidence. A15 must replace them with durable object refs.
- Session/History/Compaction is **not** persisted by this ledger (A07/A24).
  MAF's documented `AgentSession.to_dict/from_dict` path is a separate,
  opaque session-state serialization capability.
- Runtime Checkpoint/DurableTask/Worker failure resume is **not** implemented.
  A23's task facts do not by themselves satisfy G2/G6.
- This POC schema is a small validated slice, not the full production schema
  or migration/permission architecture.

## 0.3 A24/A27/A28 bounded recovery evidence

CI evidence: [GitHub Actions #37718726040](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37718726040)
executed all three PostgreSQL tests plus a distinct-process test where worker
A exits with status 91 and worker B rehydrates native Session state and
finishes the PURE Step. Both readbacks passed. This is bounded task-level
recovery evidence, not the full G6 gate.

A new PostgreSQL migration, `sql/002_runtime_recovery.sql`, adds two
deliberately small POC records: opaque native MAF Session payload in a
separate runtime-state table, and a PENDING Reconciliation fact for UNKNOWN
non-PURE executions. This is not another task scheduler or checkpoint backend.

Native MAF `AgentSession.to_dict()/from_dict()` is used only through public
APIs, with explicit Run binding, provider configuration fingerprint, and
optimistic revision to reject stale writers. The CI process roundtrip uses a
controlled state marker, **not** a real-model chat-history/compaction test.
The runtime session payload is stored in a dedicated PostgreSQL POC table
for a bounded proof, not as Harness Run metadata; the production Session
backend and Payload policy still need to be chosen and tested.

The fault-injection CLI intentionally terminates a Python process with code
91 *after* the initial Run/Step/Attempt/Execution facts have committed.
Another Python process then resumes a demonstrably PURE read-only Document
Verification Step. It records the old Attempt as FAILED/EXECUTOR_CRASH and
starts a new Attempt within the same Run and Step. A tardy old result
cannot finalize that Run. No Same Attempt checkpoint resume is claimed.

When side-effect semantics are NON_RETRYABLE and an execution may already
have been dispatched, a missing worker is classified UNKNOWN and an explicit
PENDING Reconciliation record is written; **no new Attempt is created**.
The test never sends a real external write.

Run these against the POC PostgreSQL database:

```bash
python -m unittest discover -s poc/maf/tests -p "test_session_recovery_pg.py" -v
# Requires POC_POSTGRES_DSN. CI additionally tests separate OS processes:
#   recovery_process_probe.py --create-crashed-run
#   recovery_process_probe.py --save-session RUN_ID
#   recovery_process_probe.py --load-session RUN_ID
#   recovery_process_probe.py --resume-pure RUN_ID --expected-attempt ATTEMPT_ID
```

Limitations: no lease expiry/watchdog, automatic scheduling, native Workflow
Checkpoint or durable same-Attempt resume, real history/compaction, Workspace
restore, Sandbox snapshot, OSS Evidence or G2/G6 pass. Recovery commands are
explicit and anchored to a particular interrupted Attempt identity; they do
not silently infer that any RUNNING execution is abandoned. Retrying a
non-PURE execution without reconciliation remains prohibited.

## 0.4 Stage conclusions, native checkpoint and approval wait (A25/A26)

The evidence-backed [POC-A Stage Findings](../../docs/POC_A_STAGE_FINDINGS.md)
now separates each verified slice from undecided architecture and the G1–G8 gates.

### A25: native workflow Checkpoint, not a custom engine

```bash
mkdir -p /tmp/maf-checkpoint-poc && chmod 700 /tmp/maf-checkpoint-poc
python poc/maf/checkpoint_probe.py --save /tmp/maf-checkpoint-poc
python poc/maf/checkpoint_probe.py --restore /tmp/maf-checkpoint-poc
```

MAF `FileCheckpointStorage` remains completely owned by the framework. The
second command runs in a fresh Python process, rebuilds the same Workflow
with stable Executor IDs, and rehydrates the native checkpoint before the
terminal superstep. The test rejects re-executing the already completed
`PrepareExecutor`. The `probe-manifest.json` contains only the
`checkpoint_id` and workflow identifier, and is outside the native
checkpoint files. This development-only file store **is not an enterprise
Durable Task backend**. Python file checkpoint serialization has a
restricted-pickle security boundary; never load untrusted checkpoint files.

### A26: durable platform WAITING_APPROVAL, not native MAF HITL

The platform Approval store records requester, approver, action/resource/
policy references, Step and Attempt, all in PostgreSQL. A Run starts
`WAITING_APPROVAL` with a `CREATED` Attempt and **no Execution**: a gated
tool is not dispatched while the decision is pending. A second process
reads the same Run's pending request. The decision transaction checks the
named approver and *a trusted external authorization decision*, then
updates the Run; rejection makes it terminal with no Execution.

```bash
# Requires POC_POSTGRES_DSN and a running PostgreSQL:
python -m unittest discover -s poc/maf/tests -p "test_approval_wait_pg.py" -v
# The separate-process CLI is strictly a trusted CI fixture, NOT a public
# endpoint: it assumes the fixture's approver and Policy authorization.
```

Neither the CLI nor the PostgreSQL test implements enterprise IAM; never
copy its fixed `authorized=True` into an HTTP approval handler.
Native MAF `request_info`/pending-response checkpoint mapping and an
actual sensitive Tool approval remain A26/G7 follow-up. This stage does not
claim G2/G6/G7 PASS.

## 0.5 Native MAF HITL / platform Approval bridge (A26 follow-up)

[Final PR #9 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720102476): approved/rejected cross-process native HITL, two PostgreSQL binding integrity tests and three lineage-selected checkpoint restore repetitions all passed.

The `native_hitl_probe.py` fixture uses **real MAF public**
`WorkflowContext.request_info`, `@response_handler`, and
`FileCheckpointStorage`, not a synthesized RequestInfo event.
The request ID and opaque native checkpoint reference are stored as an
immutable binding inside the same PostgreSQL transaction as the platform's
WAITING_APPROVAL fact (`sql/004_native_hitl_binding.sql`).

GitHub Actions runs the requester and decision responder in different Python
processes: only the workflow that restores the exact native request ID from
the checkpoint may accept the already-validated platform decision.
`REJECTED` produces a deny-only output, with **zero dispatch of the
simulated sensitive Executor**; `APPROVED` can enter the simulated
Executor. The test requires no network model, Cloud backend or credentials.

The CLI is **only a trusted test fixture**: it injects a fixed approver and
`authorized=True` instead of an external IAM/Policy decision. It is never
safe to expose it as an approval endpoint. Approval decision persistence and
runtime resume are separate operations; a crash between them still requires
explicit reconciliation of the already-recorded decision before continuing.
The POC does not promise externally visible effects exactly once.

FileCheckpointStorage is a single-machine development path and is **not**
a production private Durable backend. Same Attempt end-to-end production
resumption, native Agent tool approval, external Policy/IAM, multi-worker
ownership and production storage remain open G2/G6/G7/G8 tasks.

## 0.6 Approval decision crash window & Execution ownership (A26/A29)

This POC covers **two distinct crash windows**, without implementing a
Durable Task Scheduler or an IAM backend:

- **Committed Approval, no native response delivery intent yet:** a new
  Python process recovers the same MAF pending request from the opaque
  Checkpoint and reuses the immutable PostgreSQL Approval decision.
- **Response delivery intent exists but result not durably acknowledged:**
  treat native response application as `UNKNOWN`, prevent another automatic
  native response, and require explicit reconciliation. Even a crash just
  after recording intent cannot be assumed pre-dispatch. This does **not**
  establish exactly-once side effects.

`poc_maf_hitl_deliveries` stores a small delivery token and state:
`IN_FLIGHT / APPLIED / UNKNOWN`. It does **not** interpret or save MAF
Checkpoint internals. CI fault injection ends processes with exit codes
92 (safe gap) and 93 (uncertain gap); retry of an already APPLIED response
does not re-enter the simulated sensitive Executor.

For platform-owned `Execution` only, `ExecutionOwnership` uses the
existing PostgreSQL authority for atomic Claim, Heartbeat, single
Dispatch admission, Lease expiry and epoch-based fencing token. Claimed
Execution result commits require its valid owner and token. Expired
owners cannot commit or issue new dispatch requests; recovery refuses
an active owner, revokes an expired owner, then routes PURE to
Same Step + New Attempt or non-PURE to UNKNOWN/Reconciliation.
No framework / DurableTask / Sandbox internal worker ownership is replaced.

```bash
# With POC_POSTGRES_DSN and the POC PostgreSQL container:
python -m unittest discover -s poc/maf/tests -p "test_approval_delivery_pg.py" -v
python -m unittest discover -s poc/maf/tests -p "test_execution_ownership_pg.py" -v
```

**Scope limits:** real tool effects and SideEffectReceipts, distributed
scheduler takeovers, cancellation/timeout propagation, production IAM,
long-lived distributed Durable Checkpoint storage and G2/G6/G7 gates
are **not** proven by these controlled fixtures.

## 0.7 A29 cancellation/timeout task facts and A30 recovery matrix

[A29 PostgreSQL CI #37721115581](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37721115581)
passed all six new cancellation/timeout cases. The bounded POC implements
deterministic task-fact transitions in `execution_control.py`:

- A WAITING_APPROVAL Run with no dispatched Execution can be CANCELLED
  directly, preserving the Approval request as a cancelled historical fact.
- A RUNNING Run first enters `CANCELLING`; new Execution admissions are
  rejected. Adapter `ACKNOWLEDGED` / `UNSUPPORTED` means **not terminated**.
  Only trusted `TERMINATED` with proven safe effects may finish CANCELLED.
- Non-PURE already dispatched cannot become CANCELLED solely because a
  cancellation request was acknowledged or the provider stopped running.
  It enters `UNKNOWN` and PENDING Reconciliation.
- Timeout is a **failure_type**, never a terminal state. Proven pre-dispatch
  timeout => FAILED/TIMEOUT; post-dispatch non-PURE unknown result =>
  UNKNOWN/TIMEOUT_AFTER_DISPATCH; running PURE without termination proof =>
  still RUNNING, requiring an explicit provider termination decision.

```bash
# Requires POC_POSTGRES_DSN and the running POC PostgreSQL service.
python -m unittest discover -s poc/maf/tests -p "test_execution_control_pg.py" -v
```

**These are trusted Control Plane fact transitions, not real provider
cancellation.** No actual MAF Cancel/Abort, shell/tool/process termination,
Sandbox kill or external SideEffectReceipt was exercised. The test is not
a production cancellation Adapter, distributed Scheduler or durable backend.

See [A30 Recovery Coverage Matrix](../../docs/POC_A_RECOVERY_MATRIX.md) for
the tested recovery levels, failure injection results, unverified capability
matrix and G1–G8 limitations.

## 1. Install and inspect (A01)

Use Python 3.11+ in a clean venv:

```bash
python -m pip install -r poc/maf/requirements.txt
python poc/maf/api_probe.py
python -m unittest discover -s poc/maf/tests -p "test_*.py" -v
```

Direct MAF dependencies are fixed at `agent-framework-core==1.20.0`
and `agent-framework-openai==1.15.0`. This is **not a transitive lockfile**:
record the exact resolved dependencies with `python -m pip freeze`.
Optional symbol presence is introspection, **not proof** that a capability
works or that a Durable backend is available.

## 2. Reproducible acceptance fixtures (A02)

Both cases are deliberately defined **outside the agent prompt** and will be
reused by MAF, Temporal and ADK so evaluation difficulty is identical.

```bash
# Expected PASS (exit 0):
python poc/maf/verify_fixture.py --case coding --candidate poc/maf/fixtures/coding/solution
python poc/maf/verify_fixture.py --case document --candidate poc/maf/fixtures/document/expected

# Expected FAIL (exit 1, VERIFICATION_FAILURE):
python poc/maf/verify_fixture.py --case coding --candidate poc/maf/fixtures/coding/buggy
python poc/maf/verify_fixture.py --case document --candidate poc/maf/fixtures/document/buggy
```

`fixtures/scenarios.json` declares IDs, tasks, accepted outputs and future
failure-injection plans. The UNKNOWN external-write scenario is **declared
but not implemented**; it belongs to A28, not A02.

**Security:** The coding verifier executes candidate Python. Never execute
model-modified/untrusted candidate code on the Harness Control Plane host.
For POC-A2 and beyond, run it only inside CubeSandbox (Docker fallback smoke);
the offline unit tests use only committed trusted fixture code.

## 3. Local infrastructure and container smoke (A03/A05)

Copy the example config, replace local-only credentials (do not commit `.env`):

```bash
cp poc/maf/.env.example poc/maf/.env
docker compose --env-file poc/maf/.env -f poc/maf/compose.yml config -q
docker compose --env-file poc/maf/.env -f poc/maf/compose.yml up -d postgres otel-collector
docker compose --env-file poc/maf/.env -f poc/maf/compose.yml ps
```

Ports bind to **127.0.0.1 only**:
Postgres `54329`, OTLP gRPC `14317`, OTLP HTTP `14318`. Optional object-store ports `9002/9003` require a separately approved image. This is only an *infrastructure
harness*, not a hosted HTTP Agent API (A18). Current Compose configuration
does not claim Postgres SessionStore, durable MAF history or ArtifactStore
are integrated — those are A15/A23/A24. OTLP receiver is not a production APM
backend; do not turn on prompt/response telemetry by default.

Set the following **only for an explicit real-provider probe**, not in
committed files or logs. Provider is OpenAI-compatible with a Responses API:

```bash
export OPENAI_API_KEY="<local-secret>"
export MAF_POC_MODEL="<model-or-deployment>"
# Optional supported gateway only:
# export OPENAI_BASE_URL="https://<enterprise-model-gateway>/v1"
python poc/maf/session_probe.py
# OR containerized, without relying on Foundry Hosted Agents:
docker compose --env-file poc/maf/.env -f poc/maf/compose.yml --profile live-model run --build --rm maf-runtime-smoke
```

PowerShell uses `$env:OPENAI_API_KEY` and `$env:MAF_POC_MODEL`; environment
variables are inherited by Docker Compose when launching from the same shell.
Be aware `docker compose config` can print resolved environment variables,
including secrets: use `config -q` rather than copying full output.
Use a temporary provider-scoped credential, and never upload raw responses.

The live probe reports only `streamed_both_turns`, `recalled_marker`,
`turn_count`, and `passed`; it does not print marker content or raw responses.
**Even a PASS does not satisfy G1, G2, G3 or G6**: durable state, protocol,
and task-level recovery each require their own gates.

## 4. Evidence & Durable feasibility

Copy `evidence-template.json` to a private evidence directory under
`poc/maf/evidence/` and record task ID, commit, exact SDK versions, command
without credentials, run UUID if available, observed exit code, UTC timestamp,
and trustworthy trace/artifact URI. Use `NOT_RUN`, `PASS`, `FAIL`,
`GAP` or `BLOCKED` accurately; this template does not assert any PASS.

A31 technical risks and untested private Durable backend proof requirements
are recorded in [DURABLE_FEASIBILITY.md](DURABLE_FEASIBILITY.md).

## Next slice

- A06/A07: probe MAF Todo/Mode/Context/History/Compaction using public APIs.
- A11/A12/A13: deterministic Workflow + independent verification/replanning.
- A18/A19/A20: real self-hosted API, Responses/Event Translator.
- A23–A30: Postgres task facts and task-level recovery before claiming G2/G6.
- A32/A33: real Python MAF Durable + Functions/MSSQL worker test.

References: `docs/POC.md`, `docs/POC_A_TASK_PLAN.md` and Accepted Contracts.

## Upstream MinIO image caveat (2026-10-08)

The upstream public Docker Hub and Quay MinIO images could not be pulled in GitHub Actions, and the fixed-release binary URL returned HTTP 410. The optional `local-oss` Compose profile therefore requires an explicitly configured `POC_OBJECT_STORAGE_IMAGE` from an enterprise-approved registry. This should not block the Harness POC: ArtifactStore/S3 integration is tested at A15 against an enterprise S3-compatible endpoint, not by building a storage product. Local object-store ports 9002/9003 are exposed only if the optional profile is started. No image mirror or official upstream availability is assumed.

Optional object store command after setting `POC_OBJECT_STORAGE_IMAGE` to an approved image reference:

```bash
docker compose --env-file poc/maf/.env -f poc/maf/compose.yml --profile local-oss up -d object-store
```
