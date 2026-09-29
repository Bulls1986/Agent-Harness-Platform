# 运行时拓扑与参与者模型

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-004

## 1. 核心定位

运行时拓扑（Runtime Topology）是**运行时事实模型（Fact Model）**，不是计划、Workflow 或 Scheduler。

~~~text
计划（Plan / Workflow）
= 应该发生什么（What should happen）

运行时拓扑（Runtime Topology）
= 实际正在发生 / 已经发生什么（What is actually happening / happened）
~~~

运行时拓扑只回答：

- 当前 Run 中有哪些参与者。
- 谁创建了谁。
- 谁拥有谁。
- 谁调用 / 使用谁。
- 谁运行在哪个执行环境。
- 谁仍然活跃、等待、失败或已经退出。

不得用 Runtime Topology 定义业务执行顺序或替代 Workflow。

## 2. 参与者（Participant）

V1 参与者类型至少包括：

- Workflow
- Agent
- Subagent
- Executor
- Sandbox
- Tool Runtime
- MCP Server
- Remote Agent
- Component

Sandbox、MCP Server 等基础设施对象属于 Participant，因为它们需要参与：

- 取消定位
- 故障定位
- Trace 关联
- 成本归属
- 审计
- UI 运行态展示

但它们进入 Topology 不代表每一次调用都形成拓扑变化。

## 3. 参与者最小信息

Participant 至少记录：

- participant_id
- participant_type
- run_id
- owner_participant_id（可空）
- status
- runtime / provider
- location
- started_at
- ended_at

Provider / Runtime 原生 ID 仍只作为 binding / metadata。

## 4. 关系（Relation）

V1 关系保持克制，至少包括：

- OWNS：拥有
- SPAWNS：创建
- CALLS：调用
- RUNS_ON：运行于
- HANDOFF_TO：交接给
- DEPENDS_ON：依赖

关系只表达稳定或半稳定的运行时事实，不表达业务 Workflow 顺序。

## 5. 典型拓扑

~~~text
Run R1
  ↓ OWNS
MAF Workflow
  ↓ SPAWNS
Main Agent
  ↓ SPAWNS
Review Subagent
  ↓ CALLS
Codex Executor
  ↓ RUNS_ON
CubeSandbox S1
~~~

也允许：

~~~text
Main Agent
  ↓ CALLS / USES
MCP Server
~~~

## 6. 动态事实事件

Runtime Topology 由真实运行事件形成，不要求所有参与者预先注册。

典型事件：

- participant.started
- participant.status_changed
- participant.stopped
- participant.failed
- relation.created
- relation.removed

Runtime Topology 是动态事实图，不是静态设计图。

## 7. 不记录高频调用明细

必须严格分层：

~~~text
Runtime Topology
→ 参与者身份 + 生命周期 + 稳定关系
→ 低频

Trace / Span
→ 调用链、时延、依赖
→ 中频

Log / Tool Output / Command Output
→ 具体调用输出
→ 高频
~~~

例如 MCP Server 进入 Topology 只需要记录：

~~~text
MCP Server A = ACTIVE
Agent B → USES / CALLS → MCP Server A
~~~

具体第 N 次 MCP Tool Call 不进入拓扑存储，而进入 Trace / Event / Log。

Sandbox 同理：

- 记录 Sandbox 创建、状态变化、归属关系、销毁。
- 不记录每次 shell command 作为拓扑边。

## 8. Topology 与生命周期的边界

Runtime Topology 不拥有 Run 状态机。

Run 状态仍由 Domain Model 管理：

- PLANNING
- EXECUTING
- VERIFYING
- COMPLETED
- ...

Participant 只需要轻量状态，例如：

- CREATED
- ACTIVE
- WAITING
- STOPPED
- FAILED

禁止在 Topology 中再造一套完整业务状态机。

## 9. 主要用途

Runtime Topology 主要服务：

### 9.1 运行时控制

例如 Run Cancel 时，可依据参与者关系找到仍存活的 Agent / Subagent / Executor / Sandbox。

具体取消传播语义由 ARCH-TODO-016 继续讨论。

### 9.2 故障定位

回答：

- Run 为什么卡住。
- 哪个参与者失败。
- 哪个 Sandbox 已失效。
- 哪个 Subagent 仍在等待。

### 9.3 Trace / Cost / Evidence 关联

Topology 提供“谁属于谁”的关系上下文。

具体调用明细仍进入 Trace / Event / Evidence。

### 9.4 UI 运行态展示

可以展示：

~~~text
Main Agent
├─ Backend Agent ACTIVE
├─ Frontend Agent COMPLETED
└─ Review Agent WAITING
~~~

## 10. 保留策略边界

Runtime Topology 属于运行控制和近期诊断数据，不是长期日志系统。

本契约只要求：

- Run 活跃期间必须可查询当前拓扑。
- Run 结束后应能保留最终拓扑快照与关键生命周期事件。
- 具体保留 7/30/90/180 天等企业 Retention Policy 不在本待办决定。

长期保留策略已由 ARCH-TODO-011 Artifact / Evidence / Log Retention 冻结：Run 完成后保留最终拓扑快照与关键生命周期事实，具体 Payload/详细 Trace 的保留周期由 Retention Policy 决定。详见 ARTIFACT_EVIDENCE_LOG_RETENTION.md。

## 11. 不在本契约范围

ARCH-TODO-004 不负责：

- Workflow / Plan 定义
- Scheduling
- Multi-Agent 协商协议
- Actor mailbox
- Service discovery
- 分布式一致性
- 自动负载均衡
- 取消传播实现
- Retention Policy
- 部署拓扑
- E2E Environment

这些议题若有需要，进入独立 Backlog。

## 12. Accepted Rules

~~~text
Runtime Topology
= 运行时事实记录
≠ Plan
≠ Workflow
≠ Scheduler
≠ 第二套 Control Plane
~~~

同时冻结：

- Sandbox / MCP Server 等基础设施对象属于 Participant。
- Topology 只记录参与者身份、生命周期和稳定关系。
- 高频调用明细进入 Trace / Log，不进入 Topology。
- Topology 用于控制定位、故障分析、Trace/Cost 关联和 UI 展示。
- 具体保留周期由 ARTIFACT_EVIDENCE_LOG_RETENTION.md 的 Retention Policy 统一约束。
