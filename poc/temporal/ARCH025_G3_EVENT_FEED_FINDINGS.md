# ARCH-TODO-025 / G3 — 统一平台 Typed Event Feed 增量验证

> 2026-10-09 | **实现已提交待 CI 验证的局部增量**；完整 G3 仍 **PARTIAL / NO-GO**。
>
> 不新增 C17，也不将不同 POC Run 的事件拼装/伪装成同一个真实业务 Run。

## 实现范围

- `platform_typed_feed.py` 对 Harness PostgreSQL 的 `poc_runs/poc_events` 做 **只读 MVCC 投影**，平台 `RunID`、`ConversationID`、`TurnID` 与 `seq` 为主键/游标；原生 Temporal History、Workflow ID 与 Provider 私有数据不进入客户端。
- `/v1/runs/{run_id}/events` 可读取已有 Temporal POC Run 所持久化的 C15 Token、C11 `artifact.created/verification.passed`、C06/C16 `execution.unknown/execution.reconciled` 的统一 SSE 事件形态；`/v1/responses/{run_id}/events` 仍仅允许 C15 Responses Run，`POST stream:true` 保留原语义。
- 每个事件按显式 `event_type → portable fields` allowlist 投影；未知类型、非对象 Payload、缺失/乱序 seq 拒绝投影；拒绝输出 `native_workflow_id` 和非允许的 provider/secret 字段。重连继续采用 `run_id:seq` 的排他游标。
- 只做 **Protocol Translator / SSE Projection**，不合并不同 Run、虚构 Tool/Approval、写入第二套 Event Store、不引入自建恢复调度器。

## 验证证据与限制

- 开发环境 Python 源码编译通过；本地 `unittest` 本增量 **5 项发现、2 项无需数据库的投影安全正/负例 PASS、3 项实际 Harness PG 测试因当前进程缺 DSN 而 SKIPPED**。待 GitHub Linux CI 使用独立实际 Harness PG 执行 `test_*.py`，再报告这些集成项结果。
- PostgreSQL 集成测试范围：C11 已落 PG 的 Artifact Metadata → SSE（对象引用使用**受控 PG-only fixture**，不能冒充真实 S3 访问）；C15 Run 同时通过 Responses/Run 两种接口读取同一 Event 序列；真实 PG UNKNOWN 仍展示为 `RUNNING / PENDING` 不宣称成功。
- C11 独立的真 SeaweedFS S3 实测和 C16 独立的真受控 HTTP Tool Receipt 均已有历史证据，**但仍属于不同的 Run**；本次并未验证 Token、Tool、Approval、Artifact 同一真实 Run 的业务正确性。

## 新发现的 G3/Cancellation P0 缺口

`live_g3_api.py` 现有 `POST /v1/responses/{id}/cancel` 调用 `LiveFacts.cancel()` 时先把平台 Run/Attempt/Execution 直接置于 `CANCELLED`，随后才向 Temporal 提交取消，且吞掉下游异常。这是 C15 原 POC 的限定行为，**不满足** [取消传播契约](../../docs/references/CANCELLATION_TIMEOUT_PROPAGATION.md) 的 `CANCELLING → provider TERMINATED/reconcile → CANCELLED|UNKNOWN|FAILED` 完整要求。应在 ARCH-TODO-025 的后续同一真实 Run 故障矩阵先闭合，不得以本次 SSE 投影通过声称 G3/生产硬门禁通过。