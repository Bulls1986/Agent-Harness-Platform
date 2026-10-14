# DEV-M8 · External consumer integration tasks

> Status: ACTIVE / PARTIAL. M7 public API and M6 prerequisites are CLOSED. Independent Node consumer and Red→Green contract tests exist (7/7 local PASS). Official real HTTP + PostgreSQL + Hatchet CI remains UNVERIFIED until latest PR Head passes. No private application data included.

- [x] Confirm archived M7 versioned `/api/v1` contract: Conversation → Turn → idempotent Run, trusted identity, scoped reads, SSE resume, `CANCEL_REQUESTED` intent and fail-closed errors; M6 prerequisite CLOSED. **证据**：docs/retrospectives/DEV_M8_CONSUMER_TDD_20261014.md
- [x] Red→Green: `tests/test_m8_synthetic_consumer.mjs` 7/7 Node tests for public path, identity, scope failure, Run binding, idempotency/ACK unknown, cursor, SSE Last-Event-ID and cancel intent. **证据**：docs/retrospectives/DEV_M8_CONSUMER_TDD_20261014.md
- [x] Implement `integrations/synthetic_consumer.mjs` independent Node HTTP consumer (no Harness internal import), plus real HTTP smoke `integrations/verify_m8_http.mjs`; all identifiers are synthetic. **证据**：docs/retrospectives/DEV_M8_CONSUMER_TDD_20261014.md
- [ ] Execute real HTTP Node consumer → synthetic trusted FastAPI gateway → actual Harness PG / Native Hatchet; require official CI latest Head PASS. Test fixture: `poc/platform_access/verify_m8_external_api.py`. Native provider termination and enterprise IdP are NOT asserted.
- [ ] Review CI evidence, security boundary, retrospective and archive this public contract stage.
