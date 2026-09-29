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

**状态：TODO**

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

**状态：TODO**

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

**状态：TODO**

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

**状态：TODO**

范围：

- execution lease
- lease TTL
- heartbeat
- fencing token
- stale Worker
- duplicate consumer
- worker crash / reconnect
- ownership transfer

目标：避免旧 Worker 复活后继续执行已经被 Retry、迁移或取消的 Step。

---

## ARCH-TODO-009 Multi-Tenant Identity & Authorization Propagation

**状态：TODO**

范围：

~~~text
User
→ Tenant
→ Run
→ Agent
→ Tool/MCP
→ Sandbox
→ External Service
~~~

需要定义：

- identity propagation
- RBAC / ABAC / Policy
- service identity
- delegated credential
- secret scope
- approval authority
- tenant isolation
- project/repository authorization

---

## ARCH-TODO-010 HA / DR / Backup

**状态：TODO**

范围：

- Control Plane HA
- PostgreSQL / Event Store backup
- Object Storage durability
- CubeSandbox control/data plane failure
- Redis loss/rebuild
- RPO / RTO
- region / cluster failure
- disaster recovery drill
- restore ordering

---

## ARCH-TODO-011 Artifact / Evidence / Log Retention

**状态：TODO**

范围：

- Artifact retention
- Evidence retention
- raw command logs
- build/test reports
- Workspace retention
- Sandbox snapshot retention
- GC
- legal/audit hold
- deduplication
- lineage after cleanup

---

## ARCH-TODO-012 Observability Contract

**状态：TODO**

范围：

- OpenTelemetry
- Trace / Span naming
- Run / Step / Attempt correlation
- Model / Tool / Sandbox spans
- metrics schema
- structured logs
- SLO / alert
- failure diagnostics
- topology correlation

---

## ARCH-TODO-013 Cost / Quota / Attribution

**状态：TODO**

范围：

- token/model cost
- sandbox CPU/RAM/runtime
- storage
- remote cluster
- browser/tool cost
- tenant/project/run attribution
- quota
- budget enforcement
- chargeback/showback

---

## ARCH-TODO-014 Environment Supply Chain Security

**状态：TODO**

范围：

- OCI provenance
- SBOM
- image signing
- signature verification
- vulnerability scanning
- base image policy
- dependency policy
- template promotion gate
- unsigned/unverified image rejection

---

## ARCH-TODO-015 Tool / MCP Trust Model

**状态：TODO**

范围：

- MCP Server identity
- Tool capability declaration
- trust level
- secret scope
- network scope
- version pinning
- untrusted tool output
- prompt injection through tool results
- audit
- revocation

---

## ARCH-TODO-016 Cancellation / Timeout Propagation

**状态：TODO**

范围：

~~~text
UI Cancel
→ Run Cancel
→ Step Cancel
→ Agent Cancel
→ Tool Cancel
→ Sandbox Command Cancel
→ subprocess kill
~~~

需要定义 graceful / force kill、timeout 层级、cleanup 与最终状态。

# 4. P2：明确延后但需要保留

## ARCH-TODO-017 Multi-Agent / Subagent Ownership

**状态：DEFERRED**

当前不优先围绕 Multi-Agent 设计平台。

后续需要讨论：

- spawn / ownership
- child budget
- child cancellation
- context inheritance
- artifact/evidence lineage
- A2A remote agent
- subagent recursion limit
- convergence

原则：先把 Run / Step / Executor / Topology / Budget / Capability 做正确，再扩展 Multi-Agent。

**已记录的讨论方向：**

- 子 Agent 作为运行时参与者（Participant），不新建一套顶层业务领域模型。
- 子 Agent 必须有 Owner、Run/Step 归属、预算边界和取消传播。
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
