# Agent Harness Platform 架构待办

| 项目 | 内容 |
|---|---|
| 文档状态 | Active Architecture Backlog |
| 创建日期 | 2026-09-29 |
| 适用范围 | Agent Harness Platform |
| 使用方式 | 一项一项讨论、形成结论、更新正式架构/ADR 后关闭 |

> 本文件只记录**尚未完成的架构问题**，不代表已接受方案。  
> 每个待办在讨论完成后，应形成明确 Decision / ADR / Contract，并同步更新 `docs/ARCHITECTURE.md`、`docs/POC.md` 或对应专题文档。

# 1. 状态定义

| 状态 | 含义 |
|---|---|
| TODO | 尚未开始正式讨论 |
| DISCUSSING | 正在讨论，尚未形成决策 |
| DECIDED | 已形成架构决策，等待同步正式文档 |
| POC | 已形成方向，但需要 POC/实测确认 |
| CLOSED | 已进入正式架构/ADR，并满足完成条件 |
| DEFERRED | 当前阶段明确延后 |

# 2. P0：进入正式实现前必须讨论清楚

## ARCH-TODO-001 Domain Model & State Contract

**状态：CLOSED**

**Decision：** 已冻结 Conversation → Turn → Run → Plan/Step/Attempt 的 V1 领域关系；Turn:Run=1:N；Plan 版本化；Step/Attempt 分离；terminal Run never reopen；Provider ID 仅为 binding/metadata。

**产出：** [DOMAIN_MODEL_AND_STATE_CONTRACT.md](references/DOMAIN_MODEL_AND_STATE_CONTRACT.md)

### 问题

当前已经定义 Conversation、Turn、Run、Plan、Step、Attempt、Event、Artifact、Evidence、Approval、ExecutionRequest、ExecutionResult 等核心概念，但尚未形成统一、版本化、可实现的数据模型。

### 需要讨论

- 对象之间的 ownership 与 cardinality。
- ID 生成边界：平台 ID 与 Provider ID。
- immutable / mutable 字段。
- Plan version / Step version / Attempt 的关系。
- Run / Session / Workspace / Sandbox 的生命周期关系。
- Event sequence 与状态重建。
- schema version 与兼容策略。
- Command 与 Event 的边界。
- 状态落库模型和最小事务边界。

### 预期产出

`docs/references/DOMAIN_MODEL_AND_STATE_CONTRACT.md`

并在正式架构中冻结 V1 核心对象关系。

### 完成条件

- MAF / Temporal / ADK Adapter 均能映射到同一领域模型。
- UI、Event Store、Persistence、Execution Plane 不再各自定义 Run/Step 语义。
- 可以仅凭持久化状态与 Event 明确恢复任意 Run。

---

## ARCH-TODO-002 Failure / Idempotency / Side Effect Contract

**状态：CLOSED**

**Decision：** 已冻结执行结果（Outcome）、失败分类（Failure Classification）、副作用类型（Side Effect Class）与恢复决策（Recovery Decision）四层语义；UNKNOWN 禁止盲目重试；Retry 与 Replan 严格分离；所有非 PURE 执行必须声明副作用契约并形成副作用回执；高风险未知结果默认进入人工介入或 Fail Safe。

**产出：** [FAILURE_IDEMPOTENCY_AND_RECOVERY.md](references/FAILURE_IDEMPOTENCY_AND_RECOVERY.md)

### 问题

当前已有 Retry、Replan、Recovery、FailureClassifier、idempotency_key 等概念，但尚未定义副作用操作的统一失败语义。

### 需要讨论

Execution 状态至少需要区分：

- NOT_STARTED
- STARTED
- SUCCEEDED
- FAILED
- TIMED_OUT
- CANCELLED
- UNKNOWN

Side Effect 至少需要讨论：

- PURE
- IDEMPOTENT
- RETRY_SAFE
- VERIFY_BEFORE_RETRY
- COMPENSATABLE
- NON_RETRYABLE

重点解决：

- 网络断开后无法判断 git push / deploy / delete 是否已经成功。
- infrastructure retry 与 business retry/replan 的边界。
- duplicate execution 防护。
- compensation / verification-before-retry。
- attempt fencing 与旧 Worker 回归问题。

### 预期产出

`docs/references/FAILURE_IDEMPOTENCY_AND_RECOVERY.md`

### 完成条件

- 每类 Tool/Execution 都能声明 retry semantics。
- UNKNOWN 状态有明确处理策略。
- 任何有副作用操作都不能仅依赖“再执行一次”恢复。
- Retry / Replan / Compensation / Human Intervention 边界明确。

---

## ARCH-TODO-003 Workspace / Repository / Git Model

**状态：CLOSED**

**Decision：** 已冻结 Project Repository → Project Workspace → Repository Workspace → Worktree 的分层；Project Manifest 静态定义项目仓库边界；Workspace 可跨 Turn/Run 复用；Run 冻结 Repository Revision Set；主干以 Git Server 为唯一权威；执行期间不隐式追主干，集成前显式刷新并重新验证；允许本地自动 commit，push/merge 等进入 Policy 与副作用契约；多仓 Revision Set 仅记录，不构建跨仓事务；项目研发流程由 Skill 定义。

**产出：** [WORKSPACE_AND_GIT_MODEL.md](references/WORKSPACE_AND_GIT_MODEL.md)

### 问题

Coding Harness 的真实工作载体是 Workspace，而不是 Sandbox。当前 Workspace、Repository、Worktree、Branch、Sandbox Binding 尚未形成正式模型。

### 需要讨论

- Workspace 与 Run / Session / Sandbox 的关系。
- Repo clone / mirror / checkout / worktree。
- base revision / branch / detached HEAD。
- dirty state / untracked files。
- concurrent run 对同一 repo 的隔离。
- commit / merge / push 权限。
- git credential 注入。
- Sandbox 被销毁后 Workspace 如何继续。
- persistent volume / snapshot / artifact 的区别。
- Workspace cleanup / retention。
- dependency cache 与 repo cache。

### 建议原则待验证

~~~text
Run ≠ Workspace
Session ≠ Workspace
Sandbox ≠ Workspace
~~~

### 预期产出

`docs/references/WORKSPACE_AND_GIT_MODEL.md`

### 完成条件

- Sandbox 可以销毁/迁移而 Workspace 生命周期不混乱。
- 并发 Coding Run 不会互相污染。
- git push / merge 等高风险副作用有明确 Policy / Approval 边界。
- Workspace 可以被恢复、审计和清理。

---

## ARCH-TODO-004 Runtime Topology / Participant Model

**状态：CLOSED**

**Decision：** 已冻结 Runtime Topology 为运行时事实模型，不承担 Plan/Workflow/Scheduler 职责；Sandbox、MCP Server 等基础设施对象作为 Participant 进入拓扑；仅记录身份、生命周期和稳定关系，不记录高频调用明细；具体 Retention Policy 留给 ARCH-TODO-011。

**产出：** [RUNTIME_TOPOLOGY.md](references/RUNTIME_TOPOLOGY.md)

### 问题

当前 Workflow Graph 描述“设计时流程”，但缺少运行时参与者拓扑。实际 Run 可能同时包含 MAF Workflow、Coding Executor、Codex/OpenCode、CubeSandbox、MCP Server、Verifier、Remote Agent、Browser Worker 等。

### 需要讨论

运行时节点类型：

- Run
- Workflow
- Executor
- Agent
- Subagent
- Sandbox
- Tool Runtime
- MCP Server
- Remote Agent
- Component

关系至少包括：

- OWNS
- SPAWNS
- CALLS
- RUNS_ON
- DEPENDS_ON
- HANDOFF_TO
- ROUTES_TO
- PROVIDES

同时讨论：

