# DEV-M8 · External consumer integration tasks

> 状态：CLOSED（原 M8 合成消费合同，归档 PR 最新 Head 全门禁通过与合并后生效）；真实 HTTP→PG→Native Hatchet 官方 M8 CI 38502350952 / 38502537080 SUCCESS。生产 IdP、真实外部 Tool/OSS、真实业务迁移及 Production GO 不在此范围。证据：docs/retrospectives/DEV_M8_FINAL_CLOSEOUT_20261014.md

- [x] Confirm archived M7 versioned `/api/v1` contract: Conversation → Turn → idempotent Run, trusted identity, scoped reads, SSE resume, `CANCEL_REQUESTED` intent and fail-closed errors; M6 prerequisite CLOSED. **证据**：docs/retrospectives/DEV_M8_CONSUMER_TDD_20261014.md
- [x] Red→Green: `tests/test_m8_synthetic_consumer.mjs` 7/7 Node tests for public path, identity, scope failure, Run binding, idempotency/ACK unknown, cursor, SSE Last-Event-ID and cancel intent. **证据**：docs/retrospectives/DEV_M8_CONSUMER_TDD_20261014.md
- [x] Implement `integrations/synthetic_consumer.mjs` independent Node HTTP consumer (no Harness internal import), plus real HTTP smoke `integrations/verify_m8_http.mjs`; all identifiers are synthetic. **证据**：docs/retrospectives/DEV_M8_CONSUMER_TDD_20261014.md
- [x] Real HTTP Node consumer → synthetic trusted FastAPI boundary → actual PG / Native Hatchet two SDK Run, same-key replay, cross-Scope 404, cursor resume and cancellation intent; native provider termination/enterprise IdP explicitly unverified. **证据**：docs/retrospectives/DEV_M8_FINAL_CLOSEOUT_20261014.md
- [x] Review M8 real Native CI, M7 API regression and architecture guard; privacy/production exclusions, retrospective and OpenSpec canonical archive; merge conditioned on latest PR Head CI. **证据**：docs/retrospectives/DEV_M8_FINAL_CLOSEOUT_20261014.md
