# AGENTS.md

本文件定义 Agent、Coding Assistant、自动化工具以及人工协作者在本仓库中的统一工作原则。  
适用于仓库根目录及全部子目录；若未来某个子目录存在更具体的 `AGENTS.md`，则以更深层文件的补充约束为准，但不得违反本文件的核心架构原则。

# 1. 项目目标

本仓库建设的是企业级、厂商无关的 **Agent Harness Platform**。

任何工作都必须优先保护以下目标：

- 厂商无关（Vendor Neutral）。
- 控制平面 / 执行平面分离（Control Plane / Data Plane Separation）。
- 领域模型由平台拥有，不由具体 Framework / Provider 定义。
- 状态可持久化、可恢复、可审计。
- Runtime / Model / Sandbox / Tool / Storage 可替换。
- Coding Execution 生产默认隔离执行。
- 架构结论必须有清晰边界、证据和可验证的 POC。

# 2. 开始任何工作前必须阅读

涉及架构、POC、接口、实现或测试前，至少阅读：

1. `README.md`
2. `docs/ARCHITECTURE_GUARDRAILS.md`（G01–G20 硬边界、设计 Review、PR 与 CI 准入）
3. `docs/ARCHITECTURE.md`
4. `docs/ARCHITECTURE_BACKLOG.md`
5. `docs/POC.md`
6. 若涉及 Process/Durable、Agent 串联、持久执行或 Worker 恢复，先读 `docs/references/HATCHET_PROCESS_DURABLE_ARCHITECTURE_20261010.md`（当前实施候选基线）及 `docs/references/THIN_HARNESS_CONTROL_PLANE_DECISION_20261010.md`（ADR-031：Hatchet 技术执行权威；Harness 薄领域控制和最小状态投影，不重造 Scheduler）
7. 涉及业务 Run/Plan/Step/Attempt 到 Hatchet 的映射/Retry/Replan 时阅读 `docs/references/HATCHET_WORKFLOW_MAPPING_CONTRACT_20261010.md`（HC-01）；跨存储/outbox/状态投影/Receipt 阅读 `docs/references/HARNESS_HATCHET_CONSISTENCY_CONTRACT_20261010.md`（HC-02）；Worker/Cube/Scope/Lease/Fencing 阅读 `docs/references/HATCHET_WORKER_SANDBOX_BINDING_CONTRACT_20261010.md`（HC-03）
8. 涉及现有 PDLC 迁移开发，读取 `docs/DEVELOPMENT_BACKLOG.md`（DEV-PDLC-01～05，旧代码/Schema 实码盘点属后续开发）
9. 与当前任务直接相关的 `docs/references/*.md`

如果任务涉及已经关闭的架构待办，必须先读取其 Accepted Contract。

禁止在不了解现有 Decision / ADR 的情况下重新发明同类模型。

**开发前置护栏：** PR 必须指明受影响的 Gxx、变更 Owner、Accepted Contract 是否改变，以及成功/失败证据。违反 H 类约束时先完成对应 ADR/Contract 变更；R 类必须补 Review 证据；D 类选型须通过 Backlog/POC/Decision。自动 CI 只覆盖可静态判断的部分，不能代替真实副作用/恢复/隔离验收。

# 2.1 强制工程流程：测试先行、架构守护、事后复盘

**这是所有开发和 POC 的默认准入与收口基线，不因任务紧急或代码规模小而跳过核心步骤。** 纯文档/格式调整可以用静态校验替代运行测试，但仍应记录结果；行为变更不得以“实现方便”为由跳过 Red/Green 证据。

