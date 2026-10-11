# Design · DEV-M6 多 Agent Recipe 与审批验证

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

DEV-M3/M4/M5 相关真实 Gate。映射 HC-01/02/03 + DEV-PDLC-04。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

Recipe/Plan JSON/YAML 版本、跨 SDK A→B→C、Artifact/Evidence 引用、验证失败阻断、WAITING_APPROVAL/INPUT 及任务级恢复；不开发完整 BPMN。

## Test-first and failure injection

正常验收：产品 Agent 完成已验证结构化需求并输出 ArtifactRef → Coding Runtime 与测试 Runtime 分别按冻结 Recipe 执行、保留 Evidence。

安全负例：写侧操作需要审批而尚未批准 → 保持 WAITING_APPROVAL，拒绝执行工具，批准后仅发生一次操作。

## Exit gate

真实 PDLC 需求→Coding→测试串联，后继只接收已验证结果，审批前工具不可执行，失败可恢复。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。