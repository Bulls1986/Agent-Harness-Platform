# DEV-M8 通用外部消费者 · TDD 与合同证据（2026-10-14）

## Scope / ownership
- 本轮严格对应现有 DEV-M8，依赖已正式归档的 DEV-M6/M7 公共合同。
- Harness 代码库仅含独立合成 Node Consumer 和合成 PG/Native CI Fixture；无真实业务消费者源码、内部仓库、企业数据库/Schema 或客户数据。
- M8 不反向限制 Harness 通用 Runtime；生产安全与真实企业身份验证仍属于后续独立门禁。

## 1. Public contract reviewed (implemented slice)
- Source of truth: archived M7 `poc/platform_access/platform_api.py`, `poc/platform_access/README.md` and M7 final closeout.
- HTTP: `POST /api/v1/conversations`, `POST /api/v1/conversations/{id}/turns`, `POST /api/v1/turns/{id}/runs` with `Idempotency-Key`, `GET /api/v1/runs/{id}`, `GET .../events?after=`, `GET .../stream` (Last-Event-ID), `POST .../cancel`.
- Identity/Policy is externally injected; unsigned client identity headers are not trusted. `CANCEL_REQUESTED` is not Provider termination; a 5xx/transport loss during POST is not a confirmed failure or success and must be reconciled without blind resubmit.

## 2. TDD Red → Green
- RED: `node --test tests/test_m8_synthetic_consumer.mjs` failed with `ERR_MODULE_NOT_FOUND` before implementing `integrations/synthetic_consumer.mjs`.
- GREEN: **7/7, 0 FAILED, 0 SKIPPED** using Node 24.21.0. Cases verify only versioned API/identity, Conversation→Turn→Run and idempotency key, scoped 401/403/404 rejection without error-body leak, Run mismatch, cancellation intent, event cursor, SSE `Last-Event-ID` and forged ID rejection, and transport/503 unknown-submission fail-closed without retries.
- `npx --yes @fission-ai/openspec@1.12.0 validate dev-m8-external-consumer-integration --strict`: PASS.
- `node --check integrations/synthetic_consumer.mjs`, `node --check integrations/verify_m8_http.mjs` and `python -m py_compile poc/platform_access/verify_m8_external_api.py`: PASS.
- Python driver serves actual platform `create_platform_app` with real PostgreSQL and Native Hatchet worker. An independent Node subprocess accesses it over loopback HTTP using **only the public versioned API**, using synthetic identities and synthetic test selections.

## 3. Not yet accepted (do NOT close M8)
- Real independent HTTP→PG/Native Hatchet and cross-identity/cancel negative gate requires a **successful official PR latest-Head CI** from `.github/workflows/dev-m8-generic-consumer.yml`; merely implementing the verifier is not PASS.
- Production external IdP, true enterprise Policy, native provider physical termination, real OSS/Tool providers and production performance are NOT VERIFIED and not silently inferred from synthetic fixtures.
- The cancel scenario intentionally holds a **synthetic** provider after actual PG dispatch/bind, so it verifies durable API/PG cancellation intent but NOT native provider termination. The ordinary successful Run is executed by genuine Hatchet and two SDKs.
- Final stage security/CI audit and OpenSpec archive remain `[ ]` until reviewed evidence is sufficient.

## 4. Lessons / guardrail
- The generic consumer must use HTTP only and never import platform internals.
- Treat POST response loss as UNKNOWN; do not replay a tool or Run without reconciling the durable `Idempotency-Key`.
- Validate Run and event cursor ownership on every read; cancellation request must not be displayed as a physically stopped provider.
