# M1 Streaming closeout — provider deltas, persisted SSE and cancellation

## ADDED Requirements

### Requirement: real provider-origin chunks, not buffered completion
- Live Pydantic AI and OpenAI Agents SDK SHALL use public streaming APIs. Only genuine upstream generated text deltas may be marked source=provider_stream.
- Each accepted delta SHALL persist immediately in Harness PG event log with ordered run-scoped sequence and step identity before the step completes.
- Local deterministic adapter output remains buffered and must not count as streaming evidence.
- Streamed draft/review bytes are provisional until the corresponding Step is verified.

#### Scenario: Active real model produces deltas
- **WHEN** a Live model streams two text fragments before Step completion
- **THEN** both fragments are independently durable PG events with source=provider_stream before the final Step output exists

### Requirement: resumable SSE
- GET /api/runs/{run_id}/stream SHALL return text/event-stream, id = run_id:sequence, typed event and PG-backed JSON.
- Last-Event-ID or after cursor SHALL replay strictly greater sequences, reject malformed/negative/cross-Run cursors with 422, and never expose another Run.
- Stream SHALL stop after draining true terminal or recorded execution error; no fabricated terminal success.

#### Scenario: Reconnect with a cursor
- **WHEN** a valid Run-scoped Last-Event-ID is passed to SSE after a connection drops
- **THEN** only strictly later events are replayed in PG sequence, and a foreign Run cursor is rejected

### Requirement: durable cancellation
- POST /api/runs/{id}/cancel SHALL write an idempotent durable command and run.cancel.requested event, without immediately inventing CANCELLED.
- Active Agent execution SHALL observe persistent cancel state, cancel/await the underlying SDK stream and acknowledge before Harness writes CANCELLED/run.cancelled.
- No new model text may persist after cancellation request, terminal cannot be reopened, repeated cancel cannot duplicate events.

#### Scenario: Cancel during streaming
- **WHEN** a user cancels a RUNNING model-only task after its first provisional token
- **THEN** Harness durably records CANCEL_REQUESTED, rejects new tokens, awaits worker cancellation and only then records CANCELLED without run.completed

### Requirement: real acceptance
- The same real Hatchet + PG + two SDK + LiteLLM run SHALL demonstrate streaming deltas from both SDKs before business completion, replay after Last-Event-ID and recovery after Inspector restart.
- Live cancellation SHALL be tested against an active Run and no Run COMPLETED may occur after request; no fake token streaming from buffered events.
- Changes remain model-only PURE. Production IAM/PII/backpressure governance, Cube, Tool Receipts remain OPEN.

#### Scenario: End-to-end provider evidence
- **WHEN** a real Hatchet two-SDK LiteLLM Run completes through Inspector
- **THEN** each of the two public SDKs has PG provider_stream events before Step completion and the final Run output is verified; restarting Inspector preserves cursor replay