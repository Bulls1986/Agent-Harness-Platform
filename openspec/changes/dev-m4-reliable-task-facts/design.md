# Design · DEV-M4 持久一致性、Receipt 与任务级恢复

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

DEV-M3 Domain/Segment；HC-02。映射 DEV-HC-02 / HC-02。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

PG transactional Outbox/Inbox、Provider 查询/ACK-loss Reconciliation、Tool Intent/Receipt/UNKNOWN、故障注入后的任务级恢复；不能以跨库 2PC 或自行重建 Scheduler 解决。

## Test-first and failure injection

正常验收：Provider Workflow 已接受而 Harness 创建调用超时 → 进入 BLOCKED_UNKNOWN，查询 Provider 并对账，不盲目重复创建。

安全负例：外部工具已经写入，Worker 在返回 Receipt 前 SIGKILL → 核对实际副作用；未知则人工介入或保持阻断，绝不自动重放。

## Exit gate

真实 PG/Hatchet 和非幂等工具在丢 ACK/SIGKILL/并发重试下可核对且不盲目重复副作用。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。