# ADR-031 · Harness Control Plane 瘦身与 Hatchet 执行状态权威边界

> **2026-10-10 · DECIDED（自研职责边界）/ IMPLEMENTATION BASELINE；非 Hatchet 生产 Accepted ADR。**
>
> 关联：[Hatchet 目标架构](HATCHET_PROCESS_DURABLE_ARCHITECTURE_20261010.md) · [ARCH-TODO-028](../ARCHITECTURE_BACKLOG.md) · [Accepted Domain Contract](DOMAIN_MODEL_AND_STATE_CONTRACT.md) · [ADR-030 Multica](MULTICA_DESIGN_REFERENCE_DECISION_20261010.md)。
>
> 本决议仅**收敛实现职责**，不撤销已 Accepted 的 Run/Step/Attempt 业务身份、审批/Receipt、任务级恢复、终态不可重开等语义（G01/G02/G07/G08）。若需要修改这些语义，必须另行走 Accepted Contract/ADR 变更。

## 1. 结论

**Harness Control Plane 由平台自研，但只作为薄应用/领域控制层（Thin Application / Control Layer）；不自行实现第二套 Workflow Engine、Durable Scheduler、Worker Coordination、技术执行状态机或 History。**

**Hatchet 当前是 Process/Durable SPI 唯一优先实现**：复用 Workflow/DAG、Queue、Dispatch、技术重试/定时、持久等待、Worker 故障接管与 Engine History。DBOS 因许可证正式排除；Temporal/MAF Durable/手写 PG Worker 仅为历史证据，当前不并行开发。

**权威事实分层，不能混为一谈：**

- **Hatchet = 技术执行状态权威。** Provider WorkflowRun/TaskRun 的排队/领取/执行/失败/完成、DAG 可运行性、Timer/Retry/Wait、Worker 接管和引擎 History。Harness 不得另建并行调度状态或重领同一 Provider Task。
- **Harness = 业务事实与决策权威。** Conversation/Turn/Run、Plan/Step/Attempt/Execution 的平台 ID、冻结版本、Verification/Approval/Policy、SideEffectReceipt/UNKNOWN/Reconciliation、Artifact/Evidence、业务 Event/Terminal 状态。必要状态是有证据可核对/重建的**领域投影**，不得镜像 Hatchet 所有内部技术状态。
- **业务状态机仅为最小确定性不变式。** Terminal Run 不重开、审批身份可信、Verification PASS 才能完成业务 Step、Cancel ACK 不等于 CANCELLED、UNKNOWN 不能盲重试、Retry/Replan/Resume 不混淆。它不是又一个 Durable 引擎。

## 2. 自研/复用职责表

| 能力 | Owner / 落地要求 |
|---|---|
| PDLC UI/会话/用户/项目/Agent/Skill 历史资产 | **复用现有 PDLC**；通过 Legacy Facade/ID Mapping 平滑迁移 |
| Chat/Run API、Responses-compatible SSE/Event Cursor | **Harness 薄 Facade + Event Bridge**；真实 Token 不以 Hatchet Log 冒充 |
| Run/Plan/Step/Attempt 领域 ID、版本冻结、Verification、业务终态 | **Harness 最小领域模型/事实及状态投影**；保留 Accepted Contract |
| Workflow/DAG、Task Queue/Dispatch、Timer/Retry、Engine Wait、Worker 接管 | **Hatchet Engine**；不再造通用 Scheduler/History/Queue |
| Workflow/Task ID Binding、事件/状态核对、幂等创建 | **Hatchet Process/Durable Adapter**；不得假设平台 Attempt 与 Provider Retry 永远 1:1 |
| Approval/WAITING_INPUT 的授权、决议及证据 | **Harness Domain**；长等待/唤醒执行尽量使用 Hatchet（尚未 P0 实测） |
| 资源分类、Admission/优先级策略、Scope/Lease/Fencing、Capability | **Harness Policy/Execution Boundary**；实际 Queue/Worker 调度委托 Hatchet |
| Agent Loop 与 Pydantic/OpenAI/OpenCode/MAF 执行 | **AgentRuntime SPI**；独立适配器 |
| Shell/FS/Git、Sandbox 实例与生命周期 | **SandboxProvider SPI + Cube**；按需、可信 Scope，空闲 Session 零 Sandbox |
| Tool Receipt、未知副作用对账、安全继续/重试裁决 | **Harness Tool/Domain Boundary**；Hatchet 不得直接重放未知非幂等操作 |
| Provider 执行技术历史 | **Hatchet 独立 PostgreSQL Schema**；不是业务事实源 |
| 最小 Task Facts/Binding/Approval/Receipt/Event/RecoveryPoint | **Harness 独立 PostgreSQL Schema**；不复制 Provider 完整技术 History |
| Artifact/Evidence 大 Payload | **OSS/S3**；平台保存 Ref/Digest/Lineage |
| IAM/MCP Governance/Secrets/APM/Backup/Cost 产品 | **外部既有能力**；Harness 仅接入，不重建 |