- Runtime Registry。
- participant lifecycle。
- dynamic join/leave。
- control routing。
- cancel propagation。
- topology 与 tracing / cost / audit 的关系。
- Design-time Graph 与 Runtime Topology 的分离。

### 预期产出

`docs/references/RUNTIME_TOPOLOGY.md`

### 完成条件

- 能解释一个 Run 当前有哪些参与者、在哪里运行、谁拥有谁。
- Cancel / Failure / Cost / Trace 可以关联到具体 participant。
- 不依赖某个 Agent Framework 自带的 graph 模型。

---

## ARCH-TODO-005 Harness Checkpoint / Sandbox Snapshot Consistency

**状态：CLOSED**

**Decision：** 已冻结轻量恢复隔离模型：平台只拥有恢复点（RecoveryPoint）与恢复能力契约（Recovery Capability）；Runtime Checkpoint、Workspace Restore、Sandbox Snapshot 均由对应 Adapter/Provider 实现；runtime checkpoint 对平台保持 Opaque；不支持的能力显式声明为不支持，平台不模拟、不 fork、不 patch，也不建立跨组件分布式事务。

**产出：** [CHECKPOINT_AND_SNAPSHOT_CONSISTENCY.md](references/CHECKPOINT_AND_SNAPSHOT_CONSISTENCY.md)

### 问题

平台已定义 Harness Checkpoint，CubeSandbox 又支持 Snapshot / Pause / Resume / Rollback，但尚未定义两类状态如何形成一致恢复点。

### 需要讨论

建议引入 RecoveryPoint：

~~~text
RecoveryPoint
├─ run_state_version
├─ plan_version
├─ step_id
├─ attempt_id
├─ event_sequence
├─ workspace_revision
├─ environment_fingerprint
├─ sandbox_snapshot_id
└─ created_at
~~~

需要明确：

- Harness 状态与 Sandbox snapshot 的 commit 顺序。
- 部分成功时如何回滚/补偿。
- Snapshot 创建失败怎么办。
- Sandbox 恢复成功但 Control Plane 恢复失败怎么办。
- snapshot 与 workspace persistent state 的边界。
- stale snapshot / orphan snapshot GC。
- recovery point versioning。

### 预期产出

`docs/references/CHECKPOINT_AND_SNAPSHOT_CONSISTENCY.md`

### 完成条件

- 不出现 Harness 与 Sandbox 状态 split-brain。
- 任一 RecoveryPoint 都可证明恢复到一致 Step/Workspace/Environment。
- 故障注入可以覆盖 checkpoint 各阶段。

---

## ARCH-TODO-006 Security Threat Model

**状态：CLOSED**

**Decision：** 已冻结轻量安全隔离模型：定义 Trust Boundary、默认不可信输入、Instruction/Data 分层、Control Plane/Data Plane 隔离与最小权限原则；MAF/Framework 能力仅通过公开扩展点映射，基础设施安全放平台外围；必须侵入式修改 Framework 才能获得的能力不进入平台强制基线。

**产出：** [SECURITY_THREAT_MODEL.md](references/SECURITY_THREAT_MODEL.md)

### 问题

当前已有 Sandbox、Policy、Approval、Secret、Network、Credential Injection，但缺少统一威胁模型和 Trust Boundary。

### 需要讨论

至少覆盖：

- malicious user
- malicious repository
- prompt injection
- malicious dependency / supply-chain attack
- malicious MCP server/tool
- compromised agent/runtime
- compromised sandbox
- compromised model/provider
- secret exfiltration
- lateral movement
- privilege escalation
- sandbox escape
- poisoned artifact / generated executable
- remote execution / data residency risk

对每类威胁定义：

~~~text
Threat
→ Trust Boundary
→ Prevent
→ Detect
→ Contain
→ Audit
→ Recover
~~~

### 预期产出

`docs/references/SECURITY_THREAT_MODEL.md`

### 完成条件

- 每个外部输入、执行主体和 secret 都有明确 trust level。
- Sandbox/network/policy/approval 不再只是分散能力，而能映射到具体威胁。
- POC 中存在对应攻击/故障测试。

# 3. P1：核心架构确定后必须补齐

## ARCH-TODO-007 Registry & Versioning

**状态：CLOSED**

**Decision：** V1 不建设统一 Registry 服务，只冻结版本目录与 Run 版本锁定语义：组件有可识别版本；Run 创建时解析为确定版本并冻结；latest 仅用于解析前配置；运行中的 Run 不热升级；Capability 在 Run 开始前匹配，不支持即拒绝，不通过侵入式修改 Framework 补齐。

**产出：** [REGISTRY_AND_VERSIONING.md](references/REGISTRY_AND_VERSIONING.md)

范围：

- Recipe Registry
- Component Registry
- Capability Registry
- Environment Registry
- Runtime Adapter version
- schema compatibility
- version freeze per Run
- upgrade / deprecation / rollback
- capability negotiation

预期产出：

`docs/references/REGISTRY_AND_VERSIONING.md`

---

## ARCH-TODO-008 Execution Lease / Fencing / Heartbeat

**状态：CLOSED**

**Decision：** Lease / Fencing 仅治理平台自有 Execution ownership：Lease 表示当前执行资格，Heartbeat 只负责活性与续租，Fencing Token 随 ownership epoch 单调递增并拒绝 stale Worker。RUNNING Execution 丢失 Lease 后不得 blind handoff；明确未执行才可重试，结果不确定必须进入 UNKNOWN → Reconciliation。Framework / Durable Engine / CubeSandbox 内部 Worker ownership 继续由各自实现负责。V1 优先使用现有权威状态存储做原子 claim / renew / fencing，不新增独立分布式锁基础设施。

**产出：** [EXECUTION_LEASE_FENCING_HEARTBEAT.md](references/EXECUTION_LEASE_FENCING_HEARTBEAT.md)

### 已确认的相邻约束

- MAF Python Durable 的生产私有化 backend 问题记录于 references/MAF_PYTHON_DURABLE_PRIVATE_DEPLOYMENT.md。
- 008 不为弥补 MAF/Durable Task backend 缺口而建设 Durable Scheduler、TaskHub backend 或 replay engine。
- Cancellation / Timeout 传播已由 ARCH-TODO-016 冻结，详见 CANCELLATION_TIMEOUT_PROPAGATION.md。

---

## ARCH-TODO-009 Identity & Authorization Propagation

**状态：CLOSED**

**Decision：** V1 以企业内部单组织信任域为基线，不引入 Tenant 一等领域模型。Authentication 由企业现有 IdP / IAM 负责；平台通过轻量 SecurityContext 保留 Initiator Identity，并将其与具体 Execution 的 Executor / Service Identity 分离。RBAC / ABAC / Group / Claim 作为 Policy 输入，平台只拥有 Authorization Decision。用户长期登录 Token / Secret 不向 Agent / Model / Sandbox 传播；外部访问通过 Credential Provider 获取短期、最小权限凭据。Run 固化 Initiator 作为审计事实，但敏感 Execution 必须按当前有效权限重新授权。

**产出：** [IDENTITY_AND_AUTHORIZATION_PROPAGATION.md](references/IDENTITY_AND_AUTHORIZATION_PROPAGATION.md)

### 边界

- 不自建账号认证、SSO、User Directory、SCIM 或完整 IAM。
- 不建设 Tenant / Organization Partition；未来确有多组织共享需求时单独立项。
- 不复制 Repository Provider ACL；通过 Policy + scoped credential 组合授权。
- Agent / Worker / Sandbox 不能自行伪造 Approval。
- Secret 产品与生命周期、DLP、Tool/MCP Trust、Network Policy 继续由独立专题处理。

---

## ARCH-TODO-010 Task Recovery Coverage & Recovery Semantics

**状态：CLOSED**