1. **Before coding：** 先读对应 OpenSpec Proposal/Specs/Design/Tasks 和 Accepted Contracts，识别 Gxx 硬约束、事实 Owner、正例/反例、失败/超时/重复投递窗口；新增功能先更新 Spec/Tasks。
2. **Red（测试先行）：** 在改生产代码前，先写能证明目标行为缺失的失败测试、回归测试或真实场景测试；记录失败原因。至少覆盖一项安全负例/错误路径（例如 UNKNOWN 阻断、无权限拒绝、终态不可重开），不得只测 Happy Path。
3. **Green（最小实现）：** 只实现让这些测试通过的最少职责，复用 Hatchet/AgentRuntime/SandboxProvider 公共能力，不扩大 Harness Kernel 或重造 Scheduler；不允许以 Mock SDK/内存数据库替代要求真实引擎/持久化的验收。
4. **Refactor + Review：** 重构后复跑原始回归、架构 Guard、OpenSpec Strict Validation，检查 Vendor Neutral / Domain Boundary / 可信 ExecutionContext / 短期 Capability / SideEffect Receipt；PR 必须列明改变哪些 Gxx、Accepted Contract 是否变化。
5. **Live acceptance：** 按所述 Gate 执行真实 PG/SDK/Worker/Cube/工具行为等测试；标注环境、命令、Run ID/Trace/Workflow ID、CI run URL。**Skipped、Mock、NOT_TESTED、还在排队或尚未完成的 CI 不得记为 PASS**；历史独立 POC 的 PASS 不等于新的一体化链路已通过。
6. **Retrospective（事后复盘）：** 每次有意义的功能、架构改动或 POC 收口前，必须复盘「目标/证据/实际失败/根因/修复措施/新增回归/遗留风险/经验沉淀」。重要变更需提交 `docs/retrospectives/` 专题；轻量修复可以在 PR Summary 中复盘。**从问题中提炼可复用的编码、测试、环境或架构护栏，并更新 AGENTS/OpenSpec/CI/Backlog 的合适位置。**
7. **Closeout：** 只有经过真实门禁、OpenSpec Tasks 勾选与 PR/CI 审核，才将当期任务标为 CLOSED；生产 Gate 与有限 POC Gate 必须区分。不可因为用户让“持续推进”就把未测试的工作标记完成，或绕过架构决议去赶进度。

对于当前首个最小闭环，遵循 [OpenSpec](openspec/changes/minimal-run-closed-loop/proposal.md) 与 [测试先行复盘](docs/retrospectives/MINIMAL_CLOSED_LOOP_20261010.md)。今后将这一工作顺序视为默认行为，而不是一次性的专项要求。

# 3. 架构优先级

发生冲突时，按以下顺序处理：

~~~text
Accepted ADR / 正式架构
        ↓
Accepted Architecture Contract
        ↓
POC 门禁 / Contract
        ↓
当前 Backlog Decision
        ↓
框架或 Provider 的默认实现
        ↓
实现便利性
~~~

**不能因为某个 Framework 当前更容易实现，就反向改变平台领域模型。**

MAF、Temporal、ADK、CubeSandbox、Codex、OpenAI Agents SDK 等都属于历史 POC 或独立 Adapter，不拥有平台核心语义。**2026-10-10 有效的 Process/Durable 首选实现为 Hatchet Embedded/自托管 + PostgreSQL，经可替换 SPI 接入；DBOS 因多 Executor 商业许可证限制正式 REJECTED，不再列为候选、备选或 POC 目标。** 不得在 Kernel 重新实现 Hatchet 已提供的通用 Queue/DAG/Scheduler，也不能将 Hatchet Workflow History 作为平台 Run/Step/Attempt 权威。参见 [Hatchet 架构边界](docs/references/HATCHET_PROCESS_DURABLE_ARCHITECTURE_20261010.md)。

# 4. 架构讨论工作流

架构问题统一进入：

`docs/ARCHITECTURE_BACKLOG.md`

状态流转：

~~~text
TODO
→ DISCUSSING
→ DECIDED / POC
→ CLOSED
~~~

当一个架构待办形成明确结论后，必须同时完成：

1. 新增或更新对应专题 Contract / Reference。
2. 更新 `docs/ARCHITECTURE.md`。
3. 必要时更新 `docs/POC.md`。
4. 新增或更新 ADR 摘要。
5. 将 Backlog 条目更新为 CLOSED。
6. 更新 `docs/references/README.md` 索引。

未完成以上动作，不得口头宣称“架构已收口”。

# 3.1 公开扩展点优先原则

这是当前架构设计的重要参考点，适用于 MAF 以及后续所有 Runtime / Framework / Provider：

