# Proposal — Real Model Agent Closed Loop

## Why

The baseline Docker PostgreSQL + Hatchet + Pydantic AI → OpenAI Agents SDK + Run Inspector POC is a genuine orchestration test, but both Agent SDKs currently return fixed local model text. It proves scheduling, not actual requirement analysis and review. The next smallest vertical slice must produce usable user-visible business output through a real remote LLM.

## What Changes

- Preserve the existing deterministic-local POC and its clean CI as a regression path.
- Introduce opt-in `HARNESS_MODEL_MODE=live` through a configurable, replaceable Responses-compatible ModelProvider boundary. Use public SDK APIs for Pydantic AI and OpenAI Agents SDK; never send credentials via Workflow payloads, domain events or the Inspector.
- Agent A: analyze the submitted business feature request and produce validated JSON with feature, summary, capabilities, business rules and acceptance criteria.
- Agent B: receive Agent A's **committed** structured output, review completeness and risk, produce validated review JSON and an end-user readable requirements + review report.
- Persist true Step outputs and final Run result in the existing Harness PostgreSQL domain facts; explicitly label model mode, model ID, and whether live execution was actually verified. No JSON dump as the default business output.
- Add test-first contract cases: invalid/incomplete JSON, SDK failure, missing key, unsupported endpoint, invalid handoff, no secret leakage, and re-open read consistency.
- Separate actual streamed provider-token events from buffered typed events; real Token SSE + cursor/cancellation gets a dedicated acceptance gate. No declaration of LIVE SSE without measurements.

## Capabilities

### New Capabilities
- `real-model-provider`: env-based Responses-compatible endpoint/model/credentials with real SDK invocation, fail closed and explicit mode tagging.
- `requirements-agent-chain`: structured requirement analysis → independent SDK review, schema/lineage checks and a readable final report.

### Modified Capabilities
- `run-inspector`: clearly differentiate deterministic SDK demonstration from live model business output and show final user-oriented report.

## Constraints

- Preserve G01–G20 and ADR-031/032 / HC-01/02/03. Hatchet remains the only technical schedule/state authority; Harness owns Domain Run/Step/Receipt/Verification and terminal state; SDKs execute only model calls in this slice (0 Cube).
- Docker PostgreSQL remains the mandatory persistence backend; Hatchet DB and Harness DB remain separate.
- Runtime model Key is environment injected; no hard-coded gateway host, key, sensitive prompt or model metadata in Agent payload/OSS/CI artifacts.
- Full Cube/Receipt/Approval/100 concurrency/PDLC migration are out of scope and remain OPEN.

## Definition of Done

OpenSpec strict validation, deterministic regression and actual external LiteLLM Responses invocation by both SDKs, A → B persisted handoff with schema validation, user-visible final result in Inspector after refresh, negative failure tests, CI and a retrospective. Any unexecuted Live/SSE gate must stay unchecked with reason and cannot be called production-ready.