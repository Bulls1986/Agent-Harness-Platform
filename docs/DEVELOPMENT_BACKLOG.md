# Development Backlog · Agent Harness Platform（2026-10-11）

> **状态：实施任务清单，不是新的架构选型或生产准入。** 以 [架构待办](ARCHITECTURE_BACKLOG.md) 的 Accepted/Decided Contract 为开发依据；实施完成度需按真实环境/CI 验收，不能因文档 DECIDED 直接宣称功能 PASS。
>
> 外部业务消费者的迁移与兼容工作由独立私有工程负责；Harness 本仓库只实现通用平台合同。

**首个实施变更（OpenSpec）**：[minimal-run-closed-loop](../openspec/changes/minimal-run-closed-loop/)：Proposal、四项 Specs（含 Run Inspector）、Design、Tasks 已建立，`openspec validate --strict` 通过；目标为 Docker PG 双库 + Hatchet + Pydantic/OpenAI 两 SDK 的一条真实业务 Run。**Docker PG + 实际 Hatchet/DAG + Pydantic/OpenAI 两 SDK + Run Inspector 的模型级 POC 本地及 CI PASS**（[运行与复盘证据](retrospectives/MINIMAL_CLOSED_LOOP_20261010.md)；[CI 38037718378](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38037718378)）。但这只关闭最小模型闭环，DEV-HC-01～03 和 ARCH-TODO-028 的完整 Receipt/Approval/Cube/高并发门禁仍 OPEN，**不等于生产准入**。

**M1 真实模型 Agent 链路阶段结论（2026-10-11）：** [OpenSpec real-model-agent-closed-loop](../openspec/changes/archive/2026-10-11-real-model-agent-closed-loop/) · [复盘](retrospectives/REAL_MODEL_AGENT_CLOSED_LOOP_20261011.md)。实际 LiteLLM Responses + Pydantic AI → OpenAI Agents SDK + Docker PG + Run Inspector 的结构化需求分析/审核、PG 回放成功（LIMITED LIVE PASS）；故障发现 Worker 定义混用与 1m Task 超时，已版本化、冻结并补负例。**M1 两 SDK 真实 Token SSE → PG 游标续传、Inspector 重启回放和模型-only Worker 确认取消已 LIMITED LIVE PASS**（详见 [SSE 收口复盘](retrospectives/M1_TOKEN_SSE_CLOSEOUT_20261011.md)）；Receipt UNKNOWN/Cube/审批/生产仍 OPEN，不表示 DEV-HC-01～03 完整关闭。

**正式开发路线：** [DEV-M0～M9 总里程碑](DEVELOPMENT_MILESTONES.md)。通用 Harness Runtime/Domain/Cube/Run API 任务在本仓库独立 OpenSpec 管理；业务消费者各自在私有工程中维护迁移实施与验收任务。

## 开发主线与依赖

| ID | 阶段 | 交付及验收定义 | 所依赖的冻结合同 | 状态 |
|---|---|---|---|---|
| DEV-HC-01 | P0 / DEV-M3 | 将 Platform Run/Plan/Step/Attempt + Workflow Segment/Binding 接入真实 Hatchet；失败阻断、可核对 A→B、Replan 新 Plan 与 Segment | [HC-01](references/HATCHET_WORKFLOW_MAPPING_CONTRACT_20261010.md) | **PLANNED；基础 Run 局部已实现，完整 Gate OPEN** |
| DEV-HC-02 | P0 / DEV-M4 | PG Task Facts + Outbox/Inbox + Provider Binding 查询 + Receipt UNKNOWN 对账；SIGKILL/ACK 丢失/乱序与并发重投负例通过 | [HC-02](references/HARNESS_HATCHET_CONSISTENCY_CONTRACT_20261010.md) | **PLANNED；基础 PG/Outbox 局部已实现，完整 Gate OPEN** |
| DEV-HC-03 | P0 / DEV-M5 | Hatchet Worker→ExecutionContext→AgentRuntime/Cube：Scope/Lease/Fencing/WorkspaceRef 重连，跨 Scope Fail Closed | [HC-03](references/HATCHET_WORKER_SANDBOX_BINDING_CONTRACT_20261010.md) | **PLANNED；Cube 专项有技术证据，完整集成 Gate OPEN** |

## 外部消费者的工程边界

外部业务应用及其独立私有仓库负责实际兼容、迁移与产品交付。本 Harness 仅交付版本化公共 API、Agent Runtime/Sandbox/Run/Receipt 通用能力，不保留任何业务消费者的私有仓库地址、代码、内部 Schema、接口清单或源系统资产。

