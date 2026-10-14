# DEV-M6 · Recipe / Approval · 2026-10-14 safety slice

## Decision and scope
**ACTIVE / OPEN; not M6 CLOSED, not Production GO.** The original DEV-M6
OpenSpec requires exactly one synthetic cross-SDK Recipe:
plan (Pydantic) → code (OpenAI, approved write) → verify (Pydantic).
Frozen Recipe version, ArtifactRef/Evidence, verifier, WAITING_APPROVAL/INPUT,
and task-level recovery remain the required scope; no new scheduler, Recipe,
SDK, IAM, business consumer or unrelated infrastructure.

This slice validates only **actual Harness PostgreSQL contracts**, with
synthetic Provider bindings, Artifact locators, verifier evidence strings,
and an M4 ToolReceiptJournal test-ledger lookup. It is NOT actual Hatchet
three-node execution, native Agent SDK calls, real model, OCI/Cube Tool,
OSS bytes/sha256 verification, trusted authorization/verification, or
physical worker recovery. Missing gate must not be marked PASS.

## Ownership and decisions
- Canonical Harness tables harness_run, harness_step, harness_step_attempt,
  harness_outbox and harness_event remain the ONLY Domain owner.
- harness_recipe_frozen, harness_recipe_step_meta and
  harness_recipe_step_approval contain version, refs and approval metadata;
  no parallel Run/Step state machine or second Scheduler.
- M4 ToolReceiptJournal owns non-idempotent intent/UNKNOWN/reconciliation;
  a Step WRITE can only be verified when its exact Run/Step/Attempt has
  a CONFIRMED_SUCCESS external receipt. Final Run remains blocked on
  unresolved receipts; already-confirmed receipts are not rejected.
- Trusted service must independently inspect OSS bytes/digest and approval
  principal before calling internal gates. The code does not perform these
  external checks, and is NOT an unauthenticated public API.
- Tool execution still requires HC-03 fencing and capabilities. A PG
  approval admission result is not a Tool execution permit.

## Red → Green → review
Local test base: Windows Python 3.12, psycopg 3.2.12, actual PostgreSQL 16
on loopback 55447, fetched main SHA 5af78a9.
Red-1: ModuleNotFoundError for missing M6 safety module.
Green-1: initial PG five tests PASS.
Architecture review caught shadow Run/Step authority in first draft; discarded.
Green-2: metadata-only overlay on PgFacts, seven actual PG tests PASS.
Red-3: write Step verified without external Receipt; final Run was blocked
even with confirmed Receipt; approved Attempt Tool Bridge gate was absent.
Green-3: write requires matching CONFIRMED_SUCCESS, unreconciled/UNKNOWN
fail closed, approved Attempt gate, actual PG nine tests PASS.

Actual commands (disposable local POC database):
    $env:HARNESS_POC_DATABASE_URL = 'postgresql://harness_poc:local_poc_only@127.0.0.1:55447/harness_poc'
    python -B -m unittest poc.recipe.test_recipe_pg -v
    python -B -m unittest discover -s tests -v
    python -B scripts/check_architecture_guardrails.py
    openspec validate dev-m6-agent-recipe-execution --strict
    openspec validate --specs --strict

Results: 9/9 M6 PG PASS; latest-main repository tests 23/23 PASS;
architecture static PASS; M6 OpenSpec Strict PASS; canonical specs 5/5 PASS.
The fake Provider reference is NOT native Hatchet execution evidence;
test-synthetic External Ledger proof is NOT real Tool side-effect evidence.
CI, PR/merge and live M6 native gates NOT VERIFIED at time of this record.

## Retrospective / remaining original admission
Root cause: M6 had only planning artifacts; prior two-Agent Inspector
live proof was not the original three-Agent M6 workflow. A naive new
state machine would violate HC-01/02; a naive receipt existence check
would either allow UNKNOWN writes or reject legitimate confirmed writes.
Regression guards now protect ownership, concurrency, approval denial,
frozen version/scope, waiting/restart persistence and UNKNOWN non-retry.

The outstanding **original** M6 gates remain: trusted real Hatchet
A→B→C with actual cross-SDK calls; persisted real ArtifactRef and
independent content/digest/source verifier; trusted Tool Bridge/Cube
write and external Receipt; WAITING_INPUT/timeout/resume and physical
restart/failure injection; official CI/PR review evidence and OpenSpec
archive. No additional requirements are added. M6 remains ACTIVE/OPEN.