> **Framework 有公开扩展点（Public Extension Point）的，平台通过 Adapter 映射；Framework 不负责的基础设施能力放在平台外围；如果某项能力必须修改 Framework 内部实现才能获得，则不把该能力作为平台强制能力。**

必须遵守：

- 优先使用官方 Public API / SPI / Middleware / Provider / Hook / Adapter 等稳定扩展面。
- 平台可以统一领域语义和接口，但不得因此重写 Framework 内核。
- Framework 职责之外的 Sandbox、Network、Secret、Storage、IAM 等能力放在平台外围。
- 如果能力只能通过 fork、monkey patch、复制内部代码或依赖私有实现获得，则该能力应降级为 unsupported / optional，而不是反向要求平台补齐。
- POC 必须验证关键企业能力能否仅通过公开扩展点完成。
- 任何需要 Framework 内部改造的设计，必须视为架构风险，而不是默认实现路径。

# 4.1 架构边界控制

所有架构讨论、POC 和实现都必须控制职责边界，避免“顺手设计”导致平台膨胀。

必须遵守：

- 一个架构待办只解决自己的核心问题。
- 发现相邻问题时，先记录到 `docs/ARCHITECTURE_BACKLOG.md`，不要直接并入当前 Contract。
- 除非当前问题无法成立，否则不要为了未来可能性提前新增领域对象、控制平面职责或分布式协调机制。
- 能作为 Metadata 的，不先升级为强领域模型。
- 能由 Project Skill / Policy / Adapter 解决的，不写死进 Harness Kernel。
- 能由 Runtime / Provider 自己承担且不破坏平台契约的，不重复建设平台能力。
- 不把 Workspace、E2E Environment、Runtime Topology、Multi-Agent、Deployment、Release 等不同职责混成一个模型。
- 新增抽象前必须回答：它是否有稳定生命周期、独立状态、独立行为、跨实现价值；如果没有，优先保持轻量。
- 架构设计优先保证边界清晰、可替换、可验证，而不是追求“一次设计覆盖所有场景”。

当讨论出现明显发散时：

~~~text
当前议题继续收敛
+
新问题登记 Backlog
+
后续单独讨论
~~~

禁止因为当前讨论方便而跨边界提前实现后续待办。

# 4.2 Harness Platform 职责边界

本项目只建设 Agent Harness Platform，不以“大包大揽”的方式复制企业已有治理与基础设施平台。

进入任何架构议题前，必须先回答：

> 这个问题是否直接属于 Harness 的任务编排、执行控制、状态/恢复、协议、能力装配或 Adapter 边界？

如果答案是否定的，应优先定义 Ownership Boundary 并交给外部系统，而不是在 Harness 内新增领域模型或服务。

Harness 核心职责聚焦于：

- Run / Plan / Step / Attempt / Execution 生命周期与状态；
- Plan → Execute → Verify → Replan；
- Runtime / Model / Tool / Sandbox / Storage 等 Adapter 与 Capability 装配；
- Policy / Approval 在执行边界上的应用；
- Failure / Retry / Recovery / Reconciliation；
- Artifact / Evidence / Event / Lineage；
- 协议转换、版本冻结、可观测关联与执行正确性。

默认不属于 Harness 的能力包括但不限于：

- 企业 IAM / SSO / User Directory；
- MCP Governance / Marketplace；
- Cost / Quota / Billing / Chargeback；
- OCI/SBOM/镜像供应链安全平台；
- PostgreSQL/MSSQL/Object Storage/磁盘 Backup/DR；
- Prometheus/Grafana/Loki/APM/Alerting 产品；
- Secret Manager、DLP、SIEM 等独立企业基础设施产品。

对这些外围能力，Harness 只定义必要的 Adapter、Reference、Metadata、Policy/Admission input 或结果消费边界。

禁止因为“平台可能用得到”就把外围能力提升为 Harness 自己的领域职责。

# 5. 术语规范

架构文档优先采用：

> **中文术语在前，英文标识括号保留。**

例如：

- 执行实例（Run）
- 计划步骤（Step）
- 执行尝试（Attempt）
- 执行动作（Execution）
- 工作空间（Workspace）
- 恢复点（RecoveryPoint）
- 执行结果（Execution Outcome）
- 失败分类（Failure Classification）
- 副作用语义（Side Effect Semantics）
- 状态核对（Reconciliation）
- 幂等键（Idempotency Key）
- 栅栏令牌（Fencing Token）
- 副作用回执（Side Effect Receipt）