**Decision：** 平台任务恢复只依赖“持久化业务执行事实 + 底层 Recovery Reference”，不复制 Runtime 内部 checkpoint。WAITING_INPUT / WAITING_APPROVAL 必须恢复同一个 Run；无 Runtime checkpoint 时最多恢复到安全 Step Boundary 并创建 New Attempt；具备真实 checkpoint/resume 能力时允许 Same Run + Same Step + Same Attempt Resume。Runtime State、Workspace State、Sandbox State 独立治理，Sandbox 实例不是恢复硬依赖。RUNNING Execution 结果不确定时必须进入 UNKNOWN → Reconciliation，不得 blind resume/retry。数据库/磁盘/集群 Backup 与 DR 不属于本契约。

**产出：** [TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md](references/TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md)

### 恢复降级顺序

~~~text
Same Attempt Resume
        ↓ unavailable / incompatible
Same Step + New Attempt
        ↓ unsafe
UNKNOWN → Reconciliation
        ↓ cannot safely continue
Fail / Wait Human
~~~

---

## ARCH-TODO-011 Artifact / Evidence / Log Retention

**状态：CLOSED**

**Decision：** Task Facts 与 Payload 分离。Artifact / Evidence 的文件、报告、截图、大日志等 Payload 默认进入 OSS / Object Storage；平台数据库只保存 metadata、lineage、content digest、retention policy 与 storage reference。Raw Log / Trace 默认短期保留，只有被明确提升或引用的内容进入 Evidence 生命周期。Recoverable Run 所依赖的 checkpoint、workspace state、evidence、snapshot reference 必须 PIN，不得被 GC。Payload 清理后保留 Tombstone/Metadata，历史 Verification、Recovery 与 Audit Lineage 不能断裂。Retention 时长由 Policy / 部署配置决定，不在 Harness Kernel 写死。

**产出：** [ARTIFACT_EVIDENCE_LOG_RETENTION.md](references/ARTIFACT_EVIDENCE_LOG_RETENTION.md)

### 边界

- Object Storage 是 Artifact / Evidence Payload Store，不替代平台任务事实数据库。
- Workspace 与 Sandbox Snapshot 生命周期仍由对应 Contract / Provider 管理。
- 不建设通用日志平台、Legal Hold/eDiscovery 或对象存储生命周期产品。

---

## ARCH-TODO-012 Observability Contract

**状态：CLOSED**

**Decision：** OpenTelemetry 作为 vendor-neutral telemetry baseline；Runtime / Framework 原生 OTel instrumentation 优先复用，Harness 只补 Control Plane / Scheduler / Policy / Recovery / Verification 等平台边界和统一 correlation。Event、Trace/Span、Log、Metric 严格分离；Run:Trace=1:N；run_id / step_id / attempt_id / execution_id / participant_id 用于 Trace/Log correlation，高基数 ID 不进入默认 Metric labels。普通成功链路允许采样，ERROR / UNKNOWN / Recovery / Reconciliation / Approval / Verification Failure 等关键路径优先保留。Prompt / Response / Tool Payload / Repository Content 默认不进入普通 telemetry。

**产出：** [OBSERVABILITY_CONTRACT.md](references/OBSERVABILITY_CONTRACT.md)

### 边界

- Observability signals 不拥有 Run / Step 最终业务状态。
- MAF 原生 traces / logs / metrics 直接接入，不重复包同等粒度埋点。
- Cost / Quota / Chargeback 已由 ARCH-TODO-013 明确为 Harness 外部治理职责。
- 不建设 Prometheus/Grafana/Loki/APM/Alerting 产品。

---

## ARCH-TODO-013 Cost / Quota Ownership Boundary

**状态：CLOSED**

**Decision：** Cost、Quota、Billing、Chargeback、Showback 与资源额度账户明确不属于 Harness Platform 核心职责。Harness 不维护价格表、余额、额度、账本或财务归属。Runtime 原生 token / duration / resource usage 仅作为 Observability telemetry。若上层 Portal / Governance 系统需要额度控制，可在 Policy / Admission boundary 前后传递允许/拒绝结果，但 Harness 不拥有 quota state。max_iterations / max_replans / timeout 等只属于单次 Run 的 Execution Limits，不构成 Quota/Budget Domain。

**产出：** [COST_QUOTA_OWNERSHIP_BOUNDARY.md](references/COST_QUOTA_OWNERSHIP_BOUNDARY.md)

---

## ARCH-TODO-014 Environment Supply Chain Security

**状态：CLOSED**

**Decision：** 本专题不由 Harness Platform 处理。OCI provenance、SBOM、image signing、signature verification、vulnerability scanning、base image/dependency policy、template promotion security gate 等属于企业 CI/CD、Artifact Registry、Container Security / Supply Chain Security 基础设施职责。

Harness 只消费已准备好的 Environment Profile、immutable OCI digest、capability、verification status 等环境元数据，并在 Run / Execution 中冻结和记录实际使用的 environment version / digest。

明确不建设：

- image signing / signature verification service
- SBOM generation / storage
- vulnerability scanner
- image promotion security workflow
- base image / dependency governance product
- supply-chain attestation service

如果企业外部平台提供上述结果，Harness 可以把最终 verification / policy decision 当作 Environment metadata 或 admission input 使用，但不拥有其内部模型和生命周期。

---

## ARCH-TODO-015 MCP Trust Ownership Boundary

**状态：CLOSED**

**Decision：** MCP Server / Tool 的准入、可信度、安全审查、发布、升级、撤销与下线属于外部 MCP Governance / Enterprise Tool Governance；Harness 只消费已经被治理层准入的 MCP。只要平台可调用，就视为已通过外部治理，不再建立 MCP Trust Score、Server Risk Level、Marketplace Approval 或二次审核模型。

Harness 仍负责具体 Execution 的 Capability / Policy / Approval / Credential / SideEffect / Audit，以及 Tool/MCP version binding；MCP 返回的业务数据仍遵守统一 Instruction / Data 隔离规则，不自动获得 Platform/System Instruction 权限。

**产出：** [MCP_TRUST_OWNERSHIP_BOUNDARY.md](references/MCP_TRUST_OWNERSHIP_BOUNDARY.md)

---

## ARCH-TODO-016 Cancellation / Timeout Propagation

**状态：CLOSED**

**Decision：** Cancel Request 不等于 CANCELLED；活动执行先进入 CANCELLING，沿 Run → Step/Attempt → Execution → Runtime/Tool/MCP/Sandbox Adapter 传播。优先 graceful cancellation，Provider 支持时可在 grace period 后 force terminate。ACKNOWLEDGED 只表示收到信号，TERMINATED 才能证明停止。Timeout 是 Failure Type，不是取消终态；已经 dispatch 的非 PURE Execution 若结果未知，必须 UNKNOWN → Reconciliation。Cancellation 不做隐式 rollback，也不删除 Workspace/Artifact/Evidence/SideEffect 历史。Provider 不支持 cancel 时显式降级，不 fork/patch。

**产出：** [CANCELLATION_TIMEOUT_PROPAGATION.md](references/CANCELLATION_TIMEOUT_PROPAGATION.md)

---

# 4. P2：明确延后但需要保留

## P2 当前阶段决策

**状态：DEFERRED / NON-BLOCKING FOR POC**

当前阶段不继续处理 P2 架构项。

原因：P2 主要属于外围能力、后续治理、工程优化或增强性能力；现有已冻结的 P0/P1 架构已经足以支撑当前 POC。

原则：

- P2 不作为进入 POC 的前置条件。
- POC 不因 P2 未完成而阻塞。
- POC 期间如果某个 P2 问题实际影响 correctness、recoverability、provider replaceability 或 production viability，再将对应条目重新提升为 active backlog。
- 不为了“架构完整”提前设计外围系统。
- 当前优先级转为执行 POC、收集实测证据、验证 Framework/Provider public extension points 与既有 Contracts。

---

## ARCH-TODO-017 Multi-Agent / Subagent Ownership

