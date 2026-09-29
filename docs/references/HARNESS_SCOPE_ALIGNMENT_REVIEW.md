# Harness Scope Alignment Review

> 日期：2026-09-29  
> 审计范围：ARCH-TODO-001 ～ ARCH-TODO-016、docs/ARCHITECTURE.md、docs/POC.md、AGENTS.md 与对应 Accepted Contracts  
> 触发原因：新增 Harness Platform 总职责约束——平台只拥有任务编排、执行控制、状态/恢复、协议与 Adapter 边界；外围企业治理与基础设施能力保持外置。

## 1. 审计结论

本轮没有发现需要推翻 001～016 核心领域模型的结构性问题。

问题主要来自早期总架构文档中的历史措辞：部分文字把 Tenant/IAM/Secret/Registry/Retention/MCP Trust 等外围能力写得像 Harness 自建产品，与当前 P12「Harness 职责收敛」原则不完全一致。

这些冲突已通过职责外置、Adapter/Reference 化和措辞修正处理，不改变已经冻结的 Run/Step/Attempt/Execution、Failure/Recovery、Workspace、Topology、Fencing、Cancellation 等核心语义。

## 2. 逐项审计

| TODO | 结论 | 审计结果 |
|---|---|---|
| 001 Domain Model & State | PASS | Conversation/Turn/Run/Plan/Step/Attempt/RecoveryPoint 属于 Harness 核心任务模型，无外围治理越界。 |
| 002 Failure / Idempotency / Side Effect | PASS | Retry/Replan/UNKNOWN/Reconciliation/SideEffectReceipt 直接关系执行正确性，属于 Harness。 |
| 003 Workspace / Repository / Git | PASS after wording alignment | Workspace/Revision/Worktree 属于 Coding Harness 执行状态；Repository ACL 与 Credential lifecycle 属于外部 Provider。Manifest access 已明确为 requested mode/capability requirement，不是 ACL。 |
| 004 Runtime Topology | PASS | 只记录 Participant 与稳定关系，不做服务发现、调度、治理平台。 |
| 005 Checkpoint / Snapshot Consistency | PASS | Harness 只拥有 RecoveryPoint/reference，Runtime checkpoint、Sandbox snapshot 由 Provider 负责。 |
| 006 Security Threat Model | PASS after boundary alignment | Trust Boundary/Instruction-Data/Control-Data Plane 属于 Harness；Secret lifecycle、Network enforcement、DLP、MCP admission 等已明确外置。 |
| 007 Registry & Versioning | PASS | Registry 已定义为 logical directory capability，不是中心化 Registry 服务；Run resolve/freeze 属于 Harness 正确性。 |
| 008 Execution Lease / Fencing / Heartbeat | PASS | 只治理 Harness Execution ownership，不接管 Runtime/Temporal/Cube 内部协调。 |
| 009 Identity & Authorization Propagation | PASS after boundary alignment | Initiator/Executor、SecurityContext、Execution authorization decision 与 Approval audit 属于 Harness；Authentication、Credential issuance/storage/rotation、Repository ACL 属于外部系统。Credential Provider 已明确为 Adapter。 |
| 010 Task Recovery Coverage | PASS | 只定义任务恢复事实与最深安全恢复点，不承担数据库/磁盘/集群 DR。 |
| 011 Artifact / Evidence / Log Retention | PASS after boundary alignment | Artifact/Evidence identity、Lineage、Recovery Pin、Tombstone 属于 Harness；企业 Retention Governance/Legal Hold/OSS lifecycle 已明确外置。 |
| 012 Observability | PASS | Harness 只定义 correlation 与最小 telemetry；Runtime 原生 OTel 优先，APM/Collector/Backend 外置。 |
| 013 Cost / Quota | PASS / OUT OF SCOPE | 已明确不是 Harness 职责。 |
| 014 Environment Supply Chain | PASS / OUT OF SCOPE | SBOM/signing/scanning/provenance 已明确归企业 CI/CD/Registry/Security。 |
| 015 MCP Trust | PASS / OUT OF SCOPE | MCP admission/trust/governance 已明确外置；Harness 只执行已准入 MCP。 |
| 016 Cancellation / Timeout | PASS | Cancellation/Timeout propagation 直接属于 Run/Execution 生命周期与副作用正确性。 |

## 3. 本轮发现并修正的历史冲突

### 3.1 Tenant / IAM 被画进 Harness Governance

旧总图存在：

~~~text
Control Plane
→ Governance
→ Tenant / IAM / Policy / Approval
~~~

并在部署章节把 Platform Layer 写成负责 Tenant/IAM。

已调整为：

~~~text
External Enterprise Governance
→ IdP / IAM / Credential / Admission
        ↓
Harness Control Plane
→ Execution Policy / Approval
~~~

Harness 保留当前 Execution 的 Policy/Approval decision，不拥有企业 IAM/Tenant Governance。

### 3.2 Credential Provider 容易被理解为 Harness 自建 Secret 产品

已冻结：

~~~text
Harness
→ Credential Provider Adapter
→ External Credential / Secret Infrastructure
~~~

Harness 可以请求 scoped credential/reference 并注入指定 Execution，但不负责 Secret/Credential 的存储、签发、轮换、撤销生命周期或 Vault/KMS/PAM 产品。