代码、Schema、API 字段保持稳定英文命名；设计说明和评审文本使用中英双语术语。

禁止同一个概念在不同文档中随意换名。

# 6. 领域模型原则

当前已接受的 V1 领域关系：

~~~text
Conversation
  └─ Turn [1..N]
       └─ Run [1..N]
            ├─ Plan [v1..N]
            │    └─ Step [1..N]
            │         └─ Attempt [1..N]
            ├─ RecoveryPoint [0..N]
            ├─ Artifact / Evidence
            └─ Terminal Result
~~~

必须遵守：

- Turn : Run = 1 : N。
- Plan 必须版本化，Replan 不覆盖历史。
- Step 与 Attempt 严格分离。
- terminal Run 永不 reopen。
- Workspace、Sandbox、Runtime Session 均不等同于 Run。
- 平台核心 ID 由平台生成。
- Provider / Framework 原生 ID 只能作为 binding / metadata。

详见：

`docs/references/DOMAIN_MODEL_AND_STATE_CONTRACT.md`

# 7. 失败、重试与副作用原则

必须遵守：

~~~text
执行结果（Outcome）
≠
失败分类（Failure Type）
≠
副作用类型（Side Effect Class）
~~~

硬规则：

- UNKNOWN（执行结果未知）禁止盲目重试。
- UNKNOWN 必须先进入状态核对（Reconciliation）。
- Retry = 同一个 Step 意图下的新 Attempt。
- Replan = 当前方案需要改变。
- 所有非 PURE 执行必须声明 Side Effect Contract。
- 所有非 PURE 执行应形成 Side Effect Receipt。
- 高风险副作用无法确认结果时，进入人工介入或 Fail Safe。
- 不承诺任意外部副作用 Exactly Once Execution。

详见：

`docs/references/FAILURE_IDEMPOTENCY_AND_RECOVERY.md`

# 8. Control Plane / Data Plane 原则

Control Plane 负责：

- Run / Plan / Step 状态机
- Retry / Replan / Abort / Complete
- Policy / Approval
- Recovery / Checkpoint
- 调度决策

Data Plane 负责：

- Model 调用
- Agent Runtime
- Shell
- Git
- Filesystem
- Browser
- MCP
- Sandbox
- Code Execution

禁止：

- Harness Kernel 直接运行 shell/git/browser 副作用。
- Sandbox/Executor 自行决定整个 Run 的最终业务状态。
- Agent 绕过 Policy / Approval 修改业务目标或扩大权限。

# 9. Coding Execution 与 Sandbox

生产 Coding Execution 默认进入隔离 Sandbox。

当前架构方向：

~~~text
ExecutionScheduler
        ↓
CubeSandboxProvider
      /               \
Local Cube Cluster   Remote Cube Cluster
~~~

约束：

- Local Cube = baseline capacity。
- Remote Cube = burst capacity。
- Docker = dev / compatibility / fallback。
- Hyperlight = specialized untrusted function/WASM execution。
- E2B 不作为独立生产 Provider；只保留 CubeSandbox 的 E2B-compatible API/SDK 兼容价值。
- 裸 LocalShell 不作为生产默认路径。

Sandbox Infrastructure Control Plane 不拥有 Harness Workflow。

# 10. 执行环境一致性

Local / Remote CubeSandbox 必须遵守统一 Execution Environment Contract。

环境版本必须通过：

- Environment Profile
- immutable OCI digest
- Environment Registry
- conformance test
- execution environment fingerprint

建立可追踪关系。

禁止生产 Run 使用不可追踪的 `latest` 环境漂移。

基础工具进入 Environment Image；项目依赖进入 Workspace。

# 10.1 运行时拓扑边界

必须遵守：

