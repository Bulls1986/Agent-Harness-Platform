# POC-A / A30：任务恢复能力与覆盖矩阵（MAF）

> 日期：2026-10-08；状态：**POC 中期证据，不是选型 ADR**。
> 依据：[阶段结论台账](POC_A_STAGE_FINDINGS.md)、[任务计划](POC_A_TASK_PLAN.md)、[Task Recovery Accepted Contract](references/TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md)、[Cancellation Accepted Contract](references/CANCELLATION_TIMEOUT_PROPAGATION.md)。
> **PASS (fixture)** 仅表示对应隔离/本地场景真实运行通过，不代表 G6 整体 PASS。无运行证据绝不标 PASS。

## 1. 恢复层级与所有权

| 层级 | 恢复对象与语义 | 记录所有权 | MAF 路线现状 |
|---|---|---|---|
| S — Session Rehydration | 原生 AgentSession 序列化 / 恢复 | Runtime Store + 原生 MAF Session | 受控 State Marker 跨进程 PASS；真实模型 History/Compaction NOT RUN |
| B — Step Boundary Retry | Same Run + Same Step + **New Attempt** | Harness Run/Plan/Step/Attempt 及 Verified SideEffectContract | PURE Document Step 跨进程 PASS；其他真实能力仍 GAP |
| C — Native Checkpoint Resume | MAF 原生 Workflow Superstep + Opaque Checkpoint | Runtime/Checkpoint Provider；Harness 只记录 reference | 本地 FileCheckpointStorage 从已完成 Prepare 之后恢复 PASS；**单机开发路径** |
| W — Native HITL | Same Run WAITING_APPROVAL，MAF 原生 Request ID + Checkpoint 恢复 | Harness Approval + Runtime Request Binding | 批准/拒绝/跨进程及两处响应投递崩溃路径 PASS（模拟敏感 Executor） |
| D-dev — DTS Emulator Durable | 官方 DurableTask Worker/Client + native MAF Workflow，两个不同 Worker 进程接续原生 HITL | 官方 DTS **开发 Emulator**；Harness 不复制 TaskHub | **PASS（仅开发 Emulator）：批准/拒绝跨 Worker、Prepare 无重复** |
| D-local — Azure Functions + MSSQL 自托管 | 官方 Python MAF AgentFunctionApp 经 Functions Durable Storage Provider 将 Workflow/History 写入本地 SQL Server | SQL Server TaskHub 自托管，无 DTS/Azure 托管状态服务 | **PASS（本机 Docker 2 轮 Worker 强杀/重建 + HITL，非生产 HA）** |
| D-live — 相同 Functions 应用双 Worker 同时在线 | 官方 Python MAF 同镜像两副本，绑定同一 SQL Provider Database/TaskHub，A 在 B 在线时 SIGKILL | 微软 MSSQL Provider 分发工作，未复制 TaskHub/lease | **PASS（两次单 Docker 主机在线接管，未验证跨物理节点/平台 Same Attempt）** |
| D — Production Durable | 私有生产 Backend 下跨进程/跨节点可靠等待、恢复、接管 | 官方 Durable Backend / Engine，不由 Harness 复制 | **NOT RUN / G1/G2/G6/G8 未通过** |

Session 恢复、Step Retry、Native Workflow Checkpoint **不是等价能力**。保留运行中 Run、Step、Attempt 的 identity 与历史事实，不隐式转换或覆盖。

## 2. 失效与恢复覆盖

