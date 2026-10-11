# Design · DEV-M7 统一 API、Chat 与用户交互

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

DEV-M2 Typed SSE 和 DEV-M3 持久 Run 所属事实构成完整 API 的内部依赖；当前可信身份由外部 Gateway/IAM Adapter 提供，可并行完成访问合同与回归。DEV-API-01 负责 M7 公共 API；下游 DEV-M8 独立合成客户端须依赖该版本化 API，不反向约束 M7；任何私有业务消费者都不构成前置。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

统一 Conversation/Turn/Run、文件引用、Typed SSE、Run/Agent/Recipe 选择、项目与授权上下文输入和用户能看懂的执行结果；Inspector 仅调试，企业 IAM 仍外部。

### 第一开发切片：受控 Run 只读访问（非生产集成）

- `poc/platform_access/authorized_reads.py` 提供一个与 Local Inspector **分离**的 read-only FastAPI facade。无默认匿名模式，不自行登录或发 Token。
- `resolve_context(Request) -> SecurityContext` 只能由已验证的外部 Gateway/IdP Adapter 提供；HTTP 传入的主体、项目 Header **不作为身份来源**。
- `RunReader.binding(run_id) -> RunBinding` 必须取平台持久化的 Run 所属 Project / Initiator，不得使用模型或 Provider ID 猜测。`RunReader.snapshot/events_since` 为读投影，不能变更 Run 事实。
- 拒绝条件：缺失身份、缺 Project Scope、Project 不匹配、Run ID 不一致、Policy 未明确返回 `True`。未授权与不存在 Run 均以相同的 404 响应隐藏内容；策略不可用返回 503，**不得**回退匿名。
- 当前 Policy 每次读取重新评估 `run.read` / `run.events.read`。此阶段不发行 OSS 链接，也不允许用户自行接入 SSE；后续 SSE 需重验权限和取消下游订阅，不能直接复用 Local Inspector 的无鉴权路由。
- 单元测试使用内存 Read Adapter 验证 HTTP 策略边界，**未对接真实 PostgreSQL 与 IAM**；仅代表可审查的接口骨架，不构成 Gate 2.1 PASS。

## Test-first and failure injection

正常验收：同一会话内不同 SDK 产生文本、工具、文件和审批事件 → 统一 API/页面关联 Turn/Run/Step、流式进度和最终结果。

安全负例：用户读取其他项目的 Run/SSE/OSS 引用 → 安全拒绝且不泄漏事件/链接。

## Exit gate

在已授权的 API/旧 UI 接入中稳定浏览历史、模型/工具结果和 Artifact/审核，跨用户和跨项目访问拒绝。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。
