# ARCH-TODO-028 · DBOS 排除决议与 Hatchet 分布式恢复证据

> 2026-10-10；**决策：DBOS = REJECTED / OUT OF SCOPE（商业许可证不符合本平台约束）；Hatchet = ACTIVE POC**。此决议为候选范围约束，**不是 Hatchet 的 Accepted 生产 ADR**。MAF / Temporal / DBOS 的旧 POC 仅保留历史可追溯性，不构成继续评估许可。

## 选型决议（2026-10-10）

**DBOS 不再参与 Agent Harness Platform 的 Process/Durable SPI 技术选型，不再列为备选，不再编排新的 DBOS POC、代码集成或与 Hatchet 的对等竞品验证。** 排除原因：生产要求开源、可私有化、多 Executor/Worker 自主故障接管，而 DBOS 自托管 Conductor 的免费许可不足以满足多 Executor 目标，扩展涉及商业许可。历史 DBOS PostgreSQL 单机恢复 PASS 仍可归档，但不影响 Hatchet 准入流程；不以“寻找替代 Conductor/自行实现 DBOS 多 Worker 协调”继续消耗研发资源。只有用户明确变更开源与许可硬约束时，才能另行提出新 ADR 重启选型。

**下一阶段仅推进 Hatchet 本身的安全恢复、审批等待、CubeSandbox Session/Lease、真实流事件和资源测试。** 未通过门禁仍生产 NO-GO。

## 一、官方资料核实结果

