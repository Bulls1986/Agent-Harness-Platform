# Identity & Authorization Propagation 契约

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-009

## 1. 核心定位

V1 面向企业内部单组织使用场景，不建设多租户（Multi-Tenant）领域模型，也不自建企业 IAM。

平台只负责：

- 接收企业 IdP / IAM 已完成认证的主体身份；
- 在 Run / Execution 中保留真实发起者；
- 区分发起者身份与实际执行服务身份；
- 将资源、动作、环境等上下文提交给 Policy 做授权决策；
- 通过受控 Credential Provider 向执行平面提供最小权限凭据；
- 对高风险动作形成可审计 Approval / Authorization 事实。

核心原则：

> Authentication 属于企业 IdP / IAM；Authorization Decision 属于平台 Policy 边界；Credential 属于受控 Provider；Agent / Worker / Sandbox 不拥有全局身份权限。

## 2. V1 信任域

V1 以单组织信任域为部署基线：

~~~text
Enterprise IdP / IAM
        ↓
Platform Gateway
        ↓
Harness Control Plane
        ↓
Agent / Executor / Tool / Sandbox
        ↓
External Service
~~~

“单组织”不等于“内部组件互相信任”。

Project、Repository、Environment、Secret、Tool、External Resource 仍必须按最小权限隔离。

V1 不引入 tenant_id 作为强制领域字段。

若未来出现多个独立组织共享同一平台的需求，必须通过新的架构决策单独引入 Tenant / Organization Partition、数据隔离、跨组织管理与审计模型；Cost / Quota / Billing 仍由外部治理系统负责。

## 3. Principal

平台统一使用主体（Principal）表达可认证身份。

V1 至少支持：

- USER：企业用户；
- SERVICE：平台服务、Worker、Automation 或系统身份。

平台不复制 IdP 的用户目录、组织树、Group 生命周期或密码体系。

Provider / IdP 原生 Subject ID 可以映射到 platform principal_id，但映射关系必须稳定且可审计。

## 4. Initiator 与 Executor 必须分离

发起者（Initiator）表示：

> 谁要求平台执行这个 Run / Action。

执行者（Executor Principal）表示：

> 哪个服务、Worker 或自动化身份实际执行某个 Execution。

例如：

~~~text
User U1
→ initiates Run R1
→ Execution E8
→ Worker Service S3 executes
→ Git Provider
~~~

审计必须能够回答：

- 谁发起；
- 哪个服务执行；
- 执行了什么；
- 访问了哪个资源；
- 经过了哪个 Policy / Approval；
- 使用了哪个 credential reference。

不得因为动作由 Worker 实际发出，就丢失真实 Initiator。

## 5. SecurityContext

V1 定义轻量安全上下文（SecurityContext），不升级为新的顶层业务领域树。

建议最小结构：

~~~text
SecurityContext
├─ initiator_principal_id
├─ initiator_principal_type
├─ project_scope?
├─ authentication_context_ref?
├─ initial_claims_snapshot_ref?
└─ delegation_ref?
~~~

说明：

- initiator identity 是 Run 的审计事实，Run 创建后不可篡改；
- project_scope 是可选授权上下文，不等同于 Tenant；
- claims snapshot 只用于审计 / 重放解释，不代表后续动作永久继承当时权限；
- executor/service principal 属于具体 Execution / Runtime 调用事实，应在执行记录中单独记录。

SecurityContext 不进入 Model Prompt 作为可信凭据载体。

## 6. Authentication 边界

企业 IdP / IAM 负责：

- 登录；
- MFA；
- 用户生命周期；
- Group / Directory；
- Token 签发；
- 企业 SSO。

Harness 只验证或消费受信任认证结果，不自建：

- 密码库；
- OAuth/OIDC Server；
- SSO Server；
- SCIM；
- 企业组织目录。

平台可以提供 IdP Adapter，但不得复制企业 IAM。

## 7. Authorization Model

平台授权采用 Policy Decision：

~~~text
Principal
+ Project / Repository / Environment / Resource
+ Action
+ Runtime Context
+ Risk
        ↓
Policy Engine
        ↓
ALLOW / DENY / REQUIRE_APPROVAL
~~~

RBAC、ABAC、Group、Claim、Resource Attribute 都只是 Policy 输入，不要求 Harness 自建完整 RBAC/ABAC 产品。

典型授权输入包括：

- principal；
- project；
- repository；
- branch；
- environment；
- capability；
- action；
- risk level；
- side effect class；
- current policy version。

授权资源边界优先使用已有业务资源，不为了 IAM 再造一套平行 ACL Domain。

## 8. Identity Freeze 与 Authorization Re-evaluation

Run 创建时必须冻结 Initiator Identity 作为不可变审计事实。

但授权不是永久冻结。

对于敏感或有副作用动作：

~~~text
Run created
→ initiator identity retained

