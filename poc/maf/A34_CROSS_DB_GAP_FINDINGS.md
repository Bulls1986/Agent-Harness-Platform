# POC-A34 / P1：Native 启动与 Response 结果不明的跨库故障窗口

> 2026-10-08。**本地官方 MAF Durable + MSSQL + PostgreSQL 的受控故障窗口测试 PASS**。
> 不采用分布式事务、不操作 DurableTask 私有状态、不清理已有 TaskHub。
> 本轮故意跳过部分 PG Commit/ACK 模拟进程中断，**不是 HTTP 中途
> SIGKILL / socket 半包注入**。Python 领域方法由 CI 真实 PG 单测覆盖。

## 1. Native /run 已成功，但 PG Binding 未提交

问题：原生 Durable Instance 已创建，Harness 未收到/未保存 Instance ID。
如果重启时盲目重发 `/run`，可能创建两个 Native Instance。

**最小设计：** 平台先在 PostgreSQL 事务写入不可变
`poc_maf_durable_launch_intents`：Run/Step/Attempt/Execution、
Workflow Name、冻结 Workflow/Runtime Version。该表不存原生 History、
不对 Native Provider 租约进行操作。每个 Execution / Attempt
只允许一个 Launch Intent。Native start 只由可信 Adapter 发起一次，
得到真实 ID 后再写入 `poc_maf_durable_running_bindings`。

启动与绑定之间崩溃时，不能把“本地没有 Native ID”解释为
“Native 未启动”。`DurableLaunchIntentStore.inspect` 返回待核查状态，
`quarantine_unbound` 在锁定平台事实后置原 Attempt/Execution
`UNKNOWN` 并写入 `PENDING Reconciliation`；再次 `prepare`
被主键/唯一性拒绝，不会授权重新提交。Native Instance 的真实存在、
状态应在 MAF 官方 API 只读获取，不能凭任务模型猜测。

**真实 Native + PG 受控窗口：**

- Instance `c264e38ed5534c0a80155d58f44c89e6`。
- 官方 Native HTTP 证明同一 Pending Request；实际
  MSSQL `dt.Instances=Running`，本实例 `dt.History=11`。
- 平台 Launch Intent **1**、Native Binding **0**、Attempt **1**；
  对账隔离结果 Attempt/Execution `UNKNOWN`、
  Reconciliation `PENDING`；模拟动作/工具执行 **0**。
- 故障注入方法：Native `/run` 成功后刻意跳过 PG Binding，
  对账事务通过受控测试 SQL 提交；没有凭空模拟原生 Instance。

## 2. Native /respond 已送达，但 PG 投递确认未提交

问题：Native HTTP Response 已应用，但调用者崩溃、无法更新
`poc_maf_hitl_deliveries`。第二个 Worker 不可以盲目重发 Response。

**最小设计：** 保留既有 `DurableApprovalDelivery.claim`：
第一次认领 `IN_FLIGHT`，不确定/重复认领转 `UNKNOWN`。
新增 `reconcile_observation`，接受**可信 Adapter 从官方 Native
GET Status 获取**的 Instance/Request/状态/输出，严格检查
Approval→Attempt→Native Instance/Request 及冻结 Workflow/Runtime；
仅当真正 `Completed` 且输出与批准/拒绝决策一致才确认
`APPLIED`，且幂等返回 `ALREADY_APPLIED`。其他
Running/Pending/Failed/Terminated、输出矛盾、不匹配版本全部
保留 `UNKNOWN` 或直接拒绝，不会再次向 Native `/respond` 投递。

**真实 Native + PG 受控窗口：**

- Instance `2ab91024f0db4ce8855954c19040c314`。
- PG 原子保存 WAITING Approval/Native Instance/Request Binding，
  然后 Approved + Delivery `IN_FLIGHT`；
  官方 Native `/respond` **只发 1 次**。
- Native `Completed`、MSSQL History **23**；
  模拟批准动作 **1 次**。
- 注入缺失的是 **PG Delivery ACK**：Native 已成功，但 PG 仍
  `IN_FLIGHT`；从官方 Native GET Status 观察到已 Completed 后，
  由受控测试 SQL 最终设为 `APPLIED`。没有再次发送 Response。

## 验证入口与边界

- 本地复现：`python poc/maf/functions-mssql/verify_cross_db_windows.py`。
  仅使用已启动的 17082 官方 MAF Functions Worker、既有专属
  MSSQL/Azurite/PostgreSQL；每轮随机 Case/Native Instance/Task ID，
  不触碰之前的历史。
- PostgreSQL 领域合约：`test_durable_cross_db_gaps_pg.py`
  包含原生启动意图去重/合法与伪造血缘拒绝、未绑定隔离、
  已绑定只读校验、响应未知→实际 Native Completed 对账、
  Pending/Failed/输出矛盾保持 UNKNOWN、冻结身份失配拒绝、
  审批拒绝分支无敏感副作用等负例。CI 真实 PG 执行。
- 真实 Native 状态/History 来源于 MSSQL Durable Provider，
  但 **PG UNKNOWN/APPLIED 的 E2E 故障注入更新是测试 SQL**；
  Python Adapter 的同等逻辑在 PG 专项测试验证，不能说本次
  Native HTTP 测试直接调用过它。
- 生产级网络半包、跨实例故障注入、真正企业 Tool Receipt、
  跨物理节点 HA、MAS SDK 升级/许可/IAM 均不在 A34 POC 范围。
  Native 仍可能在无 PG Binding 时运行 Prepare，所有危险 Tool
  必须经过 Harness Execution+Native Binding+Frozen Version 共同门禁。
- `UNKNOWN` 保留待核对，不可降级成自动 Retry；这是任务级安全恢复，
  不是 TaskHub Lease/History 恢复。

**P1 判定：关键跨库故障窗口的平台安全合约和真实 Native HTTP
受控实验 PASS。实际 Worker 在 HTTP 中途 SIGKILL 不在本轮证据内。**
