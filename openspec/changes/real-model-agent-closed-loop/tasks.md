# Tasks — Real Model Agent Closed Loop

## Planning / infrastructure
- [x] Read merged ADR-031/032, G01–G20, existing first OpenSpec/Run Inspector and DEV-HC Backlog.
- [x] Verify existing LiteLLM endpoint supports actual model discovery and Responses API without printing credentials; selected qwen3.8-flash model discovery and both Responses/Chat probes succeeded.
- [x] Complete OpenSpec Proposal, two capability Specs, Design and Tasks; strict validate.

## Red / Green model adapter
- [x] First write failing tests for JSON schema, review formatter, missing/malformed upstream data and Live opt-in config; capture Red evidence.
- [x] Implement minimal provider-neutral configuration and public SDK Responses adapters; keep local deterministic CI behavior unchanged.
- [x] Verify valid A draft and B review output, PG persistence and final readable report; verify invalid output blocks B/terminal.
- [x] Add Inspector clear mode/model metadata and live result readability; do not expose secret.

## Live proof / closeout
- [x] Execute actual LiteLLM model through Pydantic AI and OpenAI Agents SDK in one Hatchet Workflow against Docker PostgreSQL; record safe Run IDs, response evidence and outcome.
- [x] Execute HTTP Inspector live submission and refresh; final business deliverable and source Step A/B clearly readable.
- [ ] Separately validate real upstream token stream/cursor/cancel. Mark NOT_TESTED or unsupported until proven; never infer token SSE from buffered events.
- [ ] Pass deterministic CI regressions, architecture guardrails and OpenSpec strict validation; record full retrospective.
- [ ] Push PR, require green CI before merge; record accepted scope and remaining HC-02/03 & PDLC gates.
**Evidence recorded 2026-10-11:** local CLI Live Run `loop-26465ee92c4d42bfa26252dbad9312f8` and HTTP Inspector Live Run `run-04d87078786d46688b7d9d1f4dc4db2b`, both real qwen3.8-flash Responses and 14 persisted PG Events; Inspector Docker restart / same Run replay PASS. True provider-token-to-platform SSE + Last-Event-ID / cancellation is **not tested**, and keeps its own unchecked Gate. Other HC-02/03 production gates remain OPEN.