| 验证场景 | 实际结果 | 证据 | 限制 / 未通过范围 |
|---|---|---|---|
| PostgreSQL Task Facts（Run/Plan/Step/Attempt/Execution/Verification/Event）跨进程重读 | PASS (fixture) | [A23 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37718104459) | 事实可读 ≠ Runtime 运行可恢复；OSS 未接入 |
| MAF AgentSession 公共 API 序列化/跨进程还原，Revision 拒绝旧写 | PASS (fixture) | [A24 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37718726040) | 未测真实模型 History/Compaction |
| PURE Step 故障后 Same Run/Step + New Attempt | PASS (fixture) | [A27 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37718726040) | 不应称 Same Attempt Resume；Workspace 未恢复 |
| MAF FileCheckpointStorage 原生中间 Superstep 恢复不重复 Prepare | PASS（连续 3 次） | [A25 回归 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720102476) | 文件存储仅开发；不可随意按 list index 选择 Checkpoint |
| WAITING_APPROVAL 持久化、同 Run 跨进程及 MAF request_info 原生 ID 绑定 | PASS (fixture) | [A26 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720102476) | 固定授权输入，不是企业 IAM/真实 Model Tool Approval |
| APPROVED 后投递 Runtime 响应前崩溃并继续 | PASS (fixture) | [A26 crash CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720639309) | 生产事务联动未建立 |
| 原生响应投递意图后结果不明 | PASS（保守进入 UNKNOWN，禁止重复投递） | [A26 crash CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720639309) | 缺真实外部 Receipt / Reconciliation 收口 |
| 非 PURE 失联，不重试、保留 UNKNOWN/PENDING Reconciliation | PASS（数据与决策），外部副作用 NOT RUN | [A27/A29 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720639309) | 未验证实际 Idempotency-Key 或 Receipt |
| 平台 Execution Lease/Fencing、旧 Owner 拒绝和 PURE 新 Attempt | PASS (PostgreSQL fixture) | [A29 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720639309) | 仅 Harness Execution 权限，不代表 MAF 内部 Worker Lease |
| WAITING_APPROVAL 的安全取消（不执行未批准的动作） | PASS (PostgreSQL fixture) | [A29 CI #37721115581](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37721115581) | 当前仅平台事实，不是实际 Provider Cancel API |
| RUNNING Cancel：ACK != TERMINATED、CANCELLING 阻止新派发 | PASS (PostgreSQL fixture) | [A29 CI #37721115581](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37721115581) | 仍未连接真实 Provider cancel/abort API |
| Timeout：未 dispatch => FAILED/TIMEOUT，已 dispatch 非 PURE => UNKNOWN | PASS (PostgreSQL fixture) | [A29 CI #37721115581](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37721115581) | 未测真实工具请求超时、取消响应 |
| WAITING_INPUT 同 Run 跨进程恢复 | NOT RUN | — | 尚无平台 Input Request 事实与 MAF 入站响应桥接 |
| Native Same Attempt 在真实 LLM/Tool 中途崩溃后续跑 | NOT RUN | — | 本地单 Superstep 不能外推到任意工具副作用 |
| Workspace / Sandbox State 恢复与引用一致性 | NOT RUN | — | 仅需恢复任务相关 reference，不负责底层 Disk Backup/DR |
| DTS Emulator — 原生 Python Durable HITL 跨 Worker | PASS（开发环境，非生产） | [CI #37722178889](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37722178889) | Worker A 被 kill、Worker B 接续；两条已完成 Prepare 未重复，批准/拒绝正确；没有外部真实副作用 |
| Functions + MSSQL 自托管单主机、两个 Worker 进程接管/HITL | PASS (2 轮本机 Docker) | [本地操作与结果](../poc/maf/functions-mssql/README.md) | SQL Server dt.Instances/dt.History 写入，APPROVED/REJECTED 恢复，Prepare 零重放；不证明真实副作用 Exactly Once |
| Functions + MSSQL 双 Worker 同时在线并接管 | PASS (本机 2 轮) | [A34 前置双 Worker 报告](../poc/maf/functions-mssql/A34_CONCURRENT_WORKERS.md) | A Prepare/等待，B 已并发运行，A SIGKILL 后 B 原地接管；SQL 真实 Completed/History；不代表 Same Attempt 领域绑定 |
| 平台 PostgreSQL + MSSQL Durable 原生 WAITING_APPROVAL 同一 Attempt 身份恢复 | PASS（同一次本地双数据库 Worker 强杀测试） | [A34 双库整链](../poc/maf/functions-mssql/A34_PLATFORM_MSSQL_E2E.md) | Native 2 Completed / 42 History，两个 Run 各一个 CREATED Attempt；不代表执行中 Same Attempt Resume，真实不兼容版本迁移尚未测试 |
| MSSQL Durable 审批决定提交→Native Response 投递窗口 | PASS（同一双数据库双 Worker 故障链，平台令牌领取及 Native Completed→APPLIED）；投递后 UNKNOWN 仅 PostgreSQL 合约 4/4 | [A34 投递增量记录](../poc/maf/functions-mssql/A34_PLATFORM_MSSQL_E2E.md) | 不是跨数据库原子事务；真实 Native HTTP 半途强杀和对账仍 NOT RUN；不能证明 RUNNING Attempt 恢复 |
| MSSQL Durable 原生 RUNNING Executor 中途 SIGKILL 与 B 自动接续 | PASS ×2（本机单 Docker 主机；每轮已完成 Prepare 1 次，Executing Handler dispatch observer **2 次**，完成 1 次；Native Instance Completed、History=12） | [A34 RUNNING 原生执行证据](../poc/maf/functions-mssql/A34_RUNNING_EXECUTOR_CRASH.md) | Native in-flight Executor **会再次进入**；Marker 仅观测入口，非真实外部副作用。平台 RUNNING Attempt 不可变 Binding / 联合 PG UNKNOWN 未实测；不能声称 Exactly Once、完整 G6 或 G8 |
| 私有分布式 **生产** Durable Backend 与跨 Worker Recovery | PARTIAL / GAP | [A31 报告](../poc/maf/DURABLE_FEASIBILITY.md) | Functions+MSSQL 单机组合已通过；跨节点 HA、生产许可/支持、Harness 任务级绑定仍未验证 |
| 真实模型双轮历史与 Compaction 恢复 | NOT RUN | — | A05/A07 必须有真实 Provider / Gateway |
| OSS Evidence/Artifact Payload、Digest、RecoveryPoint PIN | NOT RUN | — | A15/A25 尚未做企业 S3 接入 |

## 3. 恢复决策（必须确定性）

- **已证明尚未 dispatch，且无副作用**：可终止、按 Policy Retry；Retry 始终是 *New Attempt*。
- **只有适用的 Native Opaque Checkpoint**：由 MAF 公开恢复 API 执行；可否保留同一个 Attempt 取决于能力与真实测试，不由平台伪造。
- **外部副作用已 dispatch 但结果未知**：UNKNOWN → Reconciliation；不得因 Timeout、Cancel ACK、Worker 失联或 Lease 过期而 blind retry。
- **取消中（CANCELLING）**：停止新 Dispatch，等待可信 Provider Termination / Reconciliation；只有收口条件满足才能标记 CANCELLED。Terminal Run 不会重开。
- **租约失效**：Fencing 拒绝旧 Worker 的平台受控操作，但不表示外部副作用一定失败；须结合 Side Effect Contract 判定。

## 4. Gate 与决策

**G1 自托管、G2 状态自主、G3 协议桥接、G6 任务级恢复、G7 完整 HITL、G8 私有 Durable/License Cliff 均保持 OPEN**，不能因某个受限 Test PASS 而自动变更。G4/G5 仍待真实 Model/Sandbox Adapter 证据。

A30 的矩阵属于阶段性记录；它不证明所有 S01–S12 场景完成。POC 下一依赖：A15 OSS Metadata/Reference、A18–A21 自托管协议入口、A31–A33 生产私有 Durable 后端能力，以及真实 Provider/Sandbox 故障注入。
