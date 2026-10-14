# Design · DEV-M6 多 Agent Recipe 与审批验证

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

DEV-M3/M4/M5 相关真实 Gate。任务追踪 DEV-RECIPE-01（遵守 HC-01/02/03），不以外部消费方业务实现为前置。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

Recipe/Plan JSON/YAML 版本、跨 SDK A→B→C、Artifact/Evidence 引用、验证失败阻断、WAITING_APPROVAL/INPUT 及任务级恢复；不开发完整 BPMN。

## Test-first and failure injection

正常验收：合成任务的规划 Agent 完成已验证结构化输出和 ArtifactRef → Coding Runtime 与验证 Runtime 按冻结 Recipe 执行，并持久保留 Evidence。

安全负例：写侧操作需要审批而尚未批准 → 保持 WAITING_APPROVAL，拒绝执行工具，批准后仅发生一次操作。

## Exit gate

使用合成通用任务验证真实跨 SDK 三 Agent Recipe；后继只接收验证通过的结果，审批前工具不可执行，任务级失败可恢复。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。