- Runtime Topology 是运行时事实记录，不是 Plan / Workflow / Scheduler。
- Sandbox、MCP Server 等基础设施对象可以作为 Participant。
- Topology 只记录参与者身份、生命周期和稳定关系。
- 高频 Tool / Shell / MCP 调用进入 Trace / Log，不进入 Topology。
- 不在 Topology 中重建业务状态机、调度器或 Multi-Agent 协商机制。
- Retention 周期由独立待办统一定义。

详见：

`docs/references/RUNTIME_TOPOLOGY.md`

# 10.2 恢复能力边界

必须遵守：

- 平台拥有恢复点（RecoveryPoint）领域模型，但不重新实现 Runtime Checkpoint Engine。
- Runtime Checkpoint 对平台必须保持 Opaque，通过 Runtime Adapter 引用和恢复。
- Runtime / Workspace / Sandbox 必须显式声明真实恢复 Capability。
- 底层 Framework / Provider 不支持的能力，平台不得通过 fork、monkey patch 或复制内部实现补齐。
- 平台只做轻量恢复协调，不建立跨组件 2PC 或新的分布式恢复协议。
- Sandbox Snapshot 是可选 Provider 能力，不是 RecoveryPoint 的统一硬依赖。
- 外部副作用恢复继续遵守副作用回执与状态核对契约。

详见：

`docs/references/CHECKPOINT_AND_SNAPSHOT_CONSISTENCY.md`

# 10.3 安全隔离边界

必须遵守：

- Repository、Web、Model Output，以及 Tool/MCP 返回的外部业务内容默认不能提升为高信任指令；Tool/MCP Server 是否准入由外部 Governance 负责，平台可调用即视为已治理准入。
- Instruction 与 Data 必须分层，低信任内容不得自行升级为高信任指令。
- Data Plane 只产生 Result / Evidence / Artifact / Event / Failure，不拥有 Run/Step 最终状态控制权。
- Secret 默认不直接进入模型上下文；Secret/Network enforcement 由外部 Credential/Network/Sandbox 基础设施负责，Harness 只表达当前 Execution 的 Capability / Policy 约束并消费结果。
- 单一 Sandbox / Agent Runtime / Tool Runtime 被攻破，不应天然获得 Control Plane 或全局组织/其他项目权限。
- 安全能力优先通过 Framework 公开扩展点映射；Framework 外能力放平台外围；需要侵入式修改 Framework 的能力不进入强制基线。

详见：

`docs/references/SECURITY_THREAT_MODEL.md`

# 10.4 版本冻结边界

必须遵守：

- V1 不为了版本管理建设统一 Registry 服务。
- Recipe、Component/Adapter、Runtime、Policy、Tool、Protocol、Environment 等必须有可识别版本。
- Run 创建时必须解析为确定版本并冻结，运行中不得静默漂移或热升级。
- latest/default 只能用于解析前配置，不能作为 Run 最终绑定。
- 新版本只影响新 Run；恢复已有 Run 时继续使用其冻结版本信息。
- Capability Requirement 在 Run 开始前匹配；不支持即拒绝，不通过侵入式修改 Framework 补齐。
- Registry 是逻辑版本目录能力，不等同于微服务注册中心或动态服务发现。

详见：

`docs/references/REGISTRY_AND_VERSIONING.md`

# 10.5 Execution Ownership 边界

必须遵守：

- Lease / Fencing 只治理平台自有 ExecutionScheduler → Executor 边界，不接管 Framework / Durable Engine / Sandbox Infrastructure 内部 Worker ownership。
- Lease 表示当前 Execution 执行资格；Heartbeat 只负责活性与续租。
- Fencing Token 随 ownership epoch 单调递增，旧 token 永久失效。
- stale Worker 不得更新 Execution、提交最终结果或申请新的平台控制副作用。
- RUNNING Execution 丢失 Lease 后不得 blind handoff；结果不确定必须进入 UNKNOWN → Reconciliation。
- Fencing 不能替代 idempotency、Side Effect Contract 或 Reconciliation。
- V1 优先使用已有权威状态存储实现原子 claim / renew / fencing，不新增独立分布式锁基础设施。

详见：

docs/references/EXECUTION_LEASE_FENCING_HEARTBEAT.md

# 10.6 Identity / Authorization 边界

必须遵守：

