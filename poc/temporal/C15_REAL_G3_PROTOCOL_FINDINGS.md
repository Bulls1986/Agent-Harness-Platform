# POC-C / C15 — 真实模型 Responses/Typed Token SSE 与 Native Start RecoveryPoint

> 2026-10-08 | **核心 G3 真实模型→自托管 API→持久 Typed Token SSE scoped PASS**。
> 不是整个 Responses API/全种类 Tool、Approval、Artifact/UI G3 Gate PASS。
> Native Start ACK 故障、RecoveryPoint 引用、Cancel 为额外 G2/G6 scoped 证据。

## 完整的真实模型链（非 Mock）

- `POST /v1/responses` 创建 Harness PostgreSQL 的
  Conversation/Turn/Run/Plan/Step/Attempt/Execution 和冻结原生
  Temporal Workflow ID（**先平台事务落盘，后 Native 启动**）。
- 官方 OSS Temporal 1.31.0 + 独立 PG；Worker 以独立进程运行
  `poc-c15-g3-streaming` Native Workflow，模型 `AsyncOpenAI`
  **真实流式**调用企业 LiteLLM/OpenAI-compatible Gateway。
  仅在 Worker Activity 内处理 Provider Stream，Native Workflow
  不执行模型/PG/API I/O。
- 每个真实 `delta.content` 单独落成 Harness PostgreSQL
  `response.output_text.delta` 事件；`done` 记录摘要/字符数，
  独立 Verify Activity 重新从 PG 重建文本核对 SHA-256，
  成功后才写 `verification.passed` / `run.terminal`。
  **模型实际输出文本存在 Harness 的受控 UI 事件存储中，
  不存在 Temporal Native History 里。**
- `GET /v1/responses/{run_id}` 从 PG 组装真实模型回答；
  `GET /v1/responses/{run_id}/events`、
  `GET /v1/runs/{run_id}/events` 支持真实长连接 SSE、
  `Last-Event-ID`、`after`、重连游标排他校验；
  `POST /v1/responses` 的 `stream:true` 也提供直接 SSE。
- `POST /v1/responses/{id}/cancel` 先落平台 CANCELLED
  终态再尽力发官方 Temporal Cancel，防止旧 Worker 覆盖终态；
  `run.terminal`、Attempt/Execution 均受 PG 终态触发器保护。

**最终本机第二轮真实 Provider 验收**：
`PASS_C15_G3_REAL_MODEL_TO_HTTP_TYPED_TOKEN_SSE`，
**9** 条真实 Token Delta / **63** 字符输出；SSE Delta 拼接与
GET 文本一致，实际 HTTP 服务进程重启后断点续播正确，
伪造另一 Run 的 Cursor HTTP 422，查询真实 Temporal History
确认完整模型回答未泄漏。之前第一轮为 **10** Delta / **53** 字符。
CI 运行相同实际 OSS Temporal/双 PG/HTTP/Worker，但模型替身
显式 `POC_C15_FAKE_MODEL=1`，**CI PASS 不能冒充真实 Provider PASS**。

## G2/G6：Native Start ACK 不确定

- 在 `Client.start_workflow` **已返回（Temporal Server 接受）**、
  但平台 ACK 落库前注入 `POC_C15_INJECT_START_ACK_LOSS=1`。
  HTTP 503 返回**已持久 Run ID 和 START_ACK_UNKNOWN**，
  不能偷偷创造第二个 Workflow。
- 恢复入口 `POST /v1/responses/{id}/reconcile-start` 只通过
  官方 `get_workflow_handle(frozen_id).describe()` 反查；
  Native ID/版本/Attempt 不改变，查询成功才将
  `start_state` 升级 `ACKED`，不重复发 Start。
  Native 未能确认时 HTTP 409，**拒绝盲重试**。
- 在 Harness PostgreSQL `poc_recovery_points` 持久写入
  `RecoveryPointID→Run/Step/Attempt→temporal-workflow-id://<opaque>`，
  SQL Trigger 拒绝更新、删除与重复 RecoveryPoint。
  此引用只是 Temporal Native Durable History 的 Opaque Pointer，
  **不是 Harness 内自建 History 或 Runtime Checkpoint 内容**。
- 实际 Native ACK 注入、独立 HTTP 进程重启、Cancel 幂等和终态
  不可覆盖通过。另有 **4 项真实 PostgreSQL 正反合约测试**，
  验证 Frozen Binding、RecoveryPoint、ACK 迁移、Token Digest、
  Cancel/终态不可重开。

## 还没有覆盖的 G3/G2/G6 部分

- G3 目前单个真实模型 Run 的 Typed Event：
  `run.started`、`plan.created`、`activity.started`、
  `response.output_text.delta/done`、`verification.passed`、
  `run.terminal`，另有 `CANCELLED`、故障 `FAILED` 终态；
  **真实 Tool/Approval/Artifact 跨系统合并到同一 UI 事件接口
  尚未做**。本 POC 是 Responses-compatible **受限子集**，
  并非全部官方 Responses API 语义（尤其 `stream:true` 协议格式、
  原生 tool items、Reasoning Summary、Error details）。
- 仅接受最多 500 字输入、一个固定配置模型；真实 Token
  成功不证明 Multimodal 或跨模型切换。
- 当前模型 Stream 被中断后选择安全 FAILED，**不会假定可以无损
  恢复中途 Token**；整个 G6 还需完整 Replay/Worker Crash、
  真正多步 task 恢复策略。
- ACK 注入的是**已知 Server 接受但 ACK 丢失**窗口；
  在网络完全不可用、Native 实际未启动、Timeout 不确定等
  更广窗口保持 START_UNKNOWN/人工可核验，不提供盲重试。
- API 只绑定 localhost，无生产 IAM/SSO、TLS、Quota、速率限制；
  本轮不建设额外 Gateway/调度器/APM。
