# POC-C / C16 — 真实非幂等外部 Tool Receipt 与 UNKNOWN 对账

> 2026-10-08 | **真实非幂等 HTTP 业务副作用 + 重启后 Receipt 反查 scoped PASS**，
> 不是企业 MCP 带签名回执、Exactly Once 或整个 Run 恢复终态 PASS。

## 测试隔离与执行边界

- 真实 OSS Temporal Server + Temporal PostgreSQL；独立 Harness
  PostgreSQL，平台已有 C06/C07 Frozen
  Run/Plan/Step/Attempt/Execution、PG Execution Fencing 和
  UNKNOWN/PENDING 事实，未复制 Native Scheduler/History。
- 独立 `c16_receipt_sink.py` 业务 HTTP 进程，**每次 POST 真正
  将业务 effect_delta=1 提交到独立 SQLite WAL 持久文件**；
  不提供幂等去重捷径，因此一旦盲重试就会造成 double apply。
  `GET /receipt/{execution_id}` 由实际持久账本返回 ReceiptID、
  AttemptID 与业务计数。服务与 Harness/Temporal 数据库互相独立。
- Worker A：PG Admission/Fence PASS→真实 HTTP POST
  提交副作用→Server 200→Worker **`os._exit(74)`**，
  故意不确认 Temporal Activity 完成。
- Worker B：官方 Temporal Retry 自动发生，
  但平台拒绝重新执行 NON_RETRYABLE side effect，将旧
  Attempt/Execution 原子定为 **UNKNOWN**，
  revoke 旧 Owner、Fencing +1、Reconciliation=PENDING。
- **先重启外部真实业务服务**，再由可信
  `ReceiptReconciler` 通过 HTTPS 之外的本地 POC
  `GET /receipt/{execution_id}` 做只读查询（绝不 POST）；
  限定 exact ExecutionID/AttemptID、必须**恰好一条业务 effect**。
  事务插入不可变 `poc_c16_reconciled_receipts`（包含
  ReceiptID、外部引用与 SHA256）并更新
  `poc_reconciliations.state=RESOLVED`，追加
  `execution.reconciled` Typed Event。
- PG 已冻结的原 Attempt/Execution **仍为 UNKNOWN**：
  Receipt 补证不能修改历史；Run 暂时仍 RUNNING，
  后续必须由独立业务 Verify/Decision 决定终态，
  **绝不把 Native Workflow Completed 当业务成功**。

实测 `PASS_C16_REAL_NONIDEMPOTENT_TOOL_DURABLE_RECEIPT_RECONCILIATION`：
外部效果持久提交次数 **1**；Worker A 退出码 **74**；
Worker B 未重复派发；真实 Tool 服务重启后 Receipt 完整；
Reconciliation 从 PENDING→RESOLVED；重复 Reconciler 幂等；
冻结的历史 UNKNOWN 不变；平台事件
`run.started → execution.unknown → execution.reconciled` 共 3 条。

## 禁止误判 PASS

- HTTP 业务服务与 SQLite Ledger 是**真实产生副作用的受控
  POC Tool**，但不是已有企业 MCP/ERP 的真实业务 API；
  不验证商业服务身份鉴别、签名回执或管理工具治理。
- 若 Receipt 缺失、查询失败、血缘不一致、effect_count
  **大于 1**，Reconciler 必须拒绝自动升级成功；
  外部状态仍不明需要 HUMAN_REQUIRED / 人工对账流程，
  不是默认补发危险动作。
- G6 任务恢复仅对 UNKNOWN→可信 Receipt 的对账证据
  scoped PASS；**未完成自动终态决策、新 Plan/Attempt 恢复**，
  无法据此将全 G6 标为 PASS。
- 不假设平台和外部业务数据库之间可以实现 Exactly Once
  分布式事务，也不归属外部 OSS/SQLite/Temporal 的备份容灾。
