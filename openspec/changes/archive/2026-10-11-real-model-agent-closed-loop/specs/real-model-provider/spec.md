# Real Model Provider

## ADDED Requirements

### Requirement: Opt-in real Responses model using public SDK adapters
The Harness POC SHALL select `deterministic_local_model` by default and MAY opt in to `live` with an explicit endpoint/model and API key from the execution environment. Both Pydantic AI and OpenAI Agents SDK SHALL use their public Responses-compatible model adapters; no private SDK overrides or fake models may be counted as live.

#### Scenario: Live is enabled with valid parameters
- **WHEN** `HARNESS_MODEL_MODE=live` is configured with a reachable Responses API, model ID and key
- **THEN** each SDK SHALL make a real external model request and report `mode=live` with model ID, preserving the platform Run ID and Hatchet Workflow ID independently

#### Scenario: Default local CI
- **WHEN** live is not requested
- **THEN** the existing deterministic model path SHALL continue passing without a remote service or credentials

### Requirement: Configuration and secrets fail closed
The ModelProvider MUST reject missing base URL/model/API key, unsupported API mode and request failures without constructing a fake success. Secrets MUST NOT be placed in persisted Step outputs, typed domain events, logs, CLI summaries or the frontend.

#### Scenario: Missing real model credential
- **WHEN** live is selected without a key
- **THEN** model execution MUST reject before sending a request and Run MUST NOT be marked COMPLETED

#### Scenario: Upstream model failure
- **WHEN** model provider returns HTTP failure or times out
- **THEN** only a failure observation SHALL be recorded; downstream SDK MUST NOT run and no business final result SHALL be fabricated

### Requirement: Streaming proof is independent of buffered text
The system MUST NOT advertise buffered SDK text chunks or database event polling as authentic upstream provider token streaming. True token SSE, resumable cursor and cancel are separately observable acceptance gates.

#### Scenario: Only non-streaming model response was tested
- **WHEN** a live model request succeeds but streaming was not measured
- **THEN** true Token SSE status SHALL remain NOT_TESTED