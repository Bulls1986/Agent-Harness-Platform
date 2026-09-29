# 部署独立性与平台绑定风险

> 状态：讨论参考

## 1. 为什么这是一级指标

对企业内部基础平台而言，“框架开源”不等于“生产部署自由”。

真正需要判断的是：

> 从开发 Demo 走到生产后，核心能力是否被迫进入厂商自己的 Control Plane、托管服务、专有数据库、Enterprise License 或云 Runtime。

因此 Deployment Independence 必须作为一级架构门禁。

## 2. 建议拆分检查项

### Runtime Independence

Agent Runtime 能否作为普通进程/容器运行？

### Control Plane Independence

是否必须厂商 Agent Server / Cloud Control Plane？

### State Independence

Session、Checkpoint、Run State 能否存企业自己的数据库？

### Infrastructure Independence

是否可以运行在普通 Docker/Kubernetes？

### Capability Independence

Sandbox、Memory、Search、Artifact 等关键能力是否可以替换？

### Protocol Independence

是否支持标准 HTTP/SSE/WebSocket/A2A/MCP 等可适配协议？

### License Independence

是否存在生产必需能力只有 Enterprise/Commercial License 才有？

## 3. Managed Feature Cliff

定义：

> OSS 版本可以顺利做 Demo，但真正进入生产后，大量关键能力突然只有厂商商业平台才能提供。

常见表现：

- OSS 没有完整 durable execution
- 自托管没有生产级 persistence
- Observability 只能用厂商 SaaS
- 高级 RBAC/SSO 只有 Enterprise
- Scale/Queue/Worker 只能通过平台获得
- Sandbox/Memory 被云服务绑定

## 4. 不同方案讨论结论

### MAF

- Framework 本体部署独立性较好
- Self-host 路线明确
- 使用 Foundry Hosted Agents 后绑定显著增加

### Google ADK

- Core 可自托管
- Java Runtime 友好
- 高级 Runtime/Code Execution/GCP 能力存在云倾向

### OpenAI Agents SDK

- Runtime 可自托管
- 自定义 Tool/Sandbox 可降低绑定
- Hosted Search/Code Interpreter/Managed Codex 等能力会提升 OpenAI 绑定

### Strands

- Library-first
- 无强制 Hosted Control Plane
- 部署独立性高
- 缺点是 Durable Platform 需要自己补

### Temporal

- 自托管与 Cloud 二选一
- 不绑定 Agent/Model/Sandbox
- 部署独立性高
- 运维复杂度也更高

### LangGraph

- OSS 编程模型优秀
- 生产化容易进入 LangGraph/LangSmith Platform 体系
- 本轮因部署平台绑定风险排除

## 5. POC 必问问题

1. 不使用厂商托管平台，核心流程能不能完整运行？
2. 不使用厂商数据库，Run/Session/Checkpoint 能不能落自有存储？
3. 不使用厂商 Sandbox，能不能替换 Docker/E2B/K8s？
4. 不使用厂商模型，能不能走 LiteLLM/Provider Adapter？
5. Worker/服务挂掉后能不能恢复？
6. UI 能不能只依赖自己的协议？
7. 替换 Framework 后，Run/Artifact/Event 能否保留？
8. 私有 K8s 需要部署多少额外基础设施？
9. 是否存在 Enterprise 才有的生产必需能力？
10. 厂商项目停止维护后，企业平台是否还能运行？

## 6. 架构结论

对于平台级基础设施：

> **部署独立性 + 数据独立性 + 协议独立性**

应与功能完整度、可靠性同级，而不是普通非功能指标。