- V1 以企业内部单组织信任域为基线，不为了未来 SaaS 可能性提前引入 Tenant 一等领域模型。
- Authentication 由企业 IdP / IAM 负责，Harness 不自建账号、SSO、目录或完整 IAM。
- 发起者（Initiator）身份与执行者（Executor / Service Principal）身份必须分离并可审计。
- Run 固化 Initiator Identity，但敏感 Execution 必须按当前有效权限重新授权。
- RBAC / ABAC / Group / Claim 只作为 Policy 输入，Harness 拥有 Authorization Decision，不复制企业 IAM。
- 用户长期 Token / Secret 默认不得传播到 Agent、Model、Sandbox。
- 外部访问通过 Credential Provider Adapter 对接企业现有 Credential/Secret Infrastructure，获取当前 Execution 所需的短期、最小权限、资源范围明确的 Credential；Harness 不拥有 Credential 生命周期。
- Approval 必须绑定真实 Principal / Resource / Action / Policy；Agent / Worker / Sandbox 不得自行伪造 Approval。
- Repository 权限不得因 Project Manifest 存在而自动获得；通过 Policy + Provider Credential 组合授权。

详见：

docs/references/IDENTITY_AND_AUTHORIZATION_PROPAGATION.md

# 10.7 Task Recovery 边界

必须遵守：

- 平台持久化任务执行事实与底层 Recovery Reference，不复制 Runtime 内部 checkpoint/history。
- WAITING_INPUT / WAITING_APPROVAL 必须恢复同一个 Run 的等待状态。
- 无可用 Runtime checkpoint 时，只能恢复到可证明安全的 Step Boundary，并创建 New Attempt。
- 有真实 checkpoint/resume 能力时，允许 Same Run + Same Step + Same Attempt Resume；Resume 不得记作 Retry。
- Runtime State、Workspace State、Sandbox State 独立；Sandbox 实例不是任务恢复硬依赖。
- RUNNING Execution 故障后不得 blind resume/retry；结果不确定必须进入 UNKNOWN → Reconciliation。
- 恢复优先选择最深且安全的恢复点，不默认从整个 Run 起点重跑。
- 数据库、磁盘、对象存储、K8s/Region Backup/DR 不属于 Harness Task Recovery 责任。

详见：

docs/references/TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md

# 10.8 Artifact / Evidence Retention 边界

必须遵守：

- Task Facts 与 Payload 分离；Artifact / Evidence 大 Payload 默认进入 OSS / Object Storage，平台数据库保留 metadata / lineage / digest / storage reference。
- Raw Log / Trace 默认短期保留，不自动视为长期 Evidence。
- 被 Verification / Reconciliation / Audit 明确引用的日志内容必须提升为 Evidence 或形成稳定 Evidence Reference。
- Artifact / Evidence 是逻辑身份；物理 Payload 可以去重，但不能合并逻辑 Lineage。
- Recoverable Run 仍依赖的 checkpoint、workspace state、Evidence、snapshot reference 不得被 GC。
- Payload 清理后保留最小 Metadata/Tombstone，使历史任务仍可解释。
- Retention 时间由 Policy / 部署配置决定，禁止在 Harness Kernel 写死固定天数。
- Workspace / Sandbox Snapshot 的生命周期由对应 Contract / Provider 管理，本层只定义引用与 GC 约束。

详见：

docs/references/ARTIFACT_EVIDENCE_LOG_RETENTION.md

# 10.9 Observability 边界

必须遵守：

- Event、Trace/Span、Log、Metric 严格分离；Observability signals 不得成为 Run/Step 最终业务状态事实源。
- Runtime / Framework 原生 OpenTelemetry instrumentation 优先复用；Harness 只补平台自有边界与统一 correlation。
- Run : Trace = 1:N；跨 Trace 使用 harness.run.id 关联，不强制长任务维持单一 trace_id。
- Trace / Log 在适用时关联 run_id / step_id / attempt_id / execution_id / participant_id；Provider 原生 ID 只作为 metadata。
- run_id / execution_id / user_id 等高基数值不得作为默认 Metric label。
- 普通成功 Trace/Log 可采样；ERROR / UNKNOWN / Recovery / Reconciliation / Approval / Verification Failure 等关键诊断路径优先保留；Business Event 不受 sampling 影响。
- Prompt / Response / Tool Payload / Repository Content 默认不进入普通 telemetry；敏感 telemetry 必须显式 Policy opt-in。
- Runtime 原生能观测到的 telemetry 尽量保留，不为了表面统一而丢弃；Provider-specific semantic conventions 留在 Adapter/telemetry boundary。
- Harness 不自建 Prometheus / Grafana / Loki / APM / Alerting 产品。