later Execution
→ evaluate current authorization
→ ALLOW / DENY / REQUIRE_APPROVAL
~~~

因此：

- Run 启动时有权限，不代表数小时或数天后的高风险 Execution 自动继续有权限；
- 用户被禁用、Role 变化、Project 权限撤销、Policy 更新后，后续敏感动作必须按当前有效授权重新判断；
- 历史 Policy / Claims Snapshot 仅用于解释当时发生了什么，不作为永久授权凭证。

## 9. Credential Propagation

禁止默认采用：

~~~text
User Login Token
→ Agent
→ Model
→ Sandbox
→ Tool
→ External Service
~~~

用户长期登录 Token / Refresh Token / 企业 SSO 凭据默认不得进入：

- Model Context；
- Agent Prompt；
- Repository 内容；
- Sandbox filesystem；
- Tool 参数日志；
- Artifact。

外部服务访问通过 Credential Provider 获取受控凭据。

优先：

~~~text
Execution Request
→ Policy Decision
→ Credential Provider
→ short-lived / least-privilege credential
→ Tool / Sandbox / External Service
~~~

Credential 至少应尽可能限制：

- target resource；
- action / permission；
- environment；
- expiration；
- execution / project scope。

具体 Secret Manager 产品与生命周期不在本契约内冻结。

## 10. Delegated Credential

只有外部系统确实要求“代表用户（On-Behalf-Of）”执行时，才使用 Delegated Credential。

Delegation 必须：

- 可追溯到 Initiator Principal；
- 有明确 resource/action scope；
- 有有效期；
- 不扩大原用户权限；
- 不允许 Agent 自行申请更高权限；
- 通过 Credential Provider / Policy Boundary 获取。

默认优先使用 Service Identity + Policy + Initiator Audit，而不是全链路 User Impersonation。

## 11. Approval Authority

Approval 是正式授权事实，不能只保存 approved=true。

建议至少记录：

~~~text
ApprovalDecision
├─ approval_id
├─ run_id
├─ execution_id?
├─ requester_principal_id
├─ approver_principal_id
├─ resource
├─ action
├─ policy_version
├─ decision
└─ decided_at
~~~

硬规则：

- Approver 必须是经过认证的 Principal；
- Approval 是否有效必须由 Policy 判断；
- Agent / Worker / Sandbox 不能把自己的输出当作真实人工 Approval；
- 是否要求不同于 Initiator 的独立审批人、特定 Role、多人审批等，由 Policy 配置，不写死进 Harness Kernel。

## 12. Project / Repository Authorization

Harness 不复制 Git / Repository Provider 的完整 ACL 系统。

平台负责：

~~~text
Initiator / Service Principal
+ Project Context
+ Repository / Branch / Action
→ Policy
→ Credential Provider
→ scoped repository credential
~~~

Repository Provider 自身权限仍然是最终外部约束之一。

Project Manifest 定义“项目包含什么”，不自动意味着“当前 Principal 对所有 Repository 都有写权限”。

## 13. Audit Attribution

至少要能形成：

~~~text
Initiator
→ Run
→ Step / Attempt
→ Execution
→ Executor Principal
→ Policy Decision
→ Approval?
→ Credential Reference
→ External Side Effect
~~~

审计记录不得保存明文 Secret。

授权失败、Approval 拒绝、Credential 获取失败必须形成明确事件 / Failure Evidence。

## 14. 不在本契约范围

本契约不实现：

- Multi-Tenant data partition；
- 企业 IAM / User Directory；
- Group Sync / SCIM；
- OAuth/OIDC Server；
- 完整 Role Management UI；
- Secret Manager 产品；
- DLP / PII；
- Tool / MCP Trust；
- Network Policy；
- Repository ACL 镜像；
- Cross-organization administration。

相关安全专题继续由独立待办处理。

## 15. Accepted Rules

最终冻结：

1. V1 是单组织信任域，不引入 Tenant 一等领域模型。
2. Authentication 由企业 IdP / IAM 负责，Harness 不自建账号认证体系。
3. Initiator Identity 与 Executor / Service Identity 严格分离，并贯穿审计链。
4. Run 固化 Initiator Identity 作为历史事实，但敏感 Execution 必须基于当前权限重新授权。
5. RBAC / ABAC / Group / Claim 只是 Policy 输入；平台拥有 Authorization Decision，不复制企业 IAM。
6. 用户长期登录 Token / Secret 默认不得传播到 Agent、Model、Sandbox。
7. 外部访问优先通过 Credential Provider 提供短期、最小权限、资源范围明确的 Credential。
8. Delegated Credential 仅用于确有 On-Behalf-Of 需求的场景，且不得扩大原主体权限。
9. Approval 必须绑定真实 Principal、Resource、Action 与 Policy；Agent / Worker 不能自行伪造 Approval。
10. Project / Repository 授权通过 Policy + Provider Credential 组合完成，不建设平行 Repository ACL 系统。
