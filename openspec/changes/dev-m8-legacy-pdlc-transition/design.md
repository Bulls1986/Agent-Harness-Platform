# Design · DEV-M8 现有 PDLC 迁移

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

PDLC-M0 可先启动，后续依赖 M4/M6/M7。映射 DEV-PDLC-01～05；PDLC-M0～M4。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

PDLC-M0 真源码/现网只读盘点→M1 兼容 Facade→M2 Single Writer 影子/灰度→M3 真实 PDLC Recipe→M4 分批切流/回退。保留 OpenCode Coding 和旧会话策略。

## Test-first and failure injection

正常验收：旧用户使用原 URL/SSO 查看历史项目和 Session → 业务对象、会话顺序、附件、资产及授权一致且 Legacy ID 稳定。

安全负例：同一任务切向新 Run 或需要回退 → 同一时刻恰一 Writer，副作用对账完成后才能停止/切回，活动旧会话受保护。

## Exit gate

旧 UI/SSO/项目/历史 Session/Agent/Skill/MCP/权限不退化，新增跨专业 Agent 可用、可回退。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。