## 3. 状态与一致性合同

**逻辑最小事实（不是既定 DDL）：** PlatformRun（run_id、turn_id、frozen_version、business_state、terminal_ref）；PlatformStep（step_id、plan_version、intent、verification/outcome）；PlatformAttempt/Execution（attempt_id、step_id、side_effect_class、outcome/receipt_ref）；ProviderBinding（platform run/step/attempt IDs 与 provider workflow/task/retry refs）；Approval/Receipt/Reconciliation；RecoveryPoint/Event/ArtifactRef。

- **创建**：平台先记录 Run 与冻结版本事实；以幂等 Binding/Outbox 经 Process SPI 创建 Hatchet Workflow。跨平台 Task Facts 与 Hatchet 系统存储不假设分布式原子提交，不加 2PC。
- **执行**：Hatchet 调度 Task；AgentRuntime 通过受信任 ExecutionContext 运行并产生真实 Typed Events、Tool Receipt、Evidence。Harness 只根据领域事实/Verifier/Approval 对业务终态作确定性裁决。
- **重试与恢复**：Provider Workflow/Task 的真实执行状态以 Hatchet 为准；Harness 核对业务 Step/Attempt、Receipt、Policy、Execution Owner/Fencing、Sandbox Lease 后放行。自动重试仅对 PURE 或已证明安全的幂等动作；ACK 丢失且可能已有外部副作用时 UNKNOWN → Reconciliation → 人工/自动安全决议。
- **状态失配**：Hatchet SUCCEEDED、平台投影仍 RUNNING → 基于 Provider 结果和业务证据幂等补录；平台 RUNNING、Hatchet FAILED → 先核查 Receipt 和 Lease，不根据过期业务投影重新 Dispatch。可以使用 Event/Outbox 与轻量一致性核对，**不可把它扩展成第二套 Scheduler**。
- **持久审批**：Hatchet 负责技术 wait/wakeup，平台保留审批 Principal/Resource/Action/Policy 和业务 WAITING_APPROVAL/WAITING_INPUT，同一个 Run 恢复；不占 Worker 的等待/取消/超时行为仍需真正验证。

## 4. 禁止事项与开发边界

1. 不新建通用 HarnessQueue、DurableScheduler、WorkerRecoveryDaemon、WorkflowHistory，或复制 Hatchet Queue/Retry/Timer/Worker 内部状态机。
2. 不把 Provider WorkflowRun ID 视为 Platform Run ID；Hatchet History 不是业务 Task Facts；Domain 不导入 Hatchet SDK。
3. 不删除平台 Domain Contract 的 Run/Plan/Step/Attempt/Execution/RecoveryPoint/Approval/Receipt 事实及业务决策规则。**“薄”不等于弱化审计、安全与恢复。**
4. 不以 Hatchet 自动 Retry 绕过 SideEffectReceipt、UNKNOWN 对账、Scope/Lease/Fencing、Approval 或 Cancel 安全要求。
5. 不强制每个历史 Session 一个常驻 Worker/Agent 进程/MicroVM；不在 Harness Kernel 直接执行宿主机 Shell；不重复建设企业治理产品。
6. 不因两个分项 Hatchet POC 通过而宣布完整一体化生产 Accepted。WAITING_APPROVAL、真实非幂等 Receipt ACK-loss、Token SSE/Cancel、Cube Lease/Fencing 和 100 并发密度继续归 ARCH-TODO-028 等现有门禁。

## 5. 实施分解与影响

**最终实施合同**：本 ADR-031 仅冻结瘦身职责；[HC-01](HATCHET_WORKFLOW_MAPPING_CONTRACT_20261010.md)、[HC-02](HARNESS_HATCHET_CONSISTENCY_CONTRACT_20261010.md)、[HC-03](HATCHET_WORKER_SANDBOX_BINDING_CONTRACT_20261010.md)（合称 ADR-032）进一步冻结映射、异常一致性与可信 Sandbox Binding。任何新状态机/队列/恢复模块必须先对照这三份合同审查。

- **ExecutionScheduler 瘦身**：仅保留平台资源类别、执行准入/安全策略及容量规则；Queue/Dispatch/通用 Worker 管理和 Durable Retry 交 Hatchet。
- **Run/Step/Execution 状态收敛**：保留最小身份/审计/版本/验收/业务终态不变式，技术状态由 Provider Binding + Hatchet History 提供并形成平台投影。
- **RecoveryManager 瘦身**：专注安全恢复裁决、Receipt 对账和受信任 Lease；真正的 wait/retry/resume/failover 复用 Hatchet。
- **下一阶段是集成验证，而非重新选型**：Hatchet Adapter + 平台状态投影 + AgentRuntime SPI + CubeSandbox + 真 SSE + Receipt/Approval 的同 Run 全链，先验证再谈生产准入。

**本 ADR-031 确定的是“平台必须自己做什么、绝不重复开发什么”；不是完整 Hatchet 生产上线裁决。**