**状态：DEFERRED**

**范围澄清（2026-10-10）：** 此处延期的是深度递归子 Agent、A2A/动态 Multi-Agent Topology，**不是**第一期必须支持的跨 Agent 顺序串联。基础串联基于 Harness Recipe/Plan/Step 与 ARCH-TODO-025 Runtime SPI 的集成验收，不能因为本条 DEFERRED 而取消。

当前不优先围绕 Multi-Agent 设计平台。

后续需要讨论：

- spawn / ownership
- child execution limits
- child cancellation
- context inheritance
- artifact/evidence lineage
- A2A remote agent
- subagent recursion limit
- convergence

原则：先把 Run / Step / Executor / Topology / Execution Limits / Capability 做正确，再扩展 Multi-Agent。

**已记录的讨论方向：**

- 子 Agent 作为运行时参与者（Participant），不新建一套顶层业务领域模型。
- 子 Agent 必须有 Owner、Run/Step 归属、执行限制和取消传播。
- 子 Agent 不得擅自扩大父任务目标。
- 只读子 Agent 可以共享只读基线；可写子 Agent 默认使用独立 Worktree。
- Agent 不拥有 Worktree，Repository Workspace 才拥有 Worktree。
- 子 Agent 产出必须形成 Artifact / Evidence / Finding / Patch 等可追踪对象。
- MAF 可通过 Agent-as-Tool、Workflow/Multi-Agent Orchestration、Sub-workflow 映射这些能力；平台语义不能依赖 MAF 独有模型。

---

## ARCH-TODO-018 Data Residency / DLP / PII

**状态：TODO**

重点用于决定：

- 哪些 Run 可进入 Remote Cube cluster。
- 哪些文件/代码不能离开指定区域。
- 哪些数据可进入外部 Model Provider。
- DLP policy 与 egress policy 如何联动。

---

## ARCH-TODO-019 Cache Architecture

**状态：TODO**

范围：

- repo mirror
- git object cache
- npm/pnpm cache
- Maven/Gradle cache
- Python cache
- browser cache
- environment/template cache
- cache tenancy
- poisoning prevention
- eviction

该项直接影响 Coding latency、磁盘与网络容量。

---

## ARCH-TODO-020 Provider / Adapter Contract Test Suite

**状态：TODO**

**2026-10-09 增量 POC：** 已开始验证同一个 SandboxProvider
在 OpenCode 与 OpenAI Agents SDK 等不同 Harness 之间的适配。
见 [OpenCode / OpenAI Agents SDK 统一 Sandbox 专项](../poc/opencode_sandbox/README.md)。
目前 Docker 统一 Provider 的任务 Scope 隔离和 SDK Native/FunctionTool
局部实测通过，但 Cube/E2B 真机、OpenCode 全工具隔离、真实
跨 Harness 同物理 Sandbox 接力、容量压测都未验，**本待办保持 TODO，
不得将专项局部 PASS 升级为跨 Harness Provider Contract 全面通过**。

**状态更新：** 上句是早于 Cube 真机运行的历史 POC 记录；2026-10-09 已有 Cube 原生 SDK 真机 PASS，官方 E2B 2.53.1 与 OpenAI Native Client 405 FAIL。后续以 ARCH-TODO-026 与目标架构候选快照为准；020 合约套件依然 TODO。

需要建立平台级 Contract Suite，而不是只靠接口签名保证可替换性。

至少覆盖：

- Agent Runtime Adapter
- SandboxProvider
- Model Provider
- ContextProvider
- Session/Checkpoint Store
- Event Translator
- Tool/MCP Adapter
- Environment Provider

目标：替换实现后，上层 Workflow 与领域模型无需修改。

**2026-10-09 当前真实验证修订：** Cube v0.7.2 已在独立 WSL2 + 16 GiB XFS 中用其原生 SDK 创建 MicroVM，完成 Shell/文件/运行中按 ID 重新连接，且 OpenAI Agents SDK FunctionTool 接同一真实 Sandbox 有局部 PASS；不可再称为“没有 Cube 真机”。但官方 E2B SDK 2.53.1 及 OpenAI 原生 E2BSandboxClient 真实创建均因 HTTP 405 失败，OpenCode 2 在 Cube 仍缺专用 OCI 模板，完整 Runtime-SPI 跨 Harness 接力尚未通过。下列 ARCH-TODO-025～028 分拆剩余 Gate，**020 保持 TODO，024 保持 POC CANDIDATE，均未正式 CLOSED**。

## ARCH-TODO-024 Multi-Harness Sandbox & Shared Runtime Density

**状态：POC / ARCHITECTURE CANDIDATE（未接受）**

**触发：** PDLC 与 AI 企业门户的专业 Agent 将运行于 OpenCode 2、
OpenAI Agents SDK、MAF 等不同 Harness。高密度要求逻辑 Session 不与
Runtime Worker/Sandbox 一一绑定；Sandbox 由 Execution Capability
按需申请，且跨 Harness 可共享**平台 SandboxProvider 契约**。

**本轮候选文档：** [多 Harness 共享 Sandbox 与 Runtime 密度](references/MULTI_HARNESS_SANDBOX_RUNTIME_DENSITY_CANDIDATE.md)。

**核心未决：** OpenCode 2 SDK Host 的多 Session/CWD/LSP/PTY/插件文件隔离能否
通过公开扩展点建立；Harness-in-Sandbox 与 Shared Host 两拓扑的真实
资源优势；OpenCode 2 和 OpenAI Agents SDK 使用同一个实际 Sandbox
完成 Workspace 接力；CubeSandbox 全链 conformance 和安全恢复。

**收口要求：** 对照同等隔离/负载完成安全、资源和任务级恢复验收后，
再决定生产主拓扑、更新 Accepted ADR。当前不改变 P0/P1 已接受约束，
不得因为 OpenCode 2 新 API 就修改平台领域模型。

**2026-10-09 顺序修正：** 将 CubeSandbox 提供 E2B 兼容接口作为当前首要
门禁；[Cube E2B 兼容性与环境阻塞记录](../poc/opencode_sandbox/CUBE_E2B_COMPATIBILITY_FINDINGS.md)。
只有 Cube 原生端到端 conformance 通过，才继续讨论共享 Host 的资源优化。

**OpenCode 2 反向实测：** 共享 Host 两 Session + 两个外部隔离 Sandbox，
OpenCode 原生 Shell 仍在 Host 执行。已记录于
[架构候选](references/MULTI_HARNESS_SANDBOX_RUNTIME_DENSITY_CANDIDATE.md)。
因此不采纳“仅 Session ID→Sandbox ID 配置即可实现透明工具隔离”
这一假设；Topology B 保持未通过，待公开扩展点完整覆盖。

**2026-10-09 阶段性验收/选型增量：** 用户明确当前系统本就未完成隔离，
故先记录每种技术实际达到的能力，Session→Sandbox 功能性验证
不再被全部宿主机执行入口安全重定向阻断；生产隔离要求保持不变。
引入 [多专业 Agent 技术选型评估](references/MULTI_HARNESS_TECH_SELECTION_20261009.md)，
重点对照 **Pydantic AI Harness + Temporal + Cube(E2B)**、
**OpenAI Agents SDK + Temporal + Cube(E2B)** 与已投入的
OpenCode 2 / MAF；目前全部为候选，尚无完美零适配技术栈。

---

## ARCH-TODO-025 AgentRuntime SPI / Pydantic 默认 Adapter 与跨 SDK 可替换性

**状态：POC / ARCHITECTURE CANDIDATE（P1；未接受）**

**方向：** Pydantic AI Harness 是新通用 Agent 的默认 Runtime Adapter 候选；OpenAI Agents SDK、OpenCode 2 和 MAF 分别作为独立适配器。SDK 切换由**平台 AgentRuntime SPI** 实现，不由 Pydantic 原生托管其他 SDK；模型 Provider 切换另行治理。关联 [目标架构候选](references/MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md)。

