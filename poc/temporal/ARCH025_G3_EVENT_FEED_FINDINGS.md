# ARCH-TODO-025 / G3 — 统一平台 Typed Event Feed 增量验证

> 2026-10-09 | **真实 PostgreSQL + Linux CI 局部 PASS**；完整 G3 仍 **PARTIAL / NO-GO**。
>
> 不新增 C17，也不将不同 POC Run 的事件拼装/伪装成同一个真实业务 Run。

## 实现范围

- `platform_typed_feed.py` 对 Harness PostgreSQL 的 `poc_runs/poc_events` 做 **只读 MVCC 投影**，平台 `RunID`、`ConversationID`、`TurnID` 与 `seq` 为主键/游标；原生 Temporal History、Workflow ID 与 Provider 私有数据不进入客户端。
- `/v1/runs/{run_id}/events` 可读取已有 Temporal POC Run 所持久化的 C15 Token、C11 `artifact.created/verification.passed`、C06/C16 `execution.unknown/execution.reconciled` 的统一 SSE 事件形态；`/v1/responses/{run_id}/events` 仍仅允许 C15 Responses Run，`POST stream:true` 保留原语义。
- 每个事件按显式 `event_type → portable fields` allowlist 投影；未知类型、非对象 Payload、缺失/乱序 seq 拒绝投影；拒绝输出 `native_workflow_id` 和非允许的 provider/secret 字段。重连继续采用 `run_id:seq` 的排他游标。
- 只做 **Protocol Translator / SSE Projection**，不合并不同 Run、虚构 Tool/Approval、写入第二套 Event Store、不引入自建恢复调度器。

## 验证证据与限制

- Python 源码编译与 Git diff check 通过。首次本地运行仅 2 个纯投影测试 PASS、3 个 PG 用例 SKIPPED（缺运行时依赖/DSN），**未被计为 PG 验收**。随后补装既定官方 `temporalio==1.34.0`，使用新建的独立 PostgreSQL 16 容器、临时随机凭据与 loopback 端口真实执行，新增测试 **5/5 PASS、0 SKIP**；测试结束后销毁临时容器。
- [GitHub Actions #37848460468](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37848460468) **5/5 Job SUCCESS**（包含真实 OSS Temporal、独立 Harness PostgreSQL、API/Worker）；在 `selfhost-harness-c06-c07-fault-chain` Job 日志中查证 5 项 `test_arch025_typed_feed_pg` 用例均为 `ok`，不是 skipped；该 Job 的完整 PG 合约测试累计 **25 项 PASS**。CI 模型阶段仍使用明确 Fake Tokens，不代表本轮再次访问真实模型。
- PostgreSQL 集成测试范围：C11 已落 PG 的 Artifact Metadata → SSE（对象引用使用**受控 PG-only fixture**，不能冒充真实 S3 访问）；C15 Run 同时通过 Responses/Run 两种接口读取同一 Event 序列；真实 PG UNKNOWN 仍展示为 `RUNNING / PENDING` 不宣称成功。
- C11 独立的真 SeaweedFS S3 实测和 C16 独立的真受控 HTTP Tool Receipt 均已有历史证据，**但仍属于不同的 Run**；本次并未验证 Token、Tool、Approval、Artifact 同一真实 Run 的业务正确性。

## 新发现的 G3/Cancellation P0 缺口

`live_g3_api.py` 现有 `POST /v1/responses/{id}/cancel` 调用 `LiveFacts.cancel()` 时先把平台 Run/Attempt/Execution 直接置于 `CANCELLED`，随后才向 Temporal 提交取消，且吞掉下游异常。这是 C15 原 POC 的限定行为，**不满足** [取消传播契约](../../docs/references/CANCELLATION_TIMEOUT_PROPAGATION.md) 的 `CANCELLING → provider TERMINATED/reconcile → CANCELLED|UNKNOWN|FAILED` 完整要求。应在 ARCH-TODO-025 的后续同一真实 Run 故障矩阵先闭合，不得以本次 SSE 投影通过声称 G3/生产硬门禁通过。