详见：

docs/references/OBSERVABILITY_CONTRACT.md

# 10.10 Cost / Quota Ownership 边界

必须遵守：

- Cost、Quota、Billing、Chargeback、Showback 与资源额度账户不属于 Harness Platform 核心职责。
- Harness 不维护模型价格表、余额、额度账户、账本、订阅套餐或财务归属。
- Runtime 原生 token / duration / resource usage 可以作为 Observability telemetry，但不得因此形成 Cost Domain。
- 外部 Portal / Governance 系统可以做 entitlement / quota decision；Harness 只通过 Policy / Admission boundary 消费允许/拒绝结果，不拥有 quota state。
- max_iterations / max_replans / timeout / max_runtime 等属于 Execution Limits，只用于单次 Run 的运行安全，不属于 Quota/Budget。
- 未来若要建设正式计费或额度产品，必须独立立项，不得从 Harness Domain 隐式扩张。

详见：

docs/references/COST_QUOTA_OWNERSHIP_BOUNDARY.md

# 10.11 Environment Supply Chain Ownership 边界

必须遵守：

- OCI provenance、SBOM、镜像签名、漏洞扫描、供应链证明不由 Harness Platform 实现。
- 这些能力由企业 CI/CD、Artifact Registry、Container Security / Supply Chain Security 基础设施负责。
- Harness 只消费 Environment Profile/version、immutable digest、capability、verification status 与可选 external attestation reference。
- Run / Execution 仍必须冻结并记录实际 Environment version / digest。
- 不得因为外部安全平台不存在就把 SBOM/扫描/签名引擎重新实现进 Harness Kernel。

详见：

docs/references/ENVIRONMENT_SUPPLY_CHAIN_OWNERSHIP_BOUNDARY.md

# 10.12 MCP Trust Ownership 边界

必须遵守：

- MCP Server / Tool 的准入、可信度、安全审查、发布、升级、撤销与下线由外部 MCP Governance / Enterprise Tool Governance 负责。
- Harness 可调用到的 MCP 默认视为已经治理准入，不建立 Trust Score、Risk Level、Marketplace Approval 或二次审核模型。
- Harness 仍负责具体 Execution 的 Capability / Policy / Approval / Credential / SideEffect / Audit 与版本绑定。
- MCP 返回的业务数据仍遵守统一 Instruction / Data 隔离规则，不自动获得 Platform/System Instruction 权限。
- 不得把 MCP Governance 产品能力重新实现进 Harness Kernel。

详见：

docs/references/MCP_TRUST_OWNERSHIP_BOUNDARY.md

# 10.13 Cancellation / Timeout 边界

必须遵守：

- Cancel Request 不等于 CANCELLED；活动执行先进入 CANCELLING。
- Cancel 沿 Run → Step/Attempt → active Execution → Runtime/Tool/MCP/Sandbox Adapter 传播；未开始工作停止 dispatch。
- 优先 graceful cancel；只有 Provider 明确支持时才可升级 force terminate。
- ACKNOWLEDGED 只表示收到信号，TERMINATED 才能证明下游停止。
- Timeout 是 Failure Type / termination cause，不是 CANCELLED 的别名。
- 已 dispatch 的非 PURE Execution 在 Cancel/Timeout 后结果不确定时必须 UNKNOWN → Reconciliation。
- Cancellation 不做隐式 rollback，不删除 Workspace / Artifact / Evidence / SideEffect 历史。
- Provider 不支持 cancel 时显式 unsupported，不 fork / patch Framework。

详见：

docs/references/CANCELLATION_TIMEOUT_PROPAGATION.md

# 11. POC 原则

POC 必须：