**业务优先级 P0（2026-10-10）：** 单一 Run 下以 Recipe/Step 顺序调度至少两个异构 AgentRuntime；使用授权 WorkspaceRef 和受控 Artifact/Evidence 交接，失败阻断后继 Step，支持重试/重规划、审批暂停与任务级恢复。现有真实 Tool 接力不等于 Kernel 端到端串联完成。PDLC 是用例而非固定流程。
**2026-10-10 版本冻结门禁：** [已验证 SDK/Runtime/OCI Digest/Template 快照](references/VERIFIED_STACK_BASELINE_20261010.md) 已单独存为机器可读基线，包含 E2B 2.40.0 限定 PASS / 2.53.1 HTTP405 负例及自动防漂移验证；后续集成必须依 [Accepted Registry & Versioning Contract](references/REGISTRY_AND_VERSIONING.md) **在 Run 创建时**记录确切 Runtime/Adapter/SDK/Environment/Digest，重试/恢复沿用冻结绑定。POC 快照不等于数据库层已实现此持久化。


**待办与完成标准：**

- 定义最小 RuntimeExecutionContext（Run/Session/Scope/Lease/WorkspaceRef/Capability），以及 Event Translator 的 Typed Events/Token SSE/Tool Receipt/Cancel 公开适配契约；不添加新的重复领域状态机。
- 使用 Pydantic、OpenAI SDK、OpenCode 2 **三个真实 Runtime** 对同一平台 Run Contract 进行受控执行/选择/失败/取消；无支持能力必须明确标记 unsupported。
- 验证无 Shell/文件需求时不申请 Sandbox；同一 Worker 多 Pydantic Run/Session；升级测试冻结 SDK 0.x 版本。
- 凡仅 Mock、FunctionTool 直调、无模型 Agent Loop 的局部结果只标 LIMITED PASS，不代替完整 SDK/Session Gate。

**未关闭原因：** Pydantic 20 并发与 Run-scoped LocalWorkspace 仅离线/Linux CI；跨三 Runtime SPI 未完成。

---

**2026-10-09 新增有限真实 SDK 证据：** 已运行 1 个 Pydantic AI 基础 Agent 对真实 Cube Native Sandbox 的两个 Run、6 个 `@agent.tool` 读写/Shell 调用；OpenAI SDK `@function_tool` 成功读取同一个 Workspace。属于跨 Runtime 公共 **Tool Adapter 真机 PASS**，不等于已实现平台完整 AgentRuntime SPI、Pydantic Harness 内置 Coder/E2BSandbox 或真实 LLM 模型；本 TODO 保持 POC，不关闭。

**2026-10-10 AgentRuntime SPI 新增代码：** [实现与证据](../poc/runtime_spi/README.md)，平台自有 `ExecutionContext / SandboxGrant / RunRequest / AgentRuntimeDispatcher`，在单一合同上提供 Run Started/Completed/Failed/Cancelled/Unsupported、缓冲 `response.output_text.delta` / SSE 编码、租约 Fencing/Owner/Scope/Capabilities Fail Closed。独立离线 Mock 覆盖 6 类无授权拒绝与 Cancel UNKNOWN；在真实安装的 `pydantic-ai-slim==2.54.0`、`openai-agents==0.23.1` 上分别实际调用了公共 `Agent.run` 与 `Runner.run`，通过本地确定性 Model 完成相同 Run 合同（**SDK RUN LIMITED PASS，0 托管模型调用**）；OpenCode 2 `session.prepare` SPI 目前仅在离线 Fake Session Factory 下 PASS，`model.run` 明确 UNSUPPORTED。**真正 Token SSE、外部 Receipt/ACK/DB、取消真实工具副作用、OpenCode 模型 Agent Loop/真实 Cube Lease SPI/Worker 接管尚未通过，025 保持 OPEN**。

## ARCH-TODO-026 Cube E2B 兼容矩阵与真实多 SDK 接力

**状态：POC / E2B 2.40.0 + OpenAI Native LIVE LIMITED PASS；最新 E2B 2.53.1 仍协议不兼容（P0；未接受）**

**方向：** CubeSandbox 由平台 SandboxProvider SPI 统一使用；先修复或隔离官方 E2B 兼容缺口，不能把 Cube Native SDK PASS 冒充原生 E2B SDK PASS。参考 [Cube 实测](../poc/opencode_sandbox/CUBE_E2B_COMPATIBILITY_FINDINGS.md)。

**待办与完成标准：**

- 对 Cube v0.7.2 × E2B Python SDK 2.53.1 / 官方支持的版本，实际验证 POST Sandbox.create、Connect、files、commands、kill；记录 HTTP 路径/返回码及 Native/Adapter 版本矩阵。
- 确认 E2B 2.53.1 使用 POST /v2/sandboxes 时当前 Cube 返回 405 的根因，选择**官方兼容版本或公开 Cube SDK/REST 薄 Adapter**，不得侵入式 SDK monkey patch；不支持的能力明确标 Unsupported。
- OpenAI 原生 E2BSandboxClient 与 Pydantic E2BSandbox + WorkspaceRef 分别通过同一真实 Cube Sandbox ID 连接、写入/读取/命令/销毁；至少两个 SDK/Tool Adapter 互相接力。
- 恢复 Cube 在 WSL 重启时的 Control/API/TemplateCenter/CubeEgress 健康检查、模板副本 READY 及可复验脚本；验收日志保留到仓库，不把启动超时当作协议不兼容。

**已有证据：** Cube 原生 SDK MicroVM/Shell/Files/reconnect PASS；E2B 2.53.1 与 OpenAI 原生 E2B Client 创建 **FAIL（405）**。

---

**2026-10-09 晚间兼容矩阵增量：** 已检查官方 SDK 1.0.5 / 2.0.0 / 2.40.0 对 `POST /sandboxes` 与连接配置的公开行为：1.0.5 无 `Sandbox.create`，2.0.0 的 debug 返回 synthetic `debug_sandbox_id`，2.40.0 支持 `E2B_API_URL` 但真实连接仍受到 Cube 冷启动健康门禁阻塞，**026 不可关闭**。具体原始证据在 [Cube专项](../poc/opencode_sandbox/CUBE_E2B_COMPATIBILITY_FINDINGS.md)。

**2026-10-09 进一步真机验证：** `e2b==2.40.0` 在 3000/8090/9091 均健康时官方 `Sandbox.create` 已返回非 Debug 的真实 Cube Sandbox 句柄；`files.write` 阶段 `ConnectError`，未触发 `commands.run`。026 的 Control Plane 局部 PASS、Data Plane **BLOCKED/FAIL**，应重点查 E2B `*.cube.app` 域名解析、TLS/CA、CubeProxy，而不能提前关闭 CUBE-1。详见最新 [Findings](../poc/opencode_sandbox/CUBE_E2B_COMPATIBILITY_FINDINGS.md)。

**2026-10-10 ARCH-TODO-026 原生 E2B/Cube 真机突破：** [官方 SDK / 独立 DNS 真实验收](../poc/opencode_sandbox/E2B_PRIVATE_DNS_VERIFICATION_20261010.md)。`e2b==2.40.0` 本身已能对 Cube v0.7.2 进行真实 `POST /sandboxes`，此前 `files.write ConnectError` 是 **WSL 默认 DNS 不走 Cube 已配置的 `~cube.app` 路由 + 官方 SDK `E2B_DOMAIN` 默认 `e2b.app`** 的客户端环境问题。使用独立 Linux mount namespace 的 resolver bind 和 `E2B_DOMAIN=cube.app`、本地可信 CA，不修改全局 DNS/TLS/SDK 私有字段，真实 `create → files.write/read → commands.run → kill` **PASS**；额外两真实 Sandbox 文件隔离和官方 `openai-agents==0.23.1` 的原生 `E2BSandboxClient.create/exec/aclose` **PASS**（零模型调用，`sdk_private_patches=false`）。**CUBE-1/CUBE-3 最小版本锁定的真机门禁已通过；`e2b==2.53.1` 对 `POST /v2/sandboxes` 仍 405，Pydantic 内置 E2BSandbox/跨 SDK 同一 Sandbox ID Native Connect、生产 Scope/Lease/恢复仍开放，因此 026 仍 OPEN，不是生产 Accepted**。此段优先于下方 2026-10-09 的 Data Plane ConnectError 历史结果。

