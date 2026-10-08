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
   - **2026-10-09 增量（G3 仍 PARTIAL）：** [统一 Typed Event Feed](../poc/temporal/ARCH025_G3_EVENT_FEED_FINDINGS.md) 已扩展 C15 Token/C11 Artifact/C16 UNKNOWN/Receipt 的只读 Run SSE 投影及 provider 私有字段隔离；仍是**不同 POC Run** 的读取兼容，不是单 Run 业务闭环，实际 PG CI 待验证。另发现原 C15 Cancel 请求直接标记 `CANCELLED` 且忽略下游取消失败，违反已有 CANCELLING→终止确认/对账契约，必须单独负例闭合。
2. **G2/G6 / Native Start & RecoveryPoint**：验证 Server 接受但平台 ACK 丢失、确定未启动、Timeout 导致是否启动未知等窗口；冻结 Native Binding，持久 Opaque RecoveryPoint，使用官方接口反查；未查明时拒绝盲 Start。真实 Worker 故障后按 Run/Step/Attempt/Execution 恢复到最深安全点，覆盖 WAITING_APPROVAL、UNKNOWN、Same Attempt Resume 能力限制、新 Attempt 与 terminal never reopen。
3. **G6 / 企业非幂等工具闭环**：在可获授权的已治理企业 Tool/MCP 真实 Receipt 接口上验证单次外部效果、崩溃后只读对账、Receipt 缺失/血缘不符/effect_count>1 均安全 fail-closed 或人工介入；Reconciliation RESOLVED 不直接将历史 UNKNOWN 或 Run 标成功，必须经过独立业务 Verifier/Decision 最终裁决。无真实企业接口时保留 GAP，不以受控 POC Tool 冒充企业验收。

### P1 真替换和生产成熟度

- **G4/G5**：第二真实 Model/Provider；CubeSandbox↔Docker SandboxProvider SPI 最小 conformance smoke，记录修改范围、降级模式和替代成本。
- **G1/G8**：Temporal 自托管 TLS/发布/Worker versioning 与 replay/rollout/rollback；外部 DB/OSS ownership；同负载 MAF vs Temporal TTFT/P95/CPU/Memory/依赖和运维工时对比。缺乏实测不生成分数；不自建企业 IAM、MCP Governance、APM、对象存储或数据库 Backup/DR。
- **退出条件**：同口径 G1/G2/G3/G6 真实复跑证据与 CI、部署差异及风险；任一完整硬门禁仍 PARTIAL/GAP 则**生产 NO-GO**。P1 要明确 Adopt / Conditional / Reject 和业务成本。最终形成独立新的 Accepted Production ADR，同步 `docs/ARCHITECTURE.md` / `docs/POC.md` 后，本条才能 CLOSED。

**架构边界：** Task Facts 和业务终态始终归 Harness；Temporal History/Checkpoint 不复制、不新建重复 Scheduler；MXC 属独立 P2 候选，不成为本项硬门禁。