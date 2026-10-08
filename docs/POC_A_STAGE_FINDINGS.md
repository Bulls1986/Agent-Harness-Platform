# POC-A 阶段性结论与证据台账（MAF）

> 记录日期：2026-10-08；性质：**POC Evidence Ledger / Interim Findings**，并非 Accepted ADR。
> 本台账以每阶段真实执行证据为准，结论拆分为 **Verified / Partial / Not Run / Gap**。
> 只有通过完整架构门禁并形成正式 ADR 后，才允许将某个候选标记为最终选型。

## 1. 阶段性结论（按任务能力分开判断）

| 阶段 / 任务 | 已验证的结论（Verified） | 尚不能推导的能力 | Evidence | 状态 |
|---|---|---|---|---|
| 基线 A00–A04 | 固定版 MAF Core/OpenAI Adapter API 可安装并实例化；Document/Coding 正反验收；PostgreSQL/OTLP 本地启动 | 真实 LLM、托管协议、自主 OSS、生产 Durable | [A00–A04 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37715143198) | PARTIAL |
| A06/A07 公开扩展点 | TodoProvider、AgentModeProvider、ContextProvider Hook 与 AgentSession 构造通过 | 模型驱动的 Todo/Plan、完整 History/Compaction、持久 Context | [PR #5 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37717098080) | PARTIAL |
| A11/A12 Native Workflow | 真实 MAF WorkflowBuilder/Executor 可运行；外部独立 Document Verifier 判定正确结果 COMPLETED、错误结果 FAILED；不允许无 Evidence 成功 | 完整 Agent Plan/Execute/Replan、Coding Sandbox、OSS Evidence | [PR #5 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37717098080) | PARTIAL |
| A23 Platform Facts | Run/Plan/Step/Attempt/Execution/Verification/Event PostgreSQL 原子写入及进程外读取；终态不可重开、旧 Plan 迟到不能覆盖 | 所有 Recovery/Approval/Artifact 元数据、持久分布式任务调度 | [PR #6 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37718104459) | PARTIAL |
| A24 Native Session | MAF AgentSession 公共序列化 API、PostgreSQL 私有存储和跨 Python 进程重新加载已通过；revision/CAS 拒绝旧写 | 真实模型对话 History、Compaction、原生 Workflow Checkpoint | [PR #7 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37718726040) | PARTIAL |
| A25 Native Workflow Checkpoint（单机路径） | MAF FileCheckpointStorage 保存 Superstep Checkpoint；独立 Python 进程按 Checkpoint **父子血缘**选择 Prepare 之后的恢复点并完成 Workflow。列表返回顺序不保证稳定，早期 `checkpoints[-2]` 导致重放；已按官方公开 `previous_checkpoint_id` 血缘修复，并通过 CI 连续 3 次跨进程恢复、`prepare_reexecuted=false` | 私有分布式 Durable Backend、生产安全审批跨 Worker、同 Attempt + 复杂工具副作用不重复 | [PR #8 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37719461420) | PARTIAL |
| A26 Platform + Native MAF HITL | PostgreSQL WAITING_APPROVAL 保持 Same Run/Step/Attempt；使用 MAF 公开 `request_info`/`response_handler` 和 FileCheckpointStorage 生成真实请求；请求 ID、Opaque Checkpoint ID 与 Approval 原子绑定；独立进程重建 Workflow，校验 Request ID 后执行 APPROVED/REJECTED；拒绝不会执行模拟敏感 Executor | CI 固定了审批人/Policy 授权，尚未对接企业 IAM；并非真实 Model Tool Approval 或生产 Durable 后端；审批决定提交至 Runtime 恢复之间的 Crash Gap 待处理 | [PR #8 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37719461420)、[PR #9 最终 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720102476) | PARTIAL |
| A27 Safe Step Boundary | 进程显式异常退出后，新进程仍用 Same Run + Same Step + New Attempt 验证只读 PURE Document 工作；旧 Attempt 无权提交终态 | 自动 Worker ownership/fencing、原生 Same Attempt Resume、Workspace 恢复 | [PR #7 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37718726040) | PARTIAL |
| A26 Crash-gap / Response Delivery（增量） | PostgreSQL 审批决定已提交、MAF 响应尚未投递时，进程退出码 92 后另一进程可恢复原 Run；已投递响应再次恢复不会重复进入模拟敏感 Executor；投递意图后退出码 93 必须保持 UNKNOWN 并拒绝盲重放。3 项 DB 测试与两处进程退出注入通过 | 真实外部副作用、SideEffectReceipt、UNKNOWN 自动核对闭环、企业 IAM、生产 Durable 服务 | [PR #10 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720639309) | PARTIAL |
| A29 Execution Ownership / Fencing（增量） | 平台自有 Execution 的 PostgreSQL Claim/Heartbeat/一次 Dispatch 门禁及 epoch token；4 项 DB 集成测试证明过期/旧 Owner 不能提交，Lease 有效不得接管，PURE 续跑须 New Attempt，非 PURE 进入 UNKNOWN | Cancellation/Timeout 传播、真实外部工具执行的 token 端到端传递、生产并发调度与跨节点稳定性 | [PR #10 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720639309) | PARTIAL |
| A29 Cancellation / Timeout（增量） | 新增 6 项真实 PostgreSQL 合约测试：WAITING_APPROVAL 取消保持无 Execution，RUNNING→CANCELLING 及 ACK≠TERMINATED，安全停机才 CANCELLED；非 PURE 已派发即使终止也保留 UNKNOWN；未派发 Timeout=FAILED/TIMEOUT，已派发高风险 Timeout=UNKNOWN/TIMEOUT_AFTER_DISPATCH | 尚未调用真实 MAF Provider Cancel/Abort、MCP/Sandbox Tool Timeout；未实现生产取消传播完整闭环 | [A29 CI #37721115581](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37721115581) | PARTIAL |
| A30 恢复能力矩阵 | 分开列出原生 Session、PURE Step Retry、单机 File Checkpoint、原生 HITL 和生产 Durable 的证据、恢复等级、缺口与门禁 | WAITING_INPUT、真实外部副作用 Receipt/OSS、Workspace/Sandbox State、私有 Durable 跨 Worker 未验证 | [恢复覆盖矩阵](POC_A_RECOVERY_MATRIX.md) | PARTIAL |
| A28 UNKNOWN→Reconciliation | 非 PURE 被中断时产生 UNKNOWN 和持久 PENDING Reconciliation，没有第二次自动 dispatch | 真正外部副作用及 receipt 重放、人工 Reconciliation 闭环 | [PR #7 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37718726040) | PARTIAL |
| A31 Durable feasibility | 官方 DTS Emulator 与 Functions+MSSQL 两条路径已独立核对；Python MAF+Functions+MSSQL 在完全本地 Docker 成功安装、使用正式 MSSQL Provider、跨 Worker HITL 恢复通过 | 生产支持/许可、SQL Server HA/容灾、跨物理节点及更丰富故障模型仍未实测 | [Durable 可行性报告](../poc/maf/DURABLE_FEASIBILITY.md) | LOCAL FEASIBILITY PASS / PRODUCTION GAP |
| A32/A33 — 官方 DTS Emulator 跨 Worker | 真实 `DurableAIAgentWorker.configure_workflow` + `DurableWorkflowClient` 在 Docker DTS Emulator 上运行。Worker A 进入两个原生 HITL 等待后被 kill -9，Worker B 另进程接续；批准得到 SIMULATED_EXECUTION，拒绝无 Action；两条 Prepare 各仅执行一次。无模型/Foundry 凭证。 | DTS Emulator **只用于开发**；没有生产私有 DTS backend、Functions/MSSQL 分布式执行、真实 Tool SideEffectReceipt、任务 ID Same Attempt 绑定 | [Docker DTS Emulator CI #37722178889](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37722178889) | PASS (DEV EMULATOR) / PRODUCTION GAP |
| A32/A33 — 自托管 Functions + MSSQL Durable（本机） | 官方 MAF Python AgentFunctionApp + Azure Functions v4 + MSSQL Durable Provider 在隔离 Docker 中真实启动；Host 明确输出 Using the mssql storage provider，MSSQL dt.Instances/dt.History 实际持续写入。两轮新 Workflow 进入原生 HITL 等待后，强制 kill Worker A，Worker B 继续相同 Instance/Request 并 APPROVED/REJECTED；两次均 Completed，Prepare 零次重放，批准 Action 1 次，拒绝 Action 0 次。SQL Server 与 Azurite 未重启。 | 单机开发主机 + Developer Edition；尚无生产许可/支持/HA、真实外部副作用、平台 Run/Attempt 映射、企业 IAM 与 OSS Workspace 恢复证据 | [本机真实执行手册与证据](../poc/maf/functions-mssql/README.md) | PASS (LOCAL SINGLE HOST) / PRODUCTION GATES OPEN |
| A33/A34 前置 — 相同应用的双 Worker 并发 | **两轮本地实测**：Worker A 单独 Prepare→native request_info WAIT；B 在 A 存活时加入相同 SQL Server DurableA34 数据库/TaskHub，双方 MSSQL Provider/TaskHub 日志已核验且镜像 ID 一致。B 查询原生相同 Instance/Request ID；A 被 SIGKILL 后 B **不重启**，APPROVED/REJECTED 均完成；每轮 MSSQL Completed=2、History=42、Prepare replay=0、批准 Action=1、拒绝 Action=0 | 两容器位于同一 Docker 主机，未验证跨节点 HA/版本升级/企业 IAM/真实副作用，也没有平台 Same Attempt 绑定；**A34 整体仍 OPEN** | [本地双 Worker 实验记录](../poc/maf/functions-mssql/A34_CONCURRENT_WORKERS.md) | PASS (LOCAL 2 REPLICAS) / PRODUCTION GATES OPEN |
| A34（增量）原生 Durable Approval/Attempt 绑定及冻结版本 | 平台 PostgreSQL Approval 请求与原生 Functions Instance/Request、Run/Step/Attempt、Workflow/Runtime Version 在同事务写入；不可变且原生 Instance/Request 唯一；恢复读取原生 Pending 后进行平台身份/版本 fail-closed 校验；真实 PostgreSQL 测试与可选双 Worker 合并探针 | 这里只验证 **WAITING_APPROVAL Same Attempt Identity**，Attempt 仍 CREATED；原生 Running Attempt 中途恢复/真正不兼容 Workflow 升级回放未测试，平台 Same Attempt Resume 不得宣告 PASS | [A34 证据边界](../poc/maf/A34_ATTEMPT_VERSION_FINDINGS.md) | PARTIAL / INCREMENTAL |

**恢复能力完整清单**：[A30 恢复覆盖矩阵](POC_A_RECOVERY_MATRIX.md)，明确限制“单项 Fixture PASS ≠ 整体 G6 PASS”。

## 2. 不应混淆的三种恢复

1. **Session rehydration**：恢复 MAF AgentSession 的序列化数据。A24 已证明受控状态标记可跨进程恢复；未证明原生 Workflow 状态。
2. **Step Boundary Recovery**：根据平台保存的事实，对明确 PURE 的中断 Step 创建新 Attempt；A27 已证明限定用例安全续跑。Retry 并非 Resume。
3. **Native Runtime Checkpoint Resume**：Runtime 自己从 opaque checkpoint 恢复等待中的 Workflow/Executor 状态，同一个 Attempt 无需重复执行。这是 A25/A32–A34 的验证目标，不能拿前两项替代。

官方文档：[MAF Checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)；[MAF HITL](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)。对于 Python，InMemoryCheckpointStorage 仅进程内；FileCheckpointStorage 是单机开发路径；CosmosCheckpointStorage 属于云分布式路径。文件存储对 checkpoint 序列化有受限 pickle 的安全边界，不可将未经可信保护的外部文件作为恢复输入。私有 Durable 部署必须实测，不由文档推断。

## 3. 目前的架构候选判断（非 ADR）

| 候选 | 阶段结论 | 证据边界 |
|---|---|---|
| MAF 作为 **Agent Runtime** | **有积极证据，尚未验收** | Public Harness/Session/Provider 可用；缺真实模型多轮和 Sandbox 接入 |
| MAF 作为 **Workflow Engine** | **局部可行，尚未验收** | Native Workflow + Independent Verify 可运行；缺完整 Plan→Execute→Verify→Replan 及 Recovery |
| MAF 作为 **Durable Control Plane** | **Python MAF + Functions + MSSQL 自托管组合在单机 Docker 上跨 Worker HITL 实测可行** | 暂不能宣布生产可用：许可/支持、HA、Harness Same Attempt 绑定、真实副作用与全量 G1/G2/G6/G7/G8 尚未通过 |

## 4. POC Gates（截至本台账创建）

- **G1 自托管**：Python MAF + Functions v4 + MSSQL Storage Provider 在完全本地 Docker 自托管部署与真实 Workflow/HITL 跨 Worker 接管已通过；生产许可、扩展支持、跨节点 HA 及正式发布尚未验证；OPEN。
- **G2 状态自主**：平台任务事实及限定原生 Session 可读，但 Approval/Artifact/Checkpoint 等完整可迁移状态尚未验收；OPEN。
- **G3 协议桥接**：Responses/SSE/Typed Events 未实测；OPEN。
- **G4/G5 Runtime/Model/Sandbox 可替换**：缺双模型真实切换、CubeSandbox Adapter；OPEN。
- **G6 任务恢复**：已实测 PURE Step Retry、FileCheckpoint、Approval Crash Window、Execution Fencing、Cancel/Timeout、DTS Emulator，以及 Functions+MSSQL 的跨 Worker 原生 HITL 恢复（重复两轮）和同时在线双 Worker 接管（重复两轮）。真实副作用回执、Workspace/OSS、Harness 原生 Same Attempt 映射及跨节点场景仍缺证据；OPEN。
- **G7 HITL**：MAF 原生请求 + Checkpoint 与平台 Approval 的批准/拒绝、两处进程故障注入已通过；仍待外部 Policy/IAM 和真实 Tool Approval + Reconciliation；OPEN。
- **G8 License/Managed Cliff**：待完整私有 Durable 路线验证；OPEN。

## 5. 记录与收口规则

每次关键验证或缺口收敛，需要在本文件补充 **结论、验证范围、未证实部分、CI/日志链接、风险、下一决策点**。每个 POC-A 任务继续在 [执行计划](POC_A_TASK_PLAN.md) 中登记真实状态；实现细节写在 [POC README](../poc/maf/README.md)；需要改变架构边界时按 AGENTS.md 执行 Accepted Contract/ADR 流程，**不能仅靠台账认定架构已收口**。

## 6. 下一证据门槛

- **A25**：单机 FileCheckpointStorage 的原生 Superstep Checkpoint 跨进程恢复在 POC 实测通过；接下来仍需验证绑定平台 RecoveryPoint、同 Attempt 真实阻断后恢复，以及私有分布式生产存储能否接入。
- **A26**：原生 `request_info` → Opaque Checkpoint → 平台 Approval 绑定 → 新进程响应已通过模拟安全执行验证。接下来需验证外部 Authorization Decision、真实 Tool Approval、决策落库后进程崩溃的幂等继续与原生 Durable Backend。
- **A29**：平台 Execution 的 owner/epoch/Lease、取消/超时任务事实在 PostgreSQL 限定场景实测通过；仍需真实 Provider Cancel/Timeout、Data Plane 副作用与 SideEffectReceipt 及 stale Worker 请求拦截端到端证据。
- **A30**：中期恢复能力覆盖矩阵已创建，但各 G/S Gate 均保持相应未完成状态；矩阵不是最终 POC 结论。
- **A32/A33**：DTS Emulator 和完全本地 Functions+MSSQL 两条原生跨 Worker HITL 路径已有真实证据；下一步收敛生产支持/许可、跨节点与 SideEffectReceipt，并评估 MAF Durable Control Plane 是否可正式采用。