## ARCH-TODO-027 OpenCode 2 Cube 专用 OCI Template / Session 真实绑定

**状态：真实 Cube Harness-in-Cube 核心功能 POC LIVE PASS / 未 Accepted（P0；平台 Scope/Lease、统一 Runtime SPI、生产隔离待验收）**

**方向：** OpenCode 2 Coding 优先验证 Harness-in-Cube（Topology A）。共享 Host 原生 Shell/FS/PTY/Git/LSP/Plugin 不因 SessionID 映射自动重定向到 Sandbox（已有 Docker 反向证据），生产 Topology B 仍 NO-GO。

**待办与完成标准：**

- 构建含 OpenCode 2.0.24（锁镜像 Digest/版本）、必需工具链、Cube envd/Probe 和必要服务端口的 OCI 模板；在自建 Cube 真机启动并认证 OpenCode 2 V2 Server。
- 在同一 Cube MicroVM 使用 OpenCode V2 创建不少于 2 个 Session；执行原生 FS/ Shell 和至少一项 Git 工作流，验证文件只出现在绑定 Cube Workspace；与 OpenAI/Pydantic Tool Adapter 在**同一 Sandbox ID** 顺序接力。
- 记录 Host 宿主机侧绕过路径（FS/Shell/PTY/Git/LSP/Plugin/Skill）；无法透明安全重定向的共享 Host 能力应禁用或明确 unsupported，不因单一 Shell 成功宣布全隔离。
- 多 Session 不要求多 Harness 进程；按活动执行/Isolation Scope 测试 Worker 数、Sandbox 数、回收及独立租约拒绝。

**已有证据：** Docker 内 OpenCode 2.0.24 ↔ OpenAI FunctionTool 有限 PASS；Cube 默认 sandbox-code 镜像没有 opencode/node/npm/bun，尚未测试 OpenCode 真机链路。

---

**2026-10-09 晚间 OpenCode 模板增量：** 真实 OpenCode 2.0.24 OCI 二进制与 Cube sandbox-code 基础镜像已在独立 WSL Docker 获得。原生 OpenCode (Alpine/musl) 直接拷入 Cube guest (Debian/glibc) 的 build-time Version Smoke 返回 127，正在用独立 musl Loader/Private Libraries 保持 Cube envd ABI；尚无 OCI Template READY/真实 V2 Session。Cube 官方 Bash-only 插件是 *每 Bash 调用新 VM / Host 编辑与 Guest 文件不共享* 的有限隔离实现，不能代替该 TODO，**027 继续 OPEN**。更多见 [OCI 模板专项](../poc/opencode_sandbox/opencode2_cube_template/README.md)。

**2026-10-09 进一步 OCI Builder 验证：** 已完成独立 WSL Docker 组合镜像 `ahp-opencode2-cube:poc`，实际构建结果 `Successfully built 825b61c967d0`，`opencode v2.0.24`。此项使 **OCI Build/ABI Gate PASS**；本地 OCI registry pull 遇连接重置，Cube `tpl create-from-image` / Template READY / 真实 V2 Server Session **仍待验证**，027 保持 OPEN。参见 [模板 README](../poc/opencode_sandbox/opencode2_cube_template/README.md)。

**2026-10-09 22:50 根因和复测收口：** [完整 RCA](../poc/opencode_sandbox/opencode2_cube_template/INCIDENT_20261009.md) 已定位旧 Job `ec70a828...` RUNNING 40% 残留原因：WSL/systemd 停止 CubeTemplateCenter 的构建 Context，原生 exporter 返回 `context canceled`，TemplateCenter 向 CubeMaster 的 FAILED 回调也取消，Master 保留过期 RUNNING。启用持续 WSL 保活后用**同一镜像**新 Job `4be59892...` 实测 OCI Pull/EXT4 RootFS **READY** / 节点分发 1/1 全通过；后续 `CREATING_TEMPLATE` 的 Cubelet/Shim 等待事件 10s 超时，Job 最终 **FAILED**。因此“40% 构建卡死”原因 CLOSED，但新的 Guest Boot/Ready Event Gate **OPEN**；Template READY/OpenCode V2 Session 仍 NO-GO，027 不关闭。缺省运行生产容器、磁盘备份不属于本平台职责，第三方 Cube Callback 对账需作为依赖门禁而不是平台自建基础设施。

**2026-10-10 真实 Cube 复验增量：** [最新 V2 复验记录](../poc/opencode_sandbox/opencode2_cube_template/VERIFICATION_20261010.md)。同一镜像的 Guest Agent 冷启动间歇通过但原 Jupyter Code Interpreter Kernel Startup 迟滞，Cubelet 49999 健康探针超时 `PortBindingFailed`；改为 Coding 专用 **envd(49983) + 轻量 health(49999)** 后模板 `tpl-aacac99e38bf46e68ecd2f1f` 真实 **READY**。同一个 MicroVM 内 OpenCode 2.0.24 `2 V2 Session + FS read + Shell write`、Cube Native SDK connect/read、Pydantic Agent 公共 Tool 与 OpenAI SDK FunctionTool 读取 V2 Shell 写入文件、Kill **LIVE LIMITED PASS**，0 模型调用；不再归类为 `BLOCKED BY TEMPLATE`。仍须确认 Git 工作流、Sandbox Scope/Lease/并行隔离、真实 LLM/平台 Typed Event/Cancel/Receipt 等门禁，**027 保持开放，不视为生产验收**。

**2026-10-10 最终 Git-enabled 验收：** [严格 Cube 真机复验报告](../poc/opencode_sandbox/opencode2_cube_template/VERIFICATION_20261010.md)：Git Debian 12 / 2.39.5 已在 Cube 专用 OCI Guest 内置，镜像 Digest `sha256:9e4bde62fad22f2b22a2bd858ec865e403caccead740d113afc8c9a9e89e284f`；Template `tpl-363306ce3b21432cb1ae6536`、Job `c835c0cd-9cf6-4628-9e8e-c4730a3873c0` **READY**。同 1 个真实 Cube MicroVM 内 Git `init/add/commit/log`、OpenCode V2 2 Session、V2 FS/Shell 文件接力、Pydantic Agent 公共 Tool、OpenAI FunctionTool、Cube 同 ID reconnect + Kill **全 PASS**（零托管模型）。**027 功能 POC 门禁可判定 PASS；依照接受标准，真实跨 Scope 授权租约/多 Worker 密度/所有 Host 原生执行入口系统性隔离/平台统一 Runtime 事件、生产安全仍未验收，故 ARCH-TODO-027 保持 OPEN/非 Accepted。** 后续避免重复测试已通过的简单命令/模板，优先推动 025 与 026，再形成完整准入。

## ARCH-TODO-028 Process/Durable 默认实现与任务级恢复对比

**状态：TODO / POC CANDIDATE（P1；未接受）**

**方向：** Temporal、MAF Durable、PG + Worker/Scheduler 作为 Process/Durable SPI 候选。Pydantic 选为默认 Agent Adapter 不等于 Temporal 自动被淘汰或必须成为基础设施。

**待办与完成标准：**

