# Design · DEV-M9 生产交付与运营验收

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

DEV-M3～M8 核心 Gate；外部 IAM/运维/安全协作。映射 DEV-M9 / Production GO Gate。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

自托管部署 Runbook、配置/Secret 与 OTel 接入、权限安全/故障恢复/灰度回滚、100 Active Runs 真实资源与性能测量；不自建 IAM/备份平台。

## Test-first and failure injection

正常验收：在确认环境下运行 100 Active Runs 并杀 Worker/断网络 → 记录延迟/吞吐/内存/CPU/Cube 密度及恢复证据，不用 Mock 替代。

安全负例：业务功能通过但权限、Receipt UNKNOWN、隔离或回退 Gate 未通过 → 必须保持 NO-GO 和现网旧端执行权威。

## Exit gate

PDLC 等价、新 Recipe 业务和生产安全/容量三类 Gate 分别全部 PASS，才允许生产 GO。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。