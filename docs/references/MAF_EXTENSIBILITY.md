# Microsoft Agent Framework 扩展性评估

> 状态：讨论参考  
> 时间基线：2026-09-29

## 1. 核心结论

如果目标是：

> MAF 覆盖大部分 Agent/Harness 能力，企业平台只补治理、持久化、Sandbox、Artifact/Event 等差异化能力，

那么 MAF 当前扩展性总体较强。

重点不在于“什么都内置”，而在于多数缺口可以通过公开扩展点补齐，而不是必须 fork、patch 或使用 Foundry。

## 2. 主要扩展层

| 扩展层 | MAF 扩展面 | 适合补齐 |
|---|---|---|
| Agent | BaseAgent / custom agent | Codex Adapter、Remote Agent、自定义执行 Agent |
| Model | Chat Client / provider abstraction | LiteLLM、企业模型网关、Provider routing |
| Context | ContextProvider / HistoryProvider | Memory、RAG、Repo Context、用户/租户画像 |
| Middleware | Agent / Function / Chat middleware | Policy、Audit、Guardrail、Cost、Tracing |
| Workflow | Executor / Handler / Graph | Plan、Verify、Replan、Approval、业务状态机 |
| Storage | Session / Checkpoint 抽象 | PostgreSQL、Redis、自有状态库 |
| Hosting | Self-host / Responses / A2A / AG-UI | 自有 Gateway、鉴权、协议转换 |

## 3. 企业能力如何补

推荐通过公开扩展点补：

- PostgreSQL Session Store
- PostgreSQL Checkpoint Store
- Redis History / Cache
- S3/MinIO Artifact Store
- LiteLLM / Enterprise Model Client
- Policy Middleware
- Audit Middleware
- Budget / Cost Middleware
- Context Providers
- Custom Workflow Executor
- Sandbox Adapter

## 4. 不应该全部塞进 MAF 的能力

以下能力仍应属于 Platform Layer：

- Tenant management
- IAM
- Global Policy
- Recipe Registry
- Capability Registry
- Artifact Lineage
- Enterprise Audit
- Global Event Store
- Deployment orchestration
- Organization-wide scheduling / quota

原则：

> MAF 是 Runtime/Harness 实现，不是企业平台领域模型本身。

## 5. Extension Stability 风险

当前需要重点 POC 的不是“能不能扩展”，而是：

> 公开扩展点是否稳定到可以成为长期平台契约。

POC 应至少实现：

- Custom ContextProvider
- Custom SessionStore
- Custom CheckpointStorage
- Custom ChatClient
- Custom Workflow Executor
- Custom Middleware
- Custom Sandbox Adapter

并检查：

- 是否需要 private API
- 是否需要 monkey patch
- 是否需要复制框架内部代码
- 生命周期 hook 是否完整
- streaming 与 persistence 是否能同时工作
- 框架升级后接口是否容易破坏

## 6. 评价

在“不考虑 Java 原生支持”的前提下，当前讨论估算：

- 扩展性：约 8.5 / 10
- 最大优势：缺口大多有合理 public extension point
- 主要风险：API stability / hosting maturity，而不是架构不可扩展

关键 POC 验收条件：

> 企业补齐能力必须尽量仅依赖 public extension points 完成，不 fork、不 monkey patch、不依赖 Foundry。
