# Proposal: Make Run Inspector self-explanatory

## Why

The working UI shows state and a long JSON event log without answering the user’s primary questions: what is this page for, what exactly do Step A/B do, what input/output did they process, and what did the parent Run finally return? This prevents meaningful POC acceptance despite a green real Hatchet/PG integration gate.

## What Changes

- Explain the limited model-only POC intent and exact technical capabilities at the top of the Inspector. Prominently disclose that the two SDKs execute real calls but deterministic local models produce fixed test strings; no actual understanding of the user's business input or live LLM.
- Present a readable execution story: initial prompt → Step A (Pydantic AI, purpose/input/output) → Step B (OpenAI Agents SDK, same verified persisted A output as input) → final Run result.
- Persist demonstration input and final Run result in the Harness-owned PostgreSQL Run fact in the same transactions as the existing creation/terminal state changes; expose them on existing GET /api/runs/{id}. Maintain backward-compatible read behavior for pre-migration records without inventing an old prompt.
- Show human-readable event descriptions, keep raw JSON/Provider IDs available only in collapsed details. Render all model output as textContent, never injected HTML.
- Extend PG/API contract tests and live Inspector black-box E2E/refresh assertions; perform retrospective and CI before merging.

## Capabilities

### Modified Capabilities

- `run-inspector`: user-friendly narrative, node input/output and final result with honest deterministic model disclosure.
- `durable-run-facts`: optional input_prompt and result_json, persisted, backward-compatible migration.

## Impact and non-goals

POC-only changes to `poc/closed_loop/` and this OpenSpec delta. No new scheduler, no Hatchet domain dependency, no Cube, real LLM, Token SSE, approval or production scope. Local-only input is deliberately stored in plain text for an inspectable demo: no sensitive inputs or secrets; production must replace this with governed storage/refs.