1. DBOS 开源 SDK 可以运行 PostgreSQL 持久工作流和队列，上一轮已实测两个真实 SDK（本地确定性模型）、硬进程退出后新进程恢复。但那**不是 Worker A 不重启、Worker B 自动接管**。
2. DBOS 官方 [FAQ](https://docs.dbos.dev/faq) 明确：多个进程要实现正确工作流恢复需要 Conductor；**自托管 Conductor 免费许可证每应用仅一个 Executor，多 Executor 需要付费许可证**。其 [Self-hosting Guide](https://docs.dbos.dev/production/hosting-conductor/) 标注 Conductor 为 proprietary license。因此 DBOS 不符合当前开源/许可证硬约束，**已正式排除，不再寻找替代收费组件的变通实现**。
3. DBOS [Concurrent Executions](https://docs.dbos.dev/explanations/concurrent-executions) 中的 checkpoint ownership token 防止旧 Worker 持续提交历史，**不保证外部工具副作用 exactly-once**，平台保留 UNKNOWN → Reconciliation → Retry/Abort/Human 契约。
4. Hatchet [主仓库 MIT](https://github.com/hatchet-dev/hatchet/blob/main/LICENSE) 及 [hatchet-embedded Sidecar 源码仓库 MIT](https://github.com/hatchet-dev/hatchet-embedded/blob/main/LICENSE) 均已单独核实。官方 [Embedded Mode](https://docs.hatchet.run/v1/embedded) 支持 Python sidecar 与 checksum 验证，多个 Embedded Engine 可经同一外部 PostgreSQL 共享队列。Python 支持 [DAG](https://docs.hatchet.run/v1/from-temporal-to-hatchet) 与 [Durable Event Wait](https://docs.hatchet.run/reference/python/context)。它们是**公开能力**，不代表多 Worker 实测已通过。

## 二、验证路径与真实状态

| 硬门禁 | DBOS（已排除，仅历史事实） | Hatchet（当前 POC） |
|---|---|---|
| PG 队列 / 两个真实 Agent SDK 顺序交接 | LIVE PASS（上一轮） | **LIVE PASS**：GitHub Actions run 38020725053，Hatchet Embedded v0.110.5 + 本地 PostgreSQL + 两 SDK DAG |
| 单进程硬退出 → 新进程恢复 | LIVE PASS（上一轮） | NOT TESTED |
| **多 Worker A 硬退出且不重启 → B 自动接管** | **REJECTED：不再推进** | **LIVE PASS**：GitHub Actions run 38021093089，两独立 Engine/Worker + 真实 PostgreSQL，安全步骤接管 |
| 持久 WAITING_APPROVAL 不常占 Worker | NOT TESTED | NOT TESTED |
| 外部非幂等工具 ACK 丢失 / UNKNOWN 对账 | NOT TESTED | NOT TESTED |
| 实时 Token SSE / 游标重放 | NOT TESTED | NOT TESTED |
| CubeSandbox / Session / WorkspaceRef / Scope / Fencing | NOT TESTED | NOT TESTED |
| 生产准入 | **REJECTED / OUT OF SCOPE** | NO-GO（待验收） |

> **2026-10-10 实际 CI 更新：** [Hatchet Embedded 真实引擎与双 SDK PASS](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38020725053)：Bundled PostgreSQL 完成 246 项迁移，真实启动 Engine/Worker、Pydantic task、OpenAI task，并以父任务输出作为子任务输入。`remote_model_calls=0`。停止进程出现 `resource_tracker` 信号量回收警告，需单独测 Worker 资源释放；此 PASS 不证明 A→B 自动接管。[外部 PostgreSQL + 双 Engine 强制故障专用测试](../../poc/durable_engine/hatchet_fleet_failover_live.py) 独立执行，其 A→B 恢复结果以随后独立 CI 的真实 PASS 为准。

> **2026-10-10 跨 Worker 实测 PASS：** [External PG Failover CI #38021093089](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38021093089) 实测 A/B 两独立 Engine 连接同一外部 PostgreSQL 16。A 完成准备步骤并进入第二个安全步骤；B 以独立 Engine 启动后 A 进程组 SIGKILL 且不重启。B 恢复原 Workflow，首步未重执行，正在执行的安全步骤由 B 完成，`hatchet.runs.get_run_ref(id).result()` 返回该原运行终态。实际输出 `worker_A_not_restarted=true`、`completed_stage_not_reexecuted=true`、`failed_inflight_safe_stage_recovered=true`、`authoritative_run_result=PASS`。**这不是不透明 SDK Agent Checkpoint，且完全未验证外部非幂等 Tool 自动恢复**。恢复耗时与资源效率尚未基准量测。

**此分支新增：** [真实 Hatchet Embedded DAG + Pydantic/OpenAI 两 SDK 测试](../../poc/durable_engine/hatchet_embedded_live.py) 与 [独立 GitHub CI](../../.github/workflows/hatchet-embedded-poc.yml)、[双 Engine 故障注入](../../poc/durable_engine/hatchet_fleet_failover_live.py) 和 [实际跨 Worker CI](../../.github/workflows/hatchet-fleet-failover-poc.yml)。两 Agent SDK 使用本地确定性 Model，仍实际通过仓库既有 `AgentRuntimeDispatcher`；不能宣称真实 LLM/token stream。下载或启动引擎失败即 CI FAIL，不允许 Mock 回退。

## 三、跨 Worker 下一阶段验收

- **已完成基础 POC：** 两个独立 Engine/Worker、同一 PostgreSQL；A 强杀、B 恢复旧 Workflow ID，已完成准备 Step 不重复。生产侧仍需要平台 Run/Attempt/Execution 的持久 Ownership / Fencing Contract 与真实负载压力。
- A 领取安全可重复工作，确认第一步持久化后，强杀 A **且不重启**；B 在已运行状态下接管，已完成第一步不重做。
- 对已成功但 ACK 丢失的非幂等 Tool，平台必须 UNKNOWN → Reconciliation，不允许自动重执行外部副作用。
- WAITING_APPROVAL、取消/超时、真实 Cube Session 隔离、资源密度和 Token SSE 分开验收，不能以 Embedded DAG 正例取代整个 Gate。

## 四、集成注意

上轮本地 WebCodex 工作树 `agent-harness-platform-aa548030` 中的 DBOS 代码和测试证据只属历史实验，**不要求迁入主线，也不构成 PR #51 合并前置条件**。可按既有仓库清理流程在确认不影响其他未提交工作后处理该临时工作树。本 PR 继续保留 Hatchet 实测及 DBOS 被排除的选型依据，后续只推进 Hatchet 未通过的 P0 Gate。生产依旧 NO-GO。
