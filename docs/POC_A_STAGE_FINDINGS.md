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
| A28 UNKNOWN→Reconciliation | 非 PURE 被中断时产生 UNKNOWN 和持久 PENDING Reconciliation，没有第二次自动 dispatch | 真正外部副作用及 receipt 重放、人工 Reconciliation 闭环 | [PR #7 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37718726040) | PARTIAL |
| A31 Durable feasibility | 区分 Python MAF Workflow Checkpoint、本地/官方 provider 与 MAF Durable/Functions 托管路线；识别私有部署组合兼容性缺口 | 私有 Durable Backend、Functions+MSSQL 实跑、跨 Worker Same Attempt 恢复 | [调查说明](../poc/maf/DURABLE_FEASIBILITY.md) | RESEARCH / NOT VERIFIED |

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
| MAF 作为 **Durable Control Plane** | **证据不足，不得判 PASS** | 无生产私有后端、完整 HITL/Worker 恢复、同 Attempt Resume 实跑 |

## 4. POC Gates（截至本台账创建）

- **G1 自托管**：基础设施和独立 Agent Runtime 镜像已跑，托管 API、私有 Durable 端到端仍无证据；OPEN。
- **G2 状态自主**：平台任务事实及限定原生 Session 可读，但 Approval/Artifact/Checkpoint 等完整可迁移状态尚未验收；OPEN。
- **G3 协议桥接**：Responses/SSE/Typed Events 未实测；OPEN。
- **G4/G5 Runtime/Model/Sandbox 可替换**：缺双模型真实切换、CubeSandbox Adapter；OPEN。
- **G6 任务恢复**：受限 PURE Step Retry 有证据，不等于完整 waiting/same-attempt/workspace/fencing；OPEN。
- **G7 HITL**：MAF 原生 `request_info`/响应与平台 Approval 已有固定场景跨进程批准/拒绝实测；企业 Policy/IAM 校验与真实敏感 Tool Approval 尚未验证；OPEN。
- **G8 License/Managed Cliff**：待完整私有 Durable 路线验证；OPEN。

## 5. 记录与收口规则

每次关键验证或缺口收敛，需要在本文件补充 **结论、验证范围、未证实部分、CI/日志链接、风险、下一决策点**。每个 POC-A 任务继续在 [执行计划](POC_A_TASK_PLAN.md) 中登记真实状态；实现细节写在 [POC README](../poc/maf/README.md)；需要改变架构边界时按 AGENTS.md 执行 Accepted Contract/ADR 流程，**不能仅靠台账认定架构已收口**。

## 6. 下一证据门槛

- **A25**：单机 FileCheckpointStorage 的原生 Superstep Checkpoint 跨进程恢复在 POC 实测通过；接下来仍需验证绑定平台 RecoveryPoint、同 Attempt 真实阻断后恢复，以及私有分布式生产存储能否接入。
- **A26**：原生 `request_info` → Opaque Checkpoint → 平台 Approval 绑定 → 新进程响应已通过模拟安全执行验证。接下来需验证外部 Authorization Decision、真实 Tool Approval、决策落库后进程崩溃的幂等继续与原生 Durable Backend。
- **A32/A33**：只有在真实私有 Durable backend 上验证跨 Worker Same Attempt，才评定 MAF Durable Control Plane。
