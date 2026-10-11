# Design · DEV-M7 统一 API、Chat 与用户交互

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

DEV-M2 Typed SSE 和 M3 领域事实；可与 M5/M6 并行。映射 Conversation/Turn/Run 接口；DEV-CONSUMER-02 前置。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

统一 Conversation/Turn/Run、文件引用、Typed SSE、Run/Agent/Recipe 选择、项目与授权上下文输入和用户能看懂的执行结果；Inspector 仅调试，企业 IAM 仍外部。

## Test-first and failure injection

正常验收：同一会话内不同 SDK 产生文本、工具、文件和审批事件 → 统一 API/页面关联 Turn/Run/Step、流式进度和最终结果。

安全负例：用户读取其他项目的 Run/SSE/OSS 引用 → 安全拒绝且不泄漏事件/链接。

## Exit gate

在已授权的 API/旧 UI 接入中稳定浏览历史、模型/工具结果和 Artifact/审核，跨用户和跨项目访问拒绝。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。