# G6 / 官方 Native Durable Worker SIGKILL 与 Tool Receipt 同链验收

> 2026-10-09，本机真实 MAF Azure Functions + MSSQL Durable + Harness PostgreSQL + 受控外部 HTTP/SQLite Tool；状态 **PASS_GUARDED_REPLAY_SINGLE_FAULT_CHAIN**。不证明企业 MCP、跨节点或 Exactly Once。

## 一次真实故障链

1. PG Run/Step/Attempt/Execution（NON_RETRYABLE、冻结 Native Binding/Version、Fencing），调用真实 `ToolReceiptReconciler.prepare` 记录唯一不可变 Tool Dispatch Intent。
2. 官方 MAF Durable Worker A 的 Executor 发 HTTP 请求；PG 原子 Fencing Admission 首次通过，工具在**独立 SQLite 外部数据库**实际非幂等写入并提交一条带独立 ReceiptId 的回执。MAF Worker 不掌握该回执。
3. Worker B 已上线后，A **SIGKILL**；MSSQL Durable 在 B 中重新执行原生 Handler。实际 Handler **2 次**、Gateway admitted→denied、外部效果 **1 次**，第二次 HTTP Tool 派发在 PG 入口被拒。
4. 与 A34 原始验证相同，可信故障注入 SQL 将 PG 原 Attempt/Execution 标记 UNKNOWN、Reconciliation PENDING、Owner Fencing=2。**这一 UNKNOWN 更新仍是测试 SQL，不是本次调用 RecoveryCoordinator。**
5. 独立查询外部 SQLite Receipt，真实调用平台 `ToolReceiptReconciler.observe`，PG 原子写不可变 Receipt + Typed Event，并将 Reconciliation **RESOLVED**，原 Attempt 仍 UNKNOWN，不重做工具。
6. 官方 Native Status 和 MSSQL Durable RuntimeStatus 均为 **Failed**（正确拒绝重放），未将此当作业务任务成功。

## 环境、复测与结论

最初因旧缓存的 Worker 缺少冻结版本请求头，PG Gateway **正确拒绝**；未关闭版本门禁。使用现有缓存基础镜像 `docker build --pull=false ... Dockerfile.a34-guarded` 重建 v1 后，完整同链验证 **PASS**。

入口：`python poc/maf/functions-mssql/verify_guarded_receipt_local.py`，需要已有隔离 MSSQL/PostgreSQL/Azurite、Docker Network、Guarded Worker 基础镜像。读取本机测试数据库容器凭据，只在系统临时目录创建 Compose 环境文件，结束删除；不向 stdout/仓库写密钥。临时 HTTP Gateway 只服务随机一次性 Token 的单个用例，不能用于生产。

**范围：单机真实 Native Worker 崩溃 + PostgreSQL 业务派发 + 外部 SQLite 独立回执 + 平台真实 Receipt Adapter 对账，本机通过。** 企业 MCP/Tool 业务回执来源的信任、真实业务系统副作用及补偿/人工收口、生产 HA 均未通过；G2/G6 整体保持 PARTIAL/GAP。