- 冻结同样的任务级恢复场景：Worker A Crash、Worker B 接管、WAITING_APPROVAL、Cancel/Timeout、RecoveryPoint、真实非幂等 Tool Receipt UNKNOWN → Reconciliation。
- 比较三种方式所需的**新增开发量、版本运行兼容、状态持久化/恢复证据、运维成本**，以任务级继续/安全失败为标准；磁盘/数据库/对象存储备份不属 Harness。
- 若引入 Pydantic TemporalDurability，需要定义与平台 Workflow/Durable 层的职责分界，防止同一 Agent Run 重复包两层 Durable 引擎。
- MAF POC-A 与 Temporal POC-C 已有成果继续保留；形成等价验收结论后再决定生产默认并单独更新 Accepted ADR。

**未关闭原因：** 当前三方案尚未按新的多 Runtime/同 Cube 场景完成一致性成本比较。

---

## ARCH-TODO-029 存量 OpenCode PDLC 平台无感替换与跨 Agent 串联

**状态：P0 / 业务目标已确认；旧平台实码盘点与迁移集成未完成（非 Accepted）**

**业务目标：** 当前企业内产品、研发、测试、文档及业务 Agent **统一基于 OpenCode 实现**。新平台必须**替换其 PDLC 执行与控制架构，保留既有建设并实现用户侧平滑迁移**；同时新增能够将不同专业 Agent SDK 编排成一条任务的**跨 Agent 串联能力**。更换底层架构并不要求淘汰 OpenCode Coding Runtime，也不意味着在新平台复制既有 PDLC 需求/迭代/知识库等业务领域模型。

**架构策略：** 保留既有 UI/业务资产/项目与会话读取能力，经 Legacy API Facade 与稳定 ID 映射逐步迁移新 Run；原活动会话由旧执行端安全继续或在经验证的恢复点切换；同一写操作只允许一个执行 Owner，不做有副作用的双写。新 Harness 负责 Recipe/Step/Attempt/任务事实、交接、审核与恢复；各 Agent SDK 由 AgentRuntime SPI 接入。

**分阶段必过门禁：**

1. **M0 旧平台只读事实盘点：** 获取现有 PDLC 源码、运行版本、API/事件、数据 Schema、OpenCode Session、Prompt/Skills/Subagents/Plugins/Hooks/MCP、Workspace/Git、对象存储、身份权限与启用功能清单；形成业务功能与迁移对象的一一对应表。**当前 Agent Harness 仓库无法独立证明旧 PDLC 每项现网能力。**
2. **M1 原功能与数据兼容：** 既有 URL/页面/SSO、历史消息/附件、项目/工作区、已有 Agent 与 Skill 均可继续使用；旧 Session/新 Run ID 稳定关联，跨 Scope 请求拒绝。
3. **M2 逐步灰度：** 新请求按确定性路由进入旧/新运行时；有副作用的执行禁止双写，失败和回退不导致重复 Tool/Git/外部业务操作。
4. **M3 跨 Agent 串联：** 至少一条真实既有 PDLC 场景通过一个 Run 下 ≥2 个 Runtime 的 Recipe/Step 执行、受控 Artifact/Evidence 交接、验收阻断、审批、失败与任务级恢复；该机制必须能被非 PDLC Agent 复用。
5. **M4 用户无感验收与回退：** 以真实用户/项目和活动会话分别检查原功能、行为、权限、数据、Workspace/历史、一致性及回退；新旧执行权威和副作用对账清晰，未经验收不宣告生产迁移成功。

**专题及验收矩阵：** [现有 PDLC 平台替换与无感迁移方案](references/PDLC_REPLACEMENT_MIGRATION_20261010.md)。本项优先于单独实现通用 Harness Demo；与 ARCH-TODO-025～028 并行，但上述后续 Gate 不因现有 Cube/E2B/OpenCode 功能 POC 通过而自动关闭。

# 5. 推荐讨论顺序

按依赖关系建议：

~~~text
001 Domain Model & State Contract
 ↓
002 Failure / Idempotency / Side Effect
 ↓
003 Workspace / Repository / Git
 ↓
004 Runtime Topology
 ↓
005 Checkpoint / Snapshot Consistency
 ↓
006 Security Threat Model
 ↓
007 Registry & Versioning
 ↓
008 Execution Lease / Fencing
 ↓
009 Identity / Authorization
 ↓
其余 P1 / P2
~~~

其中 **001、002、003** 是进入正式 POC 实现前最需要冻结的三项。

# 6. Backlog 管理规则

0. 每个待办开始讨论前，先判断它是否真正属于 Harness Platform：若只是 Harness 的外部依赖、企业治理或基础设施能力，优先关闭为 Ownership Boundary，只定义消费接口/元数据，不在 Harness 内设计完整产品。

1. 每次只选择少量关联项深入讨论，避免把讨论扩散成一次性大设计。
2. 讨论过程中允许记录 Options，但在 Decision 前不得更新正式 ADR 为 Accepted。
3. 形成结论后：
   - 更新对应专题文档；
   - 更新 `ARCHITECTURE.md`；
   - 必要时更新 `POC.md`；
   - 新增/更新 ADR；
   - 本文件状态改为 CLOSED。
4. 任何 POC 暴露的新架构问题，优先回到本 Backlog 登记，再决定是否扩展范围。
5. 不因为某个框架当前实现方便而改变平台领域模型。


---

## ARCH-TODO-021 Project Instructions / Skills Context

**状态：TODO**

### 来源

ARCH-TODO-003 讨论过程中扩展出的项目上下文问题。

### 需要讨论

- Project Repository 中 AGENTS.md、Project Skills、公共规范如何发现和解析。
- AGENTS.md 是否只是 ProjectInstructionProvider 的一种实现。
- 项目级 Skill 的发现、版本、优先级与继承。
- 根目录/子目录指令覆盖规则。
- Main Agent / Subagent / Runtime 如何获得 Effective Project Context。
- MAF SkillsProvider 与平台 ProjectSkillsProvider 的映射。
- Codex/OpenCode 自身规则发现与平台级保证之间的边界。
- 非 Coding Agent 是否需要项目指令。
- 项目上下文如何随 Worktree / Repository Workspace 切换重新解析。

### 当前已接受方向

- 不是所有 Agent 都必须依赖 AGENTS.md。
- 平台需要的是“项目级指令能力（Project Instructions）”，而不是硬编码 AGENTS.md。
- 项目级 Skill 是可选能力，不应成为所有 Runtime 的强依赖。
- Provider/Runtime 原生规则加载机制可保留，但不能成为平台唯一保障。

---

## ARCH-TODO-022 Skill Script Execution / Runner

**状态：TODO**

### 来源

讨论 MAF 项目级 Skill 时扩展出的脚本执行问题。

### 需要讨论

- 内联技能脚本（Inline Skill Script）与文件型技能脚本（File-based Skill Script）的安全边界。
- MAF SkillScriptRunner 如何映射到平台 Execution Plane。
- LocalSubprocessSkillRunner 仅用于开发/调试还是完全禁用。
- 生产默认 SandboxSkillRunner / CubeSandbox Runner。
- Script 的 Policy / Approval / Timeout / Cancellation / Resource Limit。
- Script Side Effect Contract 与 Evidence。
- Python / Shell / Node 等脚本类型支持。
- Skill Script 版本、Environment Profile 与工具链一致性。

### 当前已接受方向

~~~text
MAF SkillsProvider
→ run_skill_script
→ Platform SkillScriptRunner
→ ExecutionScheduler
→ CubeSandboxProvider
→ CubeSandbox
~~~

生产文件型 Skill 脚本不得默认绕过 Execution Plane 落到 Agent Runtime 本机 subprocess。

---

## ARCH-TODO-023 E2E / Integration Test Environment

**状态：TODO**

### 来源

