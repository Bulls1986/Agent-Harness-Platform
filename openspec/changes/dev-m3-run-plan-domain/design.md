# Design · DEV-M3 领域内核与 Workflow 映射

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

DEV-M1/M2 现有 Run 闭环；HC-01。映射 DEV-HC-01 / HC-01。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

Run/Plan/Step/Attempt 领域事实与状态机、Plan 版本、Replan 新 Segment、Workflow ID Binding，不重写 Hatchet DAG/Queue。

## Test-first and failure injection

正常验收：已有 Run 在执行 Plan v1 时收到经批准的 Replan → 生成 v2 Plan 和新的 Workflow Segment，旧 Plan/Attempt 仅留审计而不会覆盖。

安全负例：旧 Worker 携带旧 Plan Version/Attempt 提交完成事实 → 平台拒绝旧写入，业务终态未被污染。

## Exit gate

一条真实 Hatchet Run 经 Replan 生成 v2 Plan/独立 Segment，旧 Attempt 不得继续完成。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。