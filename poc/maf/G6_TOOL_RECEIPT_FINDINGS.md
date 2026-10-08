# POC-A G6 / 非幂等 Tool Receipt 平台对账（增量）

> 2026-10-09。状态：**本机外部 HTTP+SQLite 真实写入 / PostgreSQL 对账场景 PASS；企业 Tool/MCP Receipt、真实 Native Worker 中途强杀、整体 G6/G2 仍 OPEN**。

## 收敛边界

- 只实现 Harness 平台的 **一次派发许可（ToolDispatchIntent）**、外部已提交副作用的 **不可变回执引用（SideEffectReceipt）**，及 UNKNOWN→Reconciliation 事实对账；不实现通用 Tool/MCP 治理、远端业务幂等、不复制 Runtime checkpoint、也不实现分布式事务。
- 首次 Tool Adapter POST 前，原 Run/Attempt/Execution 为 RUNNING 且 SideEffectClass 为危险类别，PG 事务创建唯一且不可修改的 `poc_tool_dispatch_intents`，冻结 adapter、operation、request digest；重复 prepare 必须拒绝，永远不授权第二次 POST。
- 外部写入后即使 Worker 退出/丢 ACK，`RecoveryCoordinator.recover` 按既有语义写原 Attempt/Execution UNKNOWN、PENDING Reconciliation（不得 Retry）。可信 Adapter **只读**查询实际外部回执：找不到不代表没有副作用；多条冲突回执不能假装唯一成功。
- 回执严格匹配原 Run/Execution、冻结 adapter/operation，确认外部 COMMITTED 后，PG 原子写不可变 `poc_side_effect_receipts`、设 Reconciliation RESOLVED、写 `execution.receipt.confirmed` Typed Event；重放同一回执返回 ALREADY_RECONCILED，冲突回执拒绝。原 Attempt/Execution **仍 UNKNOWN**、Run **仍 RUNNING**，不擅自完结任务。
- 外部回执读取来源的鉴权/可信性须由受信 Tool Adapter 保证。这不是新建 MCP 治理层；本切片没有实现该信任认证，也没有 Exactly Once 语义。

## 真实本机执行与负例

使用 **独立一次性 Docker PostgreSQL**、不同于平台数据库的 **HTTP 服务+持久 SQLite 副作用库**：

1. HTTP POST 实际提交非幂等数据库写 1 次；丢 PG ACK；HTTP 服务停启，依然通过 GET 实际回执检索到同一 operation；PG RecoveryCoordinator 标记 UNKNOWN/PENDING；ReceiptReconciler 确认已提交并持久化；工具写次数仍是 1。
2. 外部不存在 Receipt：保持 UNKNOWN/PENDING，不派发第二次写。
3. 提前确认、adapter/operation/execution 身份伪造、矛盾结果、回执改写均拒绝。
4. 两个并行 Reconciler 同时确认同一回执：1 次首次确认 + 1 次 ALREADY_RECONCILED，回执与 Typed Event 都只有一条。
5. 若外部工具真的被重复 POST 而产生 **两个独立副作用**，外部 GET 返回歧义（HTTP 409）；平台保持 PENDING，不把它合并为成功或声称 Exactly Once。

上述 `test_tool_receipt_reconciliation_pg.py` **5/5 PASS**；关联 A34 跨库异常 **8/8 PASS**；原 Session/Recovery **3/3 PASS**，均在本轮临时 PostgreSQL 执行。结束后删除了临时 PG 容器。

## 尚未达到的门禁

- 外部系统本轮是受控真实 HTTP+SQLite 服务，不是企业 MCP/业务服务；没有可信签名/业务审计来源、企业级 Receipt Adapter。
- 没有把本轮 Receipt 逻辑与一次真实 MSSQL Durable RUNNING Worker SIGKILL 置于**同一**故障链；既有 A34 Native 断点、Binding 与受控 Sink 的局部证据不能合并成一条真实端到端验收。
- Native /run ACK 中途网络半包及真实实例 ID 回查、生产 Runtime/Workspace RecoveryPoint 恢复和企业 OSS Payload/PIN 尚待验证。
- **G2、G6 总体仍 PARTIAL/GAP；G3 真实 LiteLLM 模型验收另行待执行。**
## 2026-10-09：同一官方 Native 故障链新增真实平台回执对账

新增 [同链专项证据](G6_NATIVE_RECEIPT_SINGLE_CHAIN_FINDINGS.md)：官方 MAF Functions/MSSQL Worker A SIGKILL、B 原生 Handler 重入 **2 次**，PG 首轮派发成功、重派被拒；独立 SQLite 工具真实写入 **1 次**、回执 **1 条**；使用实际 `ToolReceiptReconciler.observe` 将 PG Reconciliation PENDING→**RESOLVED**，原 Attempt 仍 UNKNOWN，Native Failed。原文“未与 Native 同链”的限制是此增量前的阶段状态，已被本次本地技术验证覆盖；企业 MCP Receipt 和生产 Exactly Once 仍未验证。

