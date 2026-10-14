# DEV-M6 native Recipe acceptance evidence · 2026-10-14

## Scope freeze

One original synthetic plan -> code -> verify workflow with Pydantic AI /
OpenAI Agents SDK / Pydantic AI. No new Recipe, UI, SDK, scheduler, enterprise
consumer, infrastructure subsystem or platform Production GO.

## TDD + actual native runtime evidence

Harness PG canonical tables retain Run/Step/Attempt/Event authority;
Hatchet Embedded Engine and Worker hold technical queue/retry/wait facts.
Three metadata tables freeze Recipe/Approval/Input and refs. M4
ToolReceiptJournal owns non-idempotent write Intent/UNKNOWN/Receipt.

1. Native local-model pass, Hatchet/PG with three real public SDK invocations
   and independent external synthetic PostgreSQL byte-store and effect ledger:
   Run m6native-d708f0f81492438fa00249e05131c735,
   Provider edaf11f5-da5f-43bf-a8c4-05ee7b0a08fa,
   three VERIFIED Steps / exactly one external PG ledger effect.
2. Native rejection:
   Run m6native-f5d4c3f719fd4552acf12437efa7383f,
   Provider 57dbc40a-5266-4691-8e42-780bbc3c9ebb,
   Harness BLOCKED / zero side effects; expected Hatchet native step failure.
3. True upstream LiteLLM Responses API, model glm-5.3-flash through all
   three actual SDK calls:
   Run m6native-14e9f8921f3f4cb8b1bb6a0fac9f139b,
   Provider 1e39460e-cccf-4da1-a64e-24aaf586e863,
   three VERIFIED Steps / final COMPLETED / one external effect.
   This run preceded a prompt-provenance refinement that now passes
   real-Engine deterministic verification; final-head live recheck needed
   for a claim of final source HEAD live model PASS.
4. New native WAITING_INPUT step and approval wait are Hatchet durable tasks.
   Real Worker's physical kill/replay initial Red:
   Worker B received the same native task but Harness rejected duplicate
   input request (not a Provider or SDK failure). Fixed only same-principal,
   same-request-digest replay idempotence; conflicting/late requests still
   fail closed. PG regression suite 12/12 PASS after fix.
5. Actual positive physical Worker test after fix:
   Run m6recover-4c491fc1cb4546d680935d8d5345d759,
   Provider 83d0e0af-0e27-4e6c-bfa7-c2a1ec93dbe9,
   Worker A PID 21 physically SIGKILL -9, separate Worker B PID 68,
   same Run / same Provider, input and approval resume,
   Plan/Code/Verify each exactly one Attempt, external effect count 1,
   three VERIFIED, domain COMPLETED.
6. Real PG fixture byte tests 2/2 PASS and PG safety tests 12/12 PASS;
   architecture baseline + original OpenSpec and repository unit regression
   on latest origin/main passed before this follow-up change.
   Official CI/PR review MUST be confirmed for final archive.

## Remaining trust separation

Synthetic external artifact fixture stores and fetches actual bytes and
checks sha256 in a separate PostgreSQL DB; its OSS-like object reference is
not a real OSS bucket. Real corporate OSS, IAM and external Policy
integration are outside this generic Recipe deliverable. M5 has separate
actual Cube/Guest and trusted HC-03 execution proofs; M6 synthetic
non-idempotent test executes actual independent PG COMMIT/Receipt, **not**
a Cube Guest Shell/enterprise write. Neither part alone is Production GO.
Cross-host and production operation belong to original M9 gate.

## Regression / conclusions

Original M6 tests protect same-project immutable Recipe, verified parent
handoff, authentic persistent Event/Attempt facts, durable Input and Approval,
deny-before-write, exactly one confirmed side effect and physical native
Worker kill-recovery without duplicate provider/step execution.

CI official pipeline and archive status determine milestone CLOSED; local
pass alone is not enough. Do not change M7 or Inspector to claim more.