多仓 Project Workspace 讨论过程中出现，但明确不在 ARCH-TODO-003 展开。

### 需要讨论

- 为一次 Run 拉起独立测试环境，还是绑定现有测试环境。
- 多个后端/前端仓库如何组合部署。
- Integration Environment 的生命周期、租约、隔离与清理。
- 测试数据与数据恢复。
- 并发 Run 的环境冲突。
- 环境与 Repository Revision Set 的绑定。
- E2E Evidence、失败恢复与成本控制。

该主题单独讨论，避免 Workspace/Git Contract 承担部署环境职责。

---

## ARCH-TODO-024 Microsoft Execution Containers（MXC）Sandbox Backend 候选

**状态：DEFERRED（Candidate / 未采纳 / 未验证）**

**来源：** Microsoft 于 2026-10-07 宣布 MXC GA，需判断 OS 级执行隔离能否作为可选 Sandbox 后端；但官方仓库仍带有 early preview 与 security-boundary 警告。

**候选结论：**

- MXC 仅作为现有 **SandboxProvider SPI** 下的可选执行后端候选；不新增平行 SPI，不调整当前 CubeSandbox 生产候选及 Docker 开发/兼容定位。
- TaskContext/Workspace 路由是逻辑隔离，不能替代 OS 沙箱；共享 Harness Worker、MAF/Agent SDK 与平台领域模型不变。
- 不承诺 MXC 在 Linux 默认后端实现 Windows Session、持久 Sandbox、快照或同等级网络强隔离能力；须按 host/backend/version 独立验证。
- 不改变现有 Checkpoint、RecoveryPoint、UNKNOWN → Reconciliation、Tool Receipt、OSS Artifact/Evidence 和外围治理 Ownership Boundary。
- **本条属于 P2 技术观察，不纳入当前 POC-A / POC-C Hard Gates，不阻塞 G3/G2/G6 收口。**

**后续触发：** 当前核心 POC 收口后，若存在轻量 Tool/Code Execution 需求，则按同负载对照验证隔离正确性、网络/凭据、cancel/cleanup、任务恢复、环境一致性及并发性能，再决定 Adopt / Keep Candidate / Reject。

**候选评估记录：** [MXC_EXECUTION_CONTAINER_CANDIDATE.md](references/MXC_EXECUTION_CONTAINER_CANDIDATE.md)

---

## ARCH-TODO-025 Durable Control Plane 生产架构准入

**状态：POC（未通过生产硬门禁，非重启 POC-C）**

**优先级：P0（完整 G2/G3/G6）；P1（G4/G5/生产成熟度）**

**来源：** [POC-C 阶段评估收口](POC_C_EVALUATION_CLOSEOUT.md) / [C14 同口径评估](../poc/temporal/C14_COMPARATIVE_DECISION.md)。本条是 C00–C16 阶段性评估之后的**唯一开放行动台账**，不创建 C17/C18。

### P0 实证验收（必须成功与故障注入）

1. **G3 / 同一真实 Run 协议**：自托管 Responses-compatible Create/GET、真实 Token SSE、Plan/Tool/Verify/Artifact/Approval/UNKNOWN 持久 Typed Event 在同一 Run 对齐，HTTP/API/Worker 重启、Last-Event-ID 重放、游标隔离、Cancel→CANCELLING/UNKNOWN/终态的完整边界均需正反例；不支持的官方语义明确 UNSUPPORTED，不伪装完全兼容。
   - **2026-10-09 增量（G3 仍 PARTIAL）：** [统一 Typed Event Feed](../poc/temporal/ARCH025_G3_EVENT_FEED_FINDINGS.md) 已扩展 C15 Token/C11 Artifact/C16 UNKNOWN/Receipt 的只读 Run SSE 投影及 provider 私有字段隔离；仍是**不同 POC Run** 的读取兼容，不是单 Run 业务闭环；独立本地 PostgreSQL 5/5 PASS、[Linux CI #37848460468](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37848460468) 5/5 Job SUCCESS（对应 5 项新测试均实际执行）。当时发现 C15 Cancel ACK 即终态的契约缺口；已由下方 2026-10-09 的限定 `PURE` 取消专项补证处理，非幂等业务取消仍未通过完整准入。
   - **同日同一 Run 的真实 S3 增量（G3/G6 仍 PARTIAL）：** [G3 Token→Artifact→Verify 与 ACK UNKNOWN 证据](../poc/temporal/ARCH025_SAME_RUN_S3_FINDINGS.md) 已在单个实际 Temporal Workflow/Run 上验证同一平台 PG Typed SSE 的 Token、真实 SeaweedFS S3 Artifact、独立 SHA256 验证与业务终态；物理 S3 PUT 后 ACK 丢失保持 Execution `UNKNOWN`/Reconciliation `PENDING`，不虚构成功或 blind retry。本地 PG 10/10 PASS，正常/负例两条实际 Temporal/S3 E2E PASS；模型使用显式 Fake Tokens；同一 Run 真实 Tool/Approval 和最终 Receipt 恢复仍未覆盖。
2. **G2/G6 / Native Start & RecoveryPoint**：验证 Server 接受但平台 ACK 丢失、确定未启动、Timeout 导致是否启动未知等窗口；冻结 Native Binding，持久 Opaque RecoveryPoint，使用官方接口反查；未查明时拒绝盲 Start。真实 Worker 故障后按 Run/Step/Attempt/Execution 恢复到最深安全点，覆盖 WAITING_APPROVAL、UNKNOWN、Same Attempt Resume 能力限制、新 Attempt 与 terminal never reopen。
   - **2026-10-09 取消契约增量（仍 G3/G6 PARTIAL）：** [C15 PURE Cancel Native 确认](../poc/temporal/ARCH025_CANCEL_CONFIRMATION_FINDINGS.md) 将早期错误的即时 CANCELLED 改为 CANCELLING→官方 Native describe 确认→平台终态；本地独立 PG 合约 7/7 PASS、真实 OSS Temporal/Worker 正常取消 ACK 与取消信号 UNKNOWN 两条 E2E PASS；对外部非幂等 Tool 未宣称通过，完整 Run/Tool 恢复门禁仍开放。
3. **G6 / 企业非幂等工具闭环**：在可获授权的已治理企业 Tool/MCP 真实 Receipt 接口上验证单次外部效果、崩溃后只读对账、Receipt 缺失/血缘不符/effect_count>1 均安全 fail-closed 或人工介入；Reconciliation RESOLVED 不直接将历史 UNKNOWN 或 Run 标成功，必须经过独立业务 Verifier/Decision 最终裁决。无真实企业接口时保留 GAP，不以受控 POC Tool 冒充企业验收。

### P1 真替换和生产成熟度

- **G4/G5**：第二真实 Model/Provider；CubeSandbox↔Docker SandboxProvider SPI 最小 conformance smoke，记录修改范围、降级模式和替代成本。
- **G1/G8**：Temporal 自托管 TLS/发布/Worker versioning 与 replay/rollout/rollback；外部 DB/OSS ownership；同负载 MAF vs Temporal TTFT/P95/CPU/Memory/依赖和运维工时对比。缺乏实测不生成分数；不自建企业 IAM、MCP Governance、APM、对象存储或数据库 Backup/DR。
- **退出条件**：同口径 G1/G2/G3/G6 真实复跑证据与 CI、部署差异及风险；任一完整硬门禁仍 PARTIAL/GAP 则**生产 NO-GO**。P1 要明确 Adopt / Conditional / Reject 和业务成本。最终形成独立新的 Accepted Production ADR，同步 `docs/ARCHITECTURE.md` / `docs/POC.md` 后，本条才能 CLOSED。

**架构边界：** Task Facts 和业务终态始终归 Harness；Temporal History/Checkpoint 不复制、不新建重复 Scheduler；MXC 属独立 P2 候选，不成为本项硬门禁。