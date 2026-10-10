# Proposal: 最小可运行 Run 闭环（Docker PostgreSQL + Hatchet + AgentRuntime）

## Why

Agent Harness Platform 已冻结 HC-01/HC-02/HC-03，但当前仅有相互独立的 Hatchet、AgentRuntime、Cube POC。缺少可由一个平台 Run ID 贯穿创建、持久化、调度、Agent 间交接与完成裁决的端到端证据。先做最小真实闭环，避免提前开发完整 Control Plane。

## What Changes

- 初始化 OpenSpec，把平台业务状态、引擎技术状态、Agent SDK 执行边界固化为可验收的规范与任务。
- Docker Compose 提供 **PostgreSQL 16**；在同一 PG 容器内使用独立 `hatchet_poc` / `harness_poc` **数据库**。Hatchet 只管理其 Workflow/Task 技术历史，Harness 只持久化最小 Run/Step/Attempt/Outbox/Binding/Event 事实；不使用 SQLite 作为运行目标。
- 真实 Hatchet Embedded Worker/DAG 驱动 Pydantic AI → OpenAI Agents SDK 两个公开 Runtime Adapter；使用公开确定性本地 Model，**零外部模型调用**。平台验证前序输出后交接，记录独立业务状态及可靠事件序列。
- 创建 Run 与 Outbox 同库事务；Provider ID 只作为 Binding；已知 ACK 可完成关联；创建响应未知则标记 BLOCKED_UNKNOWN，不盲重建第二条 Workflow。
- Model-only 工作不创建 Sandbox；后续在 HC-03 的 Tool/Shell 路径中增加 Cube Scope/Lease/Fencing，不能用本轮无 Sandbox 通过冒充真实隔离验收。
- 添加本地与 CI 回归、故障负例、OpenSpec 校验与明确 POC 范围说明。
- **Run Inspector 是本轮最小闭环的必验收功能**：提供轻量本地网页，能发起真实 Run、查看其状态、各 Agent Step/Attempt、Provider Workflow Binding 与 PG Event 时间线；刷新/重开网页从 PostgreSQL 读取，不能依赖浏览器内存假数据；不建设正式 Portal。

## Capabilities

### New Capabilities

- `run-workflow-binding`: 真实 Hatchet DAG 和平台 Run/Step/Attempt 映射、前序验证、终态裁决。
- `durable-run-facts`: Docker PG 双库隔离、最小 Task Facts、Outbox/Provider Binding/事件、未知 ACK 安全阻断。
- `runtime-handoff`: 两个公开 SDK 的受控模型执行、跨 Runtime 输出交接、Model-only 零 Sandbox。
- `run-inspector`: 本地调试 UI 与 API，启动真实 Run、轮询状态、从 PostgreSQL 读取状态与有序事件，并验证刷新后持久化。

### Modified Capabilities

无。此前没有 OpenSpec 基线 Specs；架构 ADR/Accepted Contracts 不在本变更中降级。

## Impact

- POC: `poc/closed_loop/`（含 Run Inspector API/静态页面）、复用 `poc/runtime_spi/` 与原 `poc/durable_engine/`。
- 本地: `compose.yaml`、`poc/closed_loop/Dockerfile`；不触碰/清理已有 Docker 容器或卷。
- 规范: `openspec/config.yaml`、本变更 `proposal.md/specs/design.md/tasks.md`。
- 自动化: 针对此闭环的 PG 集成 CI/回归，必要时增量更新 `docs/DEVELOPMENT_BACKLOG.md`。
- **非目标**：生产 PG Schema/HA、真实云模型或 Token SSE、Cube 真实跨 Worker Lease、Approval/Durable Wait、非幂等外部副作用、100 并发、PDLC 存量迁移（仍属于 DEV-PDLC-01～05）。

## Acceptance

一次独立真实运行在 Docker PostgreSQL 中形成同一业务 Run 的 Outbox/Binding、Hatchet Provider Workflow、两 SDK 实际执行、前后依赖验证、单调可重放业务事件和最终 COMPLETED；至少一项故障/重复/非法依赖负例 Fail Closed。未通过的门禁必须显示 NOT_TESTED/BLOCKED，不以文件存在等同可运行。

**可见性硬门禁**：在浏览器打开本地 Run Inspector、提交 Prompt、看到业务 Run 状态及两个真实 SDK 的执行事件、最终 COMPLETED，并在浏览器刷新/服务重启后依然能从 PostgreSQL 查询同一 Run；无后端引擎/数据库时页面必须明确报错，不能演示预制的成功动画。