- 使用相同业务任务和 Acceptance Criteria。
- Measure First。
- 通过故障注入验证恢复能力。
- 明确 PASS / FAIL / Gap。
- 区分厂商官方事实、讨论估算、实测数据。
- 不把 README benchmark 当生产 SLA。
- 不通过放宽门禁、skip、retry、降低 coverage 获得“通过”。

POC 结论必须给出可重复证据。

# 12. 外部事实核验

涉及以下内容时，必须使用最新官方资料或源码核验，不能仅依赖模型记忆：

- Framework 当前 API
- prerelease / stable 状态
- License
- self-host / cloud 边界
- 扩展点
- Sandbox 能力
- Provider 限制
- 性能数字
- 商业功能断层

优先级：

~~~text
官方源码 / 官方文档
> 官方 changelog / release
> 官方 issue / ADR
> 第三方资料
~~~

讨论估算必须明确标识“估算”，不得伪装成 benchmark。

# 13. 文档与代码变更纪律

修改前：

1. 阅读相关 AGENTS 与现有 Contract。
2. 查找已有实现/文档，禁止重复造概念。
3. 明确本次变更属于 Decision、POC、实现还是修复。

修改中：

- 保持改动聚焦。
- 不顺手重构无关模块。
- 不删除历史 Decision / Evidence 来让新设计“看起来一致”。
- 发现架构冲突时先记录 Backlog，不偷偷绕开。
- Provider-specific 逻辑必须留在 Adapter 边界。

修改后：

- 更新相关文档。
- 补 Contract / Unit / Integration / E2E 测试。
- 运行与变更范围匹配的验证。
- 输出已验证内容和未验证风险。

# 14. 测试与 Correctness

优先级：

~~~text
Correctness
> Recoverability
> Security
> Compatibility
> Performance
> Convenience
~~~

禁止通过以下方式掩盖失败：

- skip 关键测试
- 无依据增加 retry
- 单纯延长 timeout
- 删除断言
- 减少关键平台覆盖
- 忽略 flaky 根因
- 用 Agent 自我声明替代真实 Evidence

所有副作用、恢复、重试相关逻辑必须优先测试异常路径，而不只测试 happy path。

# 15. Git 与提交原则

- 不覆盖已经接受的历史架构决策，应通过新 Decision/ADR 修订。
- 文档与实现提交信息应说明真实意图。
- 不把无关格式化、大规模重排与架构改动混在同一提交。
- 任何 Provider 替换必须证明上层 Domain Model / Workflow 不需要修改。
- 高风险 git.push / merge 等动作必须遵守 Policy / Approval。
- Git Server 是权威主干事实源；Repository Mirror / Cache 只能作为可重建缓存。
- Project Repository 通过静态 Project Manifest 定义项目仓库边界，并承载项目级 AGENTS.md / Skills / 公共规范。
- Project Workspace 可跨 Turn / Run 复用，但 Run 必须冻结自己的 Repository Revision Set。
- Worktree 按 Git Repository 粒度隔离；并发可写 Run / 子 Agent 默认不得共享同一 Worktree。
- 执行过程中不得隐式 rebase/merge 追主干；集成前显式同步 upstream 并重新 Verify。
- 本地 commit 可按 Recipe/Policy 自动执行；push/merge/tag/delete branch/force-push 按外部副作用治理，force-push 默认禁止。
- 项目研发流程和跨仓执行顺序由项目级 Skill 定义，不写死在 Harness Kernel。
- 详见 `docs/references/WORKSPACE_AND_GIT_MODEL.md`。

# 16. 当前架构待办

所有未决问题以：

`docs/ARCHITECTURE_BACKLOG.md`

为唯一主清单。

不要在其他文档维护第二份互相漂移的 TODO 总表。

# 17. 工作完成定义

一个任务只有同时满足以下条件才可宣称完成：

- 范围内实现/文档已更新。
- 相关架构约束未被破坏。
- 必要测试已执行并通过。
- 失败/Gap 已明确记录。
- 重要 Decision 已沉淀。
- 没有把“未验证”描述成“已验证”。
- 没有把“讨论建议”描述成“正式架构决策”。

如果无法完全完成，应明确说明已完成部分、剩余风险与阻塞点，不得伪造收口。