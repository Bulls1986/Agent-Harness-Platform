# OpenAI Agent / Harness 能力梳理

> 状态：讨论参考  
> 时间基线：2026-09-29

## 1. OpenAI 相关开源/开放能力

讨论中重点关注：

- **OpenAI Agents SDK**：通用 Agent Runtime / orchestration SDK。
- **Codex OSS**：面向软件工程的 Coding Agent / Coding Harness。
- **Guardrails**：输入输出治理与安全能力。
- **Evals**：评测框架。
- **ChatKit / Apps SDK UI**：AI Chat / App UI 能力。
- **Triton**：GPU Kernel/Compiler 基础设施。
- **gpt-oss / Harmony**：开放模型与对话/工具格式相关能力。

## 2. Agents SDK 与 Codex 的区别

核心结论：

- **Agents SDK = 造 Agent 的框架 / Runtime**
- **Codex = 已经造好的 Coding Agent / Coding Harness**

Agents SDK 更偏通用抽象：

- Agent
- Runner
- Tool
- Handoff
- Session
- Guardrail
- Structured Output
- Sandbox Integration
- Tracing

Codex 已围绕软件工程实现大量专用行为：

- Repository exploration
- File read/write
- Shell
- Patch/edit
- Git
- Test/build
- Diff review
- 长任务迭代
- Coding-specific context management

~~~text
Agents SDK
  = Agent Runtime / primitives

Codex
  = Software Engineering Harness
~~~

## 3. Agents SDK 与 Sandbox

讨论中的目标结构：

~~~text
Agent
  ↓
Agents SDK
  ↓
Sandbox abstraction
  ↓
CubeSandbox / Docker / K8s / other provider
~~~

对企业平台而言，Sandbox 应继续通过自有 `SandboxProvider/SPI` 抽象，而不是让业务 Workflow 绑定具体 Provider。

## 4. Plan 能力

Agents SDK 可以支持模型自主规划，但若要求：

~~~text
Plan → Execute → Verify → Replan
~~~

具备可审计、可恢复、可持久化、可人工介入与步骤追踪，则 Plan 生命周期应该由 Harness/Control Plane 显式管理，而不能只存在模型上下文中。

## 5. OpenAI-managed Codex harness 与 OSS 的边界

~~~text
OpenAI-managed Codex Harness
  = 托管的长任务/session/orchestration/context/recovery

Codex OSS
  = 可复用/研究的本地 Coding Agent / Harness

Agents SDK
  = 通用 Agent Runtime / primitives
~~~

缺少 managed harness 时，系统仍然可以工作，但 Durable State、Recovery、Workflow、Retry/Replan、Context、Long-running lifecycle、Subagent policy 等责任需要由自有 Control Plane 或 durable workflow 基础设施接管。

## 6. 对平台架构的启示

OpenAI 能力应该成为 Adapter：

~~~text
Planner SPI
  └─ AgentsSdkPlanner

Executor SPI
  ├─ AgentsSdkExecutor
  └─ CodexExecutor

Sandbox SPI
  ├─ CubeSandbox
  └─ Docker / K8s fallback
~~~

最终原则：

> OpenAI 能力是 Runtime / Executor / Provider 的实现候选，而不是企业 Harness Platform 的控制权归属。
