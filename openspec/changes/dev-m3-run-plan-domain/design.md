# Design · DEV-M3 领域内核与 Workflow 映射

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

DEV-M1/M2 现有 Run 闭环；HC-01。映射 DEV-HC-01 / HC-01。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

Run/Plan/Step/Attempt 领域事实与状态机、Plan 版本、Replan 新 Segment、Workflow ID Binding，不重写 Hatchet DAG/Queue。

### 第二开发切片：模型-only PURE Replan v1→v2（真实 PG + Hatchet）

- 旧 v1 Provider 的技术状态由实际 Hatchet `runs.get_status(workflow_run_id)` 查询；仅 **COMPLETED** 且不存在 PG RUNNING Step、当前 Platform Run/Plan/Provider Binding 未变化、具备冻结的 Replan Intent 时可原子冻结 Plan v2。CANCELLED/取消 ACK、RUNNING、FAILED、UNKNOWN 或外部查询失败一律 Fail Closed。
- `ReplanV2` 原子创建同 Run 的 Plan v2 / Segment PENDING + 稳定 Command Key；新 Segment 使用单独 Outbox PENDING→DISPATCHING→CONFIRMED，创建 ACK 不明为 BLOCKED_UNKNOWN，不盲目重投。旧 v1 `harness_run.provider_workflow_id` 保留以供历史查询，v2 Provider ID 在 Segment Binding 中单独保存。
- 旧版本的 POC `start_step/finish_step/complete` 增加计划版本防护，避免 v2 提交后旧 Attempt 抢写终态；v2 Worker 准入同时校验冻结版本、PG Segment CONFIRMED 及实际 Hatchet Workflow ID。
- `verify_replan_v2_hatchet.py` 真实运行两个独立 Hatchet WorkflowRun，记录 native v1 COMPLETED、v2 Provider Binding、同 Run 的 PG 事件。此路径只支持 PURE/确定性模型任务，**没有验证运行中 Cancel/TERMINATED、非幂等 Tool/Receipt、真实多 Worker 接管、通用 v2 Step/Attempt 完整终态**；因此不能以此关闭整个 DEV-M3 Gate。

## Test-first and failure injection

正常验收：已有 Run 在执行 Plan v1 时收到经批准的 Replan → 生成 v2 Plan 和新的 Workflow Segment，旧 Plan/Attempt 仅留审计而不会覆盖。

安全负例：旧 Worker 携带旧 Plan Version/Attempt 提交完成事实 → 平台拒绝旧写入，业务终态未被污染。

## Exit gate

一条真实 Hatchet Run 经 Replan 生成 v2 Plan/独立 Segment，旧 Attempt 不得继续完成。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。