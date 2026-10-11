# Design · DEV-M5 Cube 可信执行与 Coding Runtime

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

HC-03 已冻结；DEV-M3/4 联合接管用例。映射 DEV-HC-03 / HC-03。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

SandboxProvider→Cube Scope/Lease/Fencing/WorkspaceRef 绑定、按需分配释放和 OpenCode Coding Guest；模型-only 0 Sandbox，禁止 Host Shell 兜底。

## Test-first and failure injection

正常验收：Worker A 在授权 Cube 中工作后中断 → Worker B 持有新 Lease 绑定同一 Workspace，恢复操作和已有文件。

安全负例：旧 Owner 或其他 Scope 访问 Workspace/执行 Shell → Fencing 和执行权限拒绝，禁止宿主 Shell 旁路。

## Exit gate

真实 Worker A→B 可信重连同 Workspace；跨 Scope 和旧 Owner 被拒，Shell/Git 仅在 Cube。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。