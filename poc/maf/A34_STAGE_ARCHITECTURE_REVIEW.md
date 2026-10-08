# POC-A / A34：阶段性架构评审与结论（2026-10-08）

## 判定

**A34 约定的 P0 + P1 本地技术验证范围已具备结论。**
MAF Durable Functions + MSSQL Provider **可以作为 Harness Runtime 的
候选实现**，但 Harness 必须拥有 Run/Step/Attempt/Execution、Native
Instance 绑定、SideEffect Admission、版本冻结和 UNKNOWN 对账协议。

这不是宣布平台生产可用，也不是说 MAF 自身具备安全的 exactly-once
执行、自动多版本隔离或生产跨节点 HA。G6/G8 仍应按各自完整
验收矩阵评定，**不能因 A34 局部收口自动标 PASS**。

## 已知事实与实现边界

| 子目标 | 证据 | 状态 |
|---|---|---|
| 官方 Native MSSQL Durable HITL Worker A→B | 原生 GET/MSSQL History，审批与拒绝跨 Worker，Prepare 不重复 | 本地 PASS |
| WAITING Approval 及冻结 Attempt/Request 身份 | 同一 PG+MSSQL Worker 故障链、独立 PG 负例 | 本地 PASS |
| RUNNING Executor 中断时原生重入 | 两轮 Worker SIGKILL，Executor 入口 2 次，Prepare 1 次 | 本地 PASS；非天然 Exactly Once |
| 危险工具派发限一次 | 同一 MSSQL+PG+HTTP Tool Sink 故障链，首次 1、重入拒绝、UNKNOWN 对账 | 本地 PASS（受控工具） |
| 不兼容应用镜像接管 | V1/V2 真正不同镜像，B 原生进入旧 Handler，被冻结版本门禁拒绝 | 本地 PASS；原生无自动平台版本隔离 |
| Native 启动/PG Binding 崩溃窗口 | PG Launch Intent 不允许盲目 /run 重试；真实 Native orphan Running、PG UNKNOWN | 本地受控窗口 PASS |
| Native Response/PG ACK 崩溃窗口 | Native Completed + 只读终态核对投递结果；不盲目 /respond 重投 | 本地受控窗口 PASS |
| PG Adapter/Task Facts 正确性 | GitHub CI 真实 PostgreSQL，专项合约和全量回归 | 以本轮 CI 结果为准 |

## 不继续扩大 A34 的事项

- 不建立 Harness 私有 Durable Scheduler/TaskHub/Lease/History。
- 不让平台负责 MSSQL 或磁盘的备份与跨物理节点 HA。
- 不实现全局 Tool/MCP 治理、IAM、Sandbox 底层或企业权限体系。
- 不承诺自动处理 UNKNOWN 外部业务副作用；仍需读取 Tool Receipt
  / 人工核查 / Policy 许可后才允许补偿。
- 不把 Worker 自报 Workflow 版本视为生产可信认证：
  真实部署必须有受信身份与固定镜像摘要/运行时兼容信息。
- 不因这次本地 Azure Functions 测试默认生产 SDK prerelease
  稳定性/许可证/支持 SLA。
- 网络半包下的真实进程 SIGKILL、跨节点故障以及真正企业
  MCP Tool Receipt 未完整覆盖，作为**明确非 POC 门禁的剩余风险**，
  不隐藏为已验证。

## 终局任务级决策

1. **明确只读且未 dispatch**：允许在 Policy 许可后创建新 Attempt，
   不能称为原 Attempt Resume。
2. **NON_RETRYABLE 派发已发生或是否派发不明**：
   不再发起工具动作；Attempt/Execution 为 UNKNOWN，
   创建 Pending Reconciliation，等待外部证据。
3. **Native /run 结果不明**：预写唯一 Launch Intent，
   不重新提交相同 Attempt；PG Binding 未完成时隔离待核查。
4. **Native /respond 结果不明**：绝不直接重新投递，
   官方 native GET 明确 Completed 且输出与审批一致才确认 APPLIED；
   其余 UNKNOWN。
5. **版本不兼容**：在 Harness Tool Adapter 入口阻止执行。
   原生 Worker 仍可能先进入 Handler；必须在 SideEffect 前拦截。

**建议 A34 不再新增子任务**。后续回到 POC-A 整体任务门禁与架构
决策，不应因为本地 POC 并未覆盖完整生产基础设施而继续无止境扩展。
