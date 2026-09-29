# MCP Trust Ownership Boundary

> 状态：Accepted Architecture Boundary  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-015

## 1. 核心决策

Tool / MCP 的准入、可信度评估、发布、下线与治理不属于 Harness Platform 核心职责。

> Harness 只消费已经由外部 MCP Governance / Enterprise Tool Governance 准入的 MCP Server / Tool；只要平台可调用，就视为已通过外部治理并可作为受信任能力使用。

Harness 不再建立独立的 MCP Trust Score、Server Risk Level、Marketplace Approval 或二次信任审核模型。

## 2. Harness 仍负责什么

Harness 只负责执行边界：

- 调用前按照现有 Capability / Policy / Approval 判断当前动作是否允许；
- 非 PURE Tool 继续声明 SideEffectClass；
- Credential 仍通过 Credential Provider 最小权限注入；
- Run / Execution 记录实际调用的 server/tool/version/binding；
- 调用结果形成 Result / Evidence / SideEffectReceipt / Trace；
- UNKNOWN 继续按 Reconciliation 处理。

这些是 Harness 的执行正确性与授权职责，不是 MCP 治理职责。

## 3. MCP Governance 负责什么

外部 MCP Governance 负责：

- MCP Server / Tool onboarding；
- server identity / ownership；
- 安全审计与代码/供应链审查；
- 发布、升级、撤销、下线；
- 企业级 allowlist / catalog；
- MCP 自身认证与授权配置；
- Tool definition / schema / scope 的治理；
- 是否允许某个 MCP 被平台发现或调用。

Harness 不复制上述模型。

## 4. 信任含义

“平台可调用的 MCP 默认可信”表示：

- Harness 不对 MCP Server 本身做二次 trust classification；
- 不要求额外 HIGH/MEDIUM/LOW trust level；
- 不要求为 MCP 建立独立审批中心；
- 不要求 Harness 验证 MCP 的代码安全、来源安全或运营治理。

但这不改变全局 Instruction / Data 边界：MCP 返回的业务数据、网页内容、Repository 内容、外部 API 内容仍按其数据来源进入 Context，不自动获得 Platform/System Instruction 权限。

这属于统一 Security Context 规则，不是 MCP 专属不信任模型。

## 5. Version / Binding

MCP / Tool 仍遵守 Registry & Versioning Contract：

- Tool definition/version 必须可识别；
- Run 创建时解析到具体 binding/version；
- Run 内不因治理平台默认版本变化而静默漂移；
- 若外部治理层撤销某 MCP，后续新的敏感调用可通过当前 Policy/Admission 被拒绝。

## 6. 不在 Harness 范围

- MCP Marketplace / Catalog；
- MCP Trust Score；
- MCP Server security review；
- Tool certification；
- MCP package signing / supply chain；
- MCP governance workflow；
- MCP OAuth / authorization server；
- MCP lifecycle management product。

## 7. Accepted Rules

1. MCP Trust / Admission 由外部 Governance 负责。
2. Harness 可调用到的 MCP 默认视为已经过治理准入。
3. Harness 不建立 MCP Trust Score、Risk Level、Marketplace Approval 或二次审核模型。
4. Harness 仍负责当前 Execution 的 Policy / Approval / Credential / SideEffect / Audit 语义。
5. MCP 返回的数据不因 Server 受信任而自动提升为 Platform/System Instruction。
6. MCP version/binding 继续服从 Run 版本冻结规则。
7. 若未来要建设统一 MCP Governance 平台，应独立立项，不进入 Harness Kernel。