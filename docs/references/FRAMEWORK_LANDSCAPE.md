# Agent / Harness Framework 首轮技术比较

> 状态：讨论参考  
> 本文记录为什么首轮最终只选 MAF、Google ADK、Temporal 进入 POC。

## 1. Microsoft Agent Framework (MAF)

关注点：

- Agent/Harness
- Workflow
- Self-host
- Session
- Approval
- Context/Compaction
- Durable Extension
- Responses / A2A / AG-UI
- Shell/Sandbox

优势：

- Harness 与 Workflow 集成度较高
- 自托管路径相对清晰
- 可作为一体化路线验证

风险：

- Durable/Hosting 部分需要关注版本成熟度
- 生产 Session/Checkpoint Store 需要补齐
- Sandbox 仍建议保留平台自有 SPI
- 使用 Foundry 等托管能力后平台绑定上升

补充结论：

- 不再把 Java Native 作为评分项。
- MAF Memory/Context、Middleware、Storage、Workflow、Hosting 的公开扩展面与目标架构高度匹配。
- 当前 POC 前估算：原生覆盖约 80%，架构适配约 89%（±5%，待 POC 验证）。
- 第一优先验证点是：企业补齐能力能否全部通过 public extension points 完成，不 fork、不 monkey patch、不依赖 Foundry。

首轮结论：**进入 POC，当前第一优先**

## 2. Google ADK

关注点：

- Java 原生支持
- Agent / Runner / Session / Event
- Sequential/Parallel/Loop
- A2A / MCP
- Streaming
- Container Code Execution
- Artifact / Session

优势：

- Agent / Runner / Session / Event 基础完整
- A2A / MCP / Streaming 能力较好
- 协议边界较清晰

风险：

- 高级能力存在明显 GCP/Agent Runtime 倾向
- 需要重点核验非 GCP、自有存储、自有 Sandbox 路线

首轮结论：**进入 POC**

## 3. Temporal

Temporal 不是 Agent Framework，而是 Durable Execution 基础设施。

适合承担：

- Workflow
- Durable state
- Retry
- Timeout
- Queue
- Worker
- Recovery
- HITL
- Scheduling

优势：

- Control Plane 与 Agent Runtime 可完全解耦
- Java 成熟
- 自托管能力明确
- 不绑定模型、Agent Framework 或 Sandbox

风险：

- 引入独立基础设施
- 运维复杂度增加
- Workflow determinism / replay 有额外开发约束

首轮结论：**进入 POC**

## 4. OpenAI Agents SDK

定位：轻量通用 Agent Runtime。

优势：

- Agent primitives 简洁
- Sandbox integration
- Structured output
- Session / tracing
- 与 OpenAI 生态集成自然

风险：

- 非 Java
- Durable Control Plane 需要另补
- 使用 Hosted Tools/Managed capability 后 OpenAI 绑定会上升

结论：**保留为 Runtime 组件候选，不单独做首轮 Control Plane POC**

## 5. Codex OSS

定位：Coding Agent / Coding Harness。

优势：

- 软件工程执行成熟
- Repo/Shell/Patch/Test/Git 工作流价值高

风险：

- 垂直于 Coding
- 不应承担通用 Platform Control Plane

结论：**保留为二阶段 Coding Executor 候选**

## 6. Strands Agents

定位：轻量 Agent Runtime / library。

优势：

- 强调 library, not platform
- 部署绑定低
- provider 开放
- Hook/Plugin 模型适合治理扩展

风险：

- 不提供 Durable Control Plane
- 需要 Temporal 或自有 Kernel 组合

结论：**保留为二阶段 Runtime 候选**

## 7. LangGraph / Deep Agents

能力本身很强：

- State/Graph
- Checkpoint
- HITL
- Durable
- Deep Agent harness
- Planning / Todo / Subagent / Context

但讨论中的主要问题不是开发能力，而是企业生产部署路径：

- 容易形成第二套 LangGraph/LangSmith Platform 控制平面
- 自托管依赖和生产运维较重
- OSS → Platform 存在明显 Managed Feature Cliff
- 企业内建时与“控制权掌握在自身平台”目标冲突

首轮结论：**排除，不进入 POC**

## 8. CrewAI / PydanticAI

- CrewAI：业务 Agent/Flow 层更高，存在 OSS → AMP 的生产平台断层风险。
- PydanticAI：轻量、类型安全，适合 Runtime/应用开发，但不作为当前平台 Control Plane 主候选。

## 9. POC 前匹配度估算

| 方案 | 原生覆盖率 | 架构适配率 | 当前优先级 |
|---|---:|---:|---|
| Microsoft Agent Framework | ~80% | ~89% | 1 |
| Temporal + 可替换 Agent Runtime | ~72% | ~92% | 2 |
| Google ADK | ~68% | ~75% | 3 |

> 以上为架构映射估算，按 ±5 个百分点理解，最终结论只以统一 POC 实测为准。

## 10. 首轮最终 POC

~~~text
POC-A: Microsoft Agent Framework
POC-B: Google ADK
POC-C: Temporal + 可替换 Agent Runtime
~~~

对比重点不再是“能不能调用工具/做 Agent”，而是：

- 自托管
- Durable
- 状态自主
- Sandbox 可替换
- Provider 可替换
- UI 协议可桥接
- 故障恢复
- HITL
- License/Managed Feature Cliff