### 3.3 MCP Server 信任与 MCP 返回数据混在一起

已冻结：

- MCP Server / Tool 是否准入：外部 MCP Governance 负责；Harness 可调用即视为已准入。
- Tool/MCP 返回的 Repository/Web/API 等业务内容：仍不能自动提升为 Platform/System Instruction。

这是统一 Instruction/Data boundary，不是 Harness 对 MCP 再做一次 Trust Governance。

### 3.4 Registry 在总图中看起来像中心化服务

正式 Contract 本身一直明确 V1 不建设统一 Registry 服务。

总图已改为：

~~~text
Version / Capability Directory
(logical capability, not a service)
~~~

Environment Registry 也只允许作为 logical directory / external registry reference。

### 3.5 Retention 被写得像 Harness 企业合规治理

011 保留：

- Recovery Pin
- payload status/tombstone
- Artifact/Evidence lineage
- retention_policy_ref

但企业保留周期、Legal Hold/eDiscovery、对象存储 lifecycle 归外部治理/部署系统。

### 3.6 Network / Secret Enforcement 边界不够清楚

现在统一为：

~~~text
Harness
→ expresses Execution constraints
→ Policy / SandboxSpec / credential reference

External Provider / Infrastructure
→ actually enforces network / credential / resource isolation
~~~

Harness 不建设 Network Policy 或 Secret Manager 产品。

## 4. 明确保留在 Harness 内的“看似治理”能力

以下能力不应因为 P12 而错误外移：

### Execution Policy Decision

Harness 必须判断当前 Execution 是否允许继续，否则无法保证 Side Effect、Approval、Cancellation 和 Recovery 正确性。

外部 IAM/ACL/Entitlement 可以作为 Policy Input，但：

~~~text
Execution Context
+ external identity / entitlement facts
→ Harness Policy Decision
→ ALLOW / DENY / REQUIRE_APPROVAL
~~~

仍属于执行控制边界。

### Approval Fact

Harness 不建设企业审批平台，但 WAITING_APPROVAL / ApprovalDecision 是 Run 生命周期事实，必须由 Harness 持久化和恢复。

### Workspace

Workspace/Worktree/Repository Revision Set 是 Coding Run 的执行状态和恢复基础，不属于 Git Hosting 产品，因此继续由 Harness 模型拥有。

### Artifact / Evidence Metadata

OSS 产品外置，但 Artifact/Evidence ID、Lineage、Verification relationship、Tombstone 属于任务事实，必须由 Harness 拥有。

### RecoveryPoint

Runtime checkpoint engine 外置，但 RecoveryPoint/reference 是任务恢复语义，属于 Harness。

### Version Freeze

Package/Registry 产品外置，但 Run 创建时 resolve/freeze 到 concrete version/digest 是 Harness reproducibility contract。

## 5. 对 POC 的影响

本次审计不新增 POC 前置架构项。

P0/P1 仍可直接进入 POC。

POC 需要特别验证的是“边界是否真的薄”：

- 外部 IAM 可以接入，但 Harness 不需要 User Directory/SSO Server；
- scoped credential 可以接入，但 Harness 不需要 Secret Manager；
- OTel 可以输出，但 Harness 不需要 APM Backend；
- Environment digest 可以冻结，但 Harness 不需要 Supply Chain Platform；
- MCP 可以调用，但 Harness 不需要 MCP Governance；
- Artifact 可以写 OSS，但 Harness 不需要 Object Storage lifecycle/DR 产品。

如果某个 Framework 迫使 Harness 为完成这些外部能力而 fork/patch 或复制完整基础设施能力，则记为 Framework Gap，而不是扩大 Harness Scope。

### 5.1 POC 验收口径收口

本轮进一步确认：POC 候选路线与 12 个统一场景不需要重做，但验收口径必须按职责边界收窄。

- G2「状态自主」只要求 Task Facts、Recovery Reference、Artifact/Evidence Metadata/Lineage 由企业掌控；大 Payload 外置到 OSS/Object Storage。
- G6「恢复」明确为 Task-level Recovery；数据库、对象存储、磁盘、K8s/Region Backup/DR 不属于 Harness POC。
- S07 只验证从持久化任务事实与真实 Runtime Capability 恢复到安全边界，不验证基础设施容灾。
- S10 只验证 SandboxProvider SPI/Adapter 可替换性；第二套 production-grade Sandbox 不是首轮硬通过条件。
- Observability 优先复用 Runtime/Framework 原生 OpenTelemetry，Harness 只补 correlation 与平台自有边界，不建设 APM Backend。
- Cost/Quota 与 MCP Trust 只保留 Ownership Boundary Check，不作为首轮 Framework POC 完成阻断。
- Accepted Contracts 中的专项 Gate 继续保留证据价值，但只有直接破坏 correctness、recoverability、replaceability 或 production viability 的问题才升级为 POC blocker。

因此本轮变化是 **POC acceptance boundary narrowing**，不是候选路线扩张、核心领域模型重构或新一轮架构设计。

## 6. 最终结论

当前 P0/P1 架构在完成上述对齐后，与新的 Harness Scope Boundary 一致。

无需重新打开 001～016。

下一阶段应进入 POC；只有实测暴露 correctness、recoverability、replaceability 或 production viability 问题时，才重新打开对应架构项。
