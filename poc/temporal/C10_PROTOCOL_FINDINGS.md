# POC-C C10 — 受限 Responses-compatible / Harness Typed Event + SSE 桥接

> 2026-10-08 | **本地实际 Temporal 崩溃链 + Harness PostgreSQL + HTTP 进程重启 PASS（受限只读范围）**
>
> 并非完整 Responses API：无模型 Token SSE、无 POST 创建、
> 无 Tool/Artifact/Approval 全类型 Event，也没有 IAM/取消/在线 tail。
> **整体 G3 仍 PARTIAL，不准标完整 PASS。**

## 1. 架构边界

`protocol_bridge.py` 的唯一领域事实来源是**Harness PostgreSQL**：
`poc_runs`、`poc_turns`、`poc_c_temporal_bindings`、
`poc_attempts`、`poc_executions`、`poc_reconciliations` 与
append-only `poc_events`。Bridge 本身不导入 Temporal Client，
不读取 Temporal History，也不把原生 Workflow 事件编造为 UI
消息。

实现的最小接口：

| HTTP 接口 | 语义 |
|---|---|
| `GET /health` | HTTP 进程就绪，**不声称数据库健康** |
| `GET /v1/responses/{run_id}` | 从同一 PostgreSQL REPEATABLE READ 快照获得 Run 状态、Attempt/Execution/Reconciliation、当前事件游标 |
| `GET /v1/runs/{run_id}/events` | 基于持久 `poc_events` 的有限 SSE Replay，支持 `?after=N` 与标准 `Last-Event-ID: {run_id}:N` |
| `POST /v1/responses` | 明确返回 `501`：不支持受限 POC 的新 Agent 请求，避免伪装完整 Responses API |

协议事件外壳按 `docs/references/CONVERSATION_PROTOCOL.md`
保留 `event_id`、`sequence`、`conversation_id`、`turn_id`、
`run_id`、`item_id`、`schema_version=1`、`timestamp`、
`type`、`data`。只支持确实落盘的 `run.started` 与
`execution.unknown`，不合成进度和 `response.completed`。

原始 `run.started` 记录的内部 `native_workflow_id`
在协议映射层按 **明确字段白名单删除**，不包含 Temporal
History/原生 payload。无权限校验的隔离开发 API **只能绑定
127.0.0.1**，不可直接发布到企业网关。

## 2. C06/C07 故障之后真实验证

复用 C06/C07 的完整真链：

1. 两套独立 PostgreSQL：Temporal OSS 1.31.0 自身 History +
   Harness 自有 Task Facts；
2. PURE Activity 基础设施重试到第 2 次；
3. NON_RETRYABLE Activity 已收到 HTTP Tool Sink 的 200，
   Worker A 实际 `os._exit(74)`；Temporal 第 2 次重试由
   Worker B 接管，但未获准再次外部派发；
4. Harness 将原 Attempt/Execution 标为 `UNKNOWN`，
   Reconciliation `PENDING`，Run 仍 `RUNNING`；
5. 启动真实 loopback Uvicorn 独立子进程，HTTP GET 只查
   Harness PostgreSQL，状态 `in_progress`，
   `attention_required=true`，`event_cursor=2`；
6. SSE 读出 `run.started`、`execution.unknown` 两个真实
   持久 Event，未泄露 Native Workflow ID；
7. 停掉 HTTP 进程，全新进程再次启动，使用
   `Last-Event-ID: {run_id}:1` **只续播序号 2**，
   重新 GET 的 Response JSON 与重启前完全一致。

**结果：`PASS_C10_RESTRICTED_HTTP_AFTER_REAL_TEMPORAL_CRASH`**。
桥接并没有根据 Temporal Native Workflow Complete 将平台
Run 冒充 `COMPLETED`。此外还使用真 PostgreSQL 完成了负例
（非法/跨 Run cursor、伪造终态、未找到 Run、重复映射等）；
这不是模型生成的消息流。

## 3. 自动化验证与局限

- `poc/temporal/tests/test_protocol_bridge_pg.py`：4 项独立
  HTTP ASGI + PostgreSQL 语义测试。
- `poc/temporal/tests/test_platform_binding_pg.py`：
  既有 4 项冻结身份/执行状态测试。
- `poc/temporal/verify_protocol_process.py`：
  **真实两个 Uvicorn 进程**验证持久化快照/游标可跨进程重读。
- `poc/temporal/verify_c06_c07.py`：把 C10 嵌入
  真 Temporal Worker 崩溃和工具派发后的最终端到端断言。
- CI 第三个 OSS + **双 PostgreSQL** 作业安装
  `requirements-protocol.txt`，全部运行；无真实 LiteLLM Key。
- 目前并非无损映射全部 Temporal 活动；平台只呈现确实
  保存的两类事实。后续 Tool、Plan、Approval、Artifact、
  Verification 等 Event 需在各业务事务中可靠写入后映射。
  SSE 只做历史 Replay，不是 live streaming；
  生产认证/鉴权、Cancel/Tool Streaming、模型 Output item
  仍是 G3 缺口。切勿为了通过门禁而伪造事件。

**C10 按本次只读协议桥接验收局部 PASS；
完整 Harness UI Protocol G3 继续 PARTIAL。下一项 C12
独立验证 Temporal Workflow Replay/版本升级。**
