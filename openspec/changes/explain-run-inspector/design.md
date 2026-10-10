# Design: Result-First Inspector

## Context

The previous real Hatchet+PostgreSQL+two SDK model-only POC and Inspector passed CI. Its UI showed a JSON-heavy event list and only step outputs; it did not persist a Run-level result or original prompt. The change must preserve ADR-031/032 and HC-01/02/03, not expand framework responsibilities.

## Data boundary

Add nullable `input_prompt TEXT` and `result_json JSONB` to **Harness-owned** `harness_run` with `ADD COLUMN IF NOT EXISTS` for existing Docker volumes. POST writes input_prompt in the existing atomic Run/Step/Outbox transaction; CLI also passes its prompt. On Domain `complete` (after both Steps + Provider Binding verified), atomically store `result_json={final_output:StepB.output,result_source_step:'openai',step_outputs:{...},mode:'deterministic_local_model'}` plus terminal state and event. The final output is a technical SDK result, not a product analysis report.

`snapshot` exposes nullable `input_prompt`, `result` and per-step input/output. Step B input comes from persisted Step A output **only after B's attempt started**. Historical Runs with no original input display `null` and a clear warning. For completed old Runs with no result_json, optionally derive the final output from persisted B.output with `provenance='derived_legacy_step'`; never claim it was previously stored.

## UI

Use a zero-framework static HTML page. The first screen communicates "what is being verified" and deterministic local model limitations. Provide a submit form/historical list, then a large final Run result panel, explicit sequential Step A/B panels (purpose, input/output, state/attempt), and event descriptions. Raw JSON/Provider IDs are in a closed-by-default `details` element. HTML/user content uses `textContent` rather than `innerHTML` to avoid XSS. Refresh re-queries PG.

## Quality gates

1. Test-first Docker PG and Inspector API assertions fail on missing prompt/result, then pass.
2. Distinguish Model SDK completed events from one business run.completed event; keep terminal immutable.
3. Run full real Hatchet+both SDKs+PG black-box Inspector CLI verifying final result and A→B input; restart and verify original Run.
4. Run OpenSpec strict validation, architecture guard/legacy regression and clean CI. Keep full Cube/Receipt/SSE/Approval/100 concurrency NOT_TESTED.
5. Retrospective: user-visible acceptance is a first-class contract, not optional decoration. Known restrictions: POC plain-text prompt and deterministic local models.