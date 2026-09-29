# 安全信任边界与隔离契约

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-006

## 1. 核心定位

本契约只定义平台安全信任边界（Trust Boundary）与隔离语义（Isolation Semantics）。

不在本契约中实现完整 IAM、DLP、MCP Trust、供应链安全、网络策略或 Secret 生命周期。

核心原则：

> 跨越 Trust Boundary 的输入默认不可信；平台通过公开扩展点、Adapter 与外围基础设施完成隔离，不修改底层 Framework 内部实现。

## 2. 信任域（Trust Zone）

V1 至少区分：

~~~text
用户 / 客户端
    ↓
控制平面（Control Plane）
    ↓
Agent Runtime / Tool Runtime
    ↓
Sandbox / Workload
    ↓
外部系统（Model / MCP / Git / API / Internet）
~~~

这些域之间不能因为处于同一企业网络或同一项目而自动互相信任。

## 3. 默认不可信原则

以下内容默认视为不可信输入：

- Repository 内容
- README / 代码注释 / 文档
- Issue / PR 文本
- Tool Output
- MCP 返回
- Browser / Web 内容
- 外部 Model 输出
- 外部 API 返回

这些内容只能作为 Data / Evidence / Context 使用，不能自行升级为 Platform Instruction 或 Policy。

## 4. 指令与数据隔离

平台必须区分：

~~~text
Platform Policy / System Rules
        ↓
Project Instructions
        ↓
User Intent
        ↓
Runtime / Agent Instructions
        ↓
Retrieved / Tool / Repo / Web Content
~~~

低信任级别的数据不得覆盖高信任级别的指令。

具体指令发现、继承与 Project Skill 解析由 ARCH-TODO-021 继续讨论。

## 5. Control Plane 与 Data Plane 隔离

Data Plane 只能产生：

- Result
- Evidence
- Artifact
- Event
- Failure

最终 Run / Step 状态迁移由 Control Plane 决定。

必须保持：

~~~text
Compromised Sandbox
≠ Compromised Control Plane

Compromised Agent Runtime
≠ Global Platform Authority

Malicious Repository
≠ Platform Instruction Authority
~~~

Data Plane 不得绕过 Policy / Approval 自行扩大权限或修改平台业务目标。

## 6. MAF / Framework 映射原则

当前架构遵守“公开扩展点优先”原则：

- MAF 有公开扩展点的能力，通过 Adapter / Middleware / Hook / Provider / Approval 等公开机制映射。
- Framework 不负责的能力放在平台外围。
- 如果某项能力必须 fork、monkey patch、复制内部实现或依赖私有 API 才能获得，则不把该能力作为平台强制能力。
- 不支持的能力显式标记 unsupported / optional。

因此本契约不要求 MAF 原生提供：

- Sandbox 隔离
- Network Policy
- Secret Store
- IAM / RBAC / ABAC
- DLP
- Supply Chain Security

这些由外围平台能力承担。

## 7. 最小权限与爆炸半径

平台安全目标不是假设每个组件永远不会被攻破，而是限制单点失陷后的爆炸半径（Blast Radius）。

原则：

- Participant 只能获得当前任务所需最小权限。
- Sandbox 不能天然访问 Control Plane 内部权限。
- Agent Runtime 不能天然读取组织级或其他 Project 的 Secret。
- Tool / MCP / Repo 内容不能自动升级权限。
- 外部副作用仍必须经过 Capability / Policy / Approval 边界。

具体身份传播与授权模型已由 ARCH-TODO-009 冻结，详见 IDENTITY_AND_AUTHORIZATION_PROPAGATION.md。

## 8. Secret 与网络边界

本契约只冻结原则：

- Secret 默认不直接进入模型上下文。
- Secret 通过受控 Provider / Execution Boundary 注入。
- Network Access 属于 Capability / Policy 边界。
- Agent / Tool 不得自行扩大网络或 Secret Scope。

具体 Secret Scope、Network Policy、Credential Delegation 由后续专项定义。

## 9. 威胁记录模型

Threat Model 只需要统一记录以下信息：

~~~text
Threat
├─ source
├─ target_asset
├─ trust_boundary
├─ attack_vector
├─ impact
├─ prevent
├─ detect
├─ contain
├─ audit
└─ recover
~~~

该模型用于分析和 POC，不要求在 V1 中建立复杂 Threat Engine。

## 10. 不在本契约范围

以下主题继续由独立待办处理：

- Identity / RBAC / ABAC / Delegated Credential → IDENTITY_AND_AUTHORIZATION_PROPAGATION.md
- Environment / OCI Supply Chain Security → 企业 CI/CD / Artifact Registry / Container Security 基础设施负责；Harness 只消费已验证的 Environment metadata / immutable digest
- MCP Trust / Admission → 外部 MCP Governance / Enterprise Tool Governance 负责；Harness 只消费已准入 MCP，详见 MCP_TRUST_OWNERSHIP_BOUNDARY.md
- Data Residency / DLP / PII → ARCH-TODO-018
- Project Instructions / Skills Context → ARCH-TODO-021
- Sandbox 具体网络与隔离实现 → Sandbox Provider / POC

## 11. Accepted Rules

最终冻结：

1. Repository、Tool、MCP、Web、Model Output 等外部内容默认不可信。
2. Instruction 与 Data 必须隔离，低信任数据不能提升为高信任指令。
3. Data Plane 不能拥有 Control Plane 的最终业务状态控制权。
4. 权限遵循最小权限与有限爆炸半径。
5. MAF / Framework 有公开扩展点则 Adapter 映射；框架外能力放外围。
6. 必须修改 Framework 内部才能实现的能力，不进入平台强制基线。
