# Design — Live Model + Verified Business Result

## Baseline
Use the existing `poc/closed_loop/` PostgreSQL/Hatchet/AgentRuntime SPI/Inspector, preserving `deterministic_local_model` as the default CI mode. Do not extend the Control Plane with a second orchestrator, tenant/quota system, or an SDK-specific state machine.

## Architecture / Owners

- **Harness Facts (PG)**: Run/Step/Outbox/Provider Binding, committed Step A/B outputs, validation outcome, final Run Result, ordered business Events.
- **Hatchet**: sole technical Workflow DAG, two task dispatches/technical retries/history.
- **Real Model Provider**: env-selected Responses endpoint/model/key; public `pydantic_ai.models.openai.OpenAIResponsesModel` + `OpenAIProvider`; public OpenAI Agents SDK `OpenAIResponsesModel` + OpenAI `AsyncOpenAI`. Only AgentRuntime SPI knows these SDKs, Domain remains provider-neutral.
- **Inspector**: read-only business fact presentation and request submission; no model key exposure and no fake live status.

## Configuration contract

`HARNESS_MODEL_MODE=local|live` (local default), `HARNESS_MODEL_BASE_URL`, `HARNESS_MODEL_NAME`, `HARNESS_MODEL_API_KEY` (or existing `JUSDA_LITELLM_API_KEY` as host-local fallback). Never commit exact credential or send one to event payload. A missing key/URL/model in live mode raises a diagnostic failure.

## Two-stage business contract

1. A system prompt instructs Agent A to return JSON only: `feature`, `summary`, nonempty lists `capabilities`, `business_rules`, `acceptance_criteria`. Validate a Pydantic `RequirementsDraft` model; store normalized JSON as the Step A Output.
2. Hatchet releases B only when A Task and persisted Step A verified output completed. B receives that exact JSON; system prompt requires a review JSON `decision`, `issues`, `risks`, `recommendations`, `summary`. Parse into `ReviewOutcome`. Render combined readable plain-text report from verified structures, store as Step B Output. This report becomes the final business result after Domain `complete()`.
3. Report real model metadata in RunResult `mode=live`, `model_id`; model/provider refs are frozen per Run, with no key in payload or persisted events. Use existing business terminal CAS. If stage fails parsing or transport, do not finish Step/Run or call B.
4. HTML renders the text report directly; existing Inspector already uses `textContent`. Reflect real-model mode in user-facing explanation based on backend mode, not a hardcoded claim.

## Test-first gates
- Red: pure parser/render contract, missing API key, malicious markup, invalid fields; checks fail before implementation.
- Green: deterministic non-live tests + PG regression still pass without external dependencies.
- Live: demonstrate LiteLLM `/v1/responses` behavior with selected model; execute actual Hatchet → Pydantic SDK → OpenAI Agents SDK with PostgreSQL, verify both Step responses and final product report after refresh.
- Stream: separate true provider delta/Run cursor/cancel tests; keep NOT_TESTED unless proven in same end-to-end chain.

## Risks
- LiteLLM/model may not support native JSON schema output; use ordinary text generation but parse and validate strict JSON at the Harness Verification boundary, no silent repairs. The model can be prompted for JSON but may still fail.
- POC currently stores short text outputs in PG for inspectability; full large Artifact/Evidence must use OSS by G10 and PII must not be sent without authorization.
- A model producing syntactically valid JSON does not prove correctness/fitness; do not claim real business acceptance without additional verification policies and sample validation.
- Cross-worker recovery, Receipt UNKNOWN and Cube gating remain OPEN for later increments.