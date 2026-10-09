# ARCH-TODO-025 / P0 取消状态与原生终止确认

> 2026-10-09 | **C15 PURE 模型流取消 scoped PASS（本地真实 Harness PG + OSS Temporal）**；生产 G3/G6 **PARTIAL / NO-GO**。

## 缺陷

C15 `POST /v1/responses/{run_id}/cancel` 原先先把 Harness Run/Attempt/Execution 直接写为 `CANCELLED`，然后 best-effort 调用 Temporal `cancel()` 并忽略远端异常。违背已接受的 [Cancellation/Timeout Contract](../../docs/references/CANCELLATION_TIMEOUT_PROPAGATION.md)：取消 ACK 不是 Native 停止证明，未确认副作用不得以取消洗白。

## 最小修复（不扩展 Harness 职责）

1. `LiveFacts.request_cancel()` 在 Harness PostgreSQL Run 行锁内将 `RUNNING → CANCELLING`，追加不可变 `cancellation.requested` Typed Event；不提前终结 Attempt/Execution，不重写 History，拒绝非 `PURE` 路径。
2. Worker `append/verify/terminal` 在 `CANCELLING` 阻止新 Token、Verifier 和胜出的迟到 `COMPLETED`；既有成功的 Attempt/Execution 不覆盖。
3. `POST /cancel` 使用官方 Temporal `WorkflowHandle.cancel()` 请求取消；收到 ACK 只记录 `cancellation.acknowledged`，HTTP **202 / CANCELLING**。网络失败、请求 ACK 不确定仍保留 CANCELLING，不能因为异常直接标 CANCELLED。
4. `POST /reconcile-cancel` 用冻结的 Native Workflow ID 调用 **官方 `WorkflowHandle.describe()`**；运行中返回 202，无法查证/绑定不一致返回 409。只有已知原生 terminal（CANCELED/TERMINATED/COMPLETED/FAILED/TIMED_OUT）才由平台 `finish_cancel()` 原子转入正确 `CANCELLED` 或 `FAILED`，写 `cancellation.confirmed` 和 `run.terminal`，禁止 reopen/重复请求重复事实。
5. `/v1/runs/{id}/events` 和 `/v1/responses/{id}/events` 透过原 PG 只读 Typed SSE 投影追加以上取消事件，继续适用 Last-Event-ID 和 Provider 私有字段 allowlist；无新增控制/调度器。
6. **仅 `PURE` 的 C15 模型流路径符合此直接终结条件。** 对实际 Tool/MCP 副作用，必须先让 Adapter/Receipt/Reconciliation 证明终止与效果；无可信证据则 fail closed/human，不得照搬这个方法。

## 已复核本地证据

- Python 源码编译通过（官方 `temporalio==1.34.0` 公共 API）。
- 独立临时 PostgreSQL 16 + 随机测试凭据：`test_c15_live_protocol_pg.py` **7/7 PASS**。包括 ACK 幂等、无法查询 Native、Native 仍 RUNNING、冻结 ID 不符、已验证历史 SUCCEEDED 不覆盖、native TIMED_OUT 映射 FAILED、Run 终态不回退。
- 实际 OSS Temporal Server/Worker + 独立临时 Harness PG：`verify_c15_g3_http.py` **正常取消 ACK 与模拟取消信号丢失两条完整 HTTP E2E PASS**。两条都先观察 CANCELLING，成功调用 Native describe 终止确认后才落盘 CANCELLED，取消事件单次出现，原成功 Run 的 Token SSE/HTTP 重连不受影响。CI 用明确 Fake Model Token；不是本轮新增 Live Model 证据。
- 早期测试脚本曾复用 `state` 覆盖原始 Run 快照，引起 `HTTP restart response differs` 假失败；修复测试局部变量后，上述 E2E 重新执行均 PASS。

## 仍然开放

- C15 之外非 PURE Tool 的实际止损/收据核对与 UNKNOWN+人工介入。
- Native 无法查证时本轮**保持 CANCELLING + 明示 UNKNOWN**，不自动声称 CANCELLED；需要后续任务级等待/对账/兜底决策策略。
- 同一真实 Run 的 Token/Tool/Approval/Artifact/UNKNOWN 事件全链及生产 API 协议仍未通过，G3/G6 保持 PARTIAL。