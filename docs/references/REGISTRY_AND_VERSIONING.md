# Registry 与版本冻结契约

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-007

## 1. 核心定位

本契约不要求建设统一 Registry 服务。

V1 只冻结以下语义：

> 各组件拥有可识别版本；Run 创建时解析为确定版本；Run 生命周期内版本不得漂移。

Registry 在 V1 中是“版本目录能力（Registry Capability）”，不是必须独立部署的中心化产品。

## 2. 需要版本化的对象

至少包括：

- Recipe
- Component / Adapter
- Runtime
- Policy
- Tool / Capability Definition
- Protocol / Schema
- Environment

不同对象可以使用不同版本机制，不要求统一成同一种包管理格式。

## 3. Run 版本冻结

Run 创建时需要把逻辑配置解析为确定绑定。

示例：

~~~text
Run
├─ recipe_version
├─ component_versions
├─ runtime_version
├─ policy_version
├─ tool_versions
├─ protocol_version
└─ environment_version / immutable digest
~~~

Run 一旦开始：

- 已解析版本不可静默变化。
- 新版本发布只影响后续新 Run。
- 运行中的 Run 不做热升级。
- 恢复时仍使用该 Run 已冻结的版本信息。

## 4. Version 与 Immutable Identifier

允许：

~~~text
version
→ 人类可读 / 配置管理

immutable identifier / digest
→ 精确机器绑定
~~~

例如 Environment 继续使用：

~~~text
coding-node24@1.3.0
+
sha256:...
~~~

但 Recipe / Component 如果其 version 记录本身已经不可变，则不要求额外 digest。

## 5. latest 的边界

latest / default 可以用于：

- 配置编辑
- 管理界面
- 新 Run 创建前的版本解析

但不得作为 Run 内最终绑定。

正确流程：

~~~text
latest
→ resolve
→ concrete version
→ freeze in Run
~~~

## 6. Capability 匹配

Component / Runtime 可以声明 Capability，Recipe 可以声明 Requirement。

Run 创建前做轻量匹配：

~~~text
Recipe Requirement
        ↓
Capability Match
        ↓
Satisfied → start
Unsatisfied → reject
~~~

不支持的能力直接返回：

~~~text
CAPABILITY_NOT_SATISFIED
~~~

平台不为了满足 Requirement 去 fork / patch Framework。

## 7. 升级与回滚

升级原则：

- 发布新版本不修改旧版本。
- 新版本默认只影响新 Run。
- 回滚本质上是新 Run 重新选择旧版本。
- 已存在 Run 不因为平台默认版本变化而改变执行绑定。

## 8. 不在本契约范围

本契约不负责：

- 服务发现（Service Discovery）
- Eureka / Consul 类运行时注册中心
- Agent 动态寻址
- 热升级
- 通用包管理器
- 复杂依赖求解器
- 自动版本迁移
- Framework 内部版本兼容实现

## 9. Accepted Rules

1. V1 不要求统一 Registry 服务。
2. 组件必须有可识别版本。
3. Run 创建时解析为确定版本并冻结。
4. latest 不能成为 Run 最终绑定。
5. 运行中 Run 不热升级。
6. 新版本只影响新 Run。
7. Capability 在 Run 开始前匹配，不支持即拒绝，不补齐 Framework 内部能力。

## 10. MCP / Tool Governance Boundary

Tool / MCP 的 trust/admission 生命周期不由本 Registry Contract 管理。外部 MCP Governance 决定哪些 Tool/Server 可以进入平台可用范围；Harness 只要求其 definition/version/binding 可识别，并在 Run 创建时解析为具体版本后冻结。

详见 MCP_TRUST_OWNERSHIP_BOUNDARY.md。
