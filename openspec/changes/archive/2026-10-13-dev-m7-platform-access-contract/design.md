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

### 第二开发切片：PostgreSQL Run 归属与拒绝原地改绑（真实 PG，非企业身份联调）

- `poc/closed_loop/facts.py` 的 `harness_run` 新增可空 `project_scope` 与 `initiator_principal_id`，使用 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 兼容旧 POC 数据；不会把历史 Run 的项目或发起者伪造补齐。
- 可信创建边界 `PgFacts.create(..., project_scope=..., initiator_principal_id=...)` 仅允许两个字段同时提供合法非空值；原有本地 Inspector 可继续创建无 Scope 的受限 POC Run，**该类 Run 不允许进入正式只读 API**。
- PostgreSQL 触发器 `harness_run_owner_immutable` 拒绝修改已经写入的归属，也拒绝将历史未绑定 Run 原地改绑。Run 状态机更新不触发归属变更。
- `PgRunReader` 从 Harness PostgreSQL 的 `harness_run` 独立读取归属，通过既有只读 `snapshot/events_since` 投影返回载荷；未绑定或不存在的 Run 返回统一 404。
- 完整 HTTP 授权流程仍必须由已验证的外部 Gateway Identity 和当前 Policy 授权结果注入；**本切片只用合成身份，未联调真实 IdP**。不开发匿名回退、Inspector 对外转接、流式 SSE 中途撤权、OSS Artifact 或 Conversation/Turn。
- PostgreSQL 16 CI 新增真实 DB 合同与越权负例，原有 8 项无数据库单测保留。PG 单测绿灯属于 DEV-M7 的受限集成子门禁，非全阶段 Gate。

### 第三开发切片：统一版本化 API / PG Conversation-Run / 授权 SSE 与 ArtifactRef（原定 M7 范围）

- 在现有外部 Gateway SecurityContext、当前 Policy 和真实 PG Run 归属上增加 `create_platform_app`（`/api/v1`），沿用 `create_read_app` 的受信任身份及策略边界；旧版 Run 读取也增加普通用户跨项目内 Initiator 的硬拒绝。无 Header 自报身份、匿名回退或内置 IdP。
- `PgConversationStore` 只新增已批准的 Conversation/Turn、Turn→已有 Run 不可变关联、Artifact 元数据引用（Ref/Digest/Media/Size）；Runtime/Recipe 选择作为冻结 Turn 元数据，**不自建通用 Recipe 引擎或 ToolRuntime**。Turn→Run 链接必须在 PG 核验其 Project/Initiator 与 Conversation Creator 完全一致；重复相同绑定幂等，绑定不同 Turn 409。
- 正式 `/api/v1/runs/{id}/events` 读平台持久化 Event/游标，`/stream` 使用 SSE `id=run:seq`、类型化 Event 与 Last-Event-ID；事件按批重新校验真实 Run 归属和当前策略、撤权中断，不把缓冲历史冒充 live token；与开发用无鉴权 Inspector 路由彻底分离。
- `/api/v1/.../artifacts` 仅返回授权后的 ArtifactRef 元数据（SHA-256/类型/大小），不向未验证的 User 提供可直接访问 OSS 的 Presigned URL；Storage Adapter 的签名分发需经过其独立授权。取消只走平台已持久的 `run.cancel.requested`，没有 Native 终止证据绝不声称业务 CANCELLED。
- `/ui/conversations/{id}` 是使用同源受信任 Gateway Cookies 的简单只读合成验收页面，通过安全 `textContent` 显示 Turn/Run/Result/Step/Tool/Approval/Artifact 元数据；不注入未可信 HTML、Token/Project Header，也不在此自建真实企业 UI。
- 真实 PG + FastAPI TestClient TDD 正反例涵盖两用户同项目隔离、跨项目、撤权、错误游标、SSE 中途撤权、失败后不泄密、跨 Turn 绑定拒绝、ArtifactRef 隐藏 OSS URL、只申请取消；在已有 `dev-m7-access.yml` 新增对应真实 PG+HTTP CI。该测试注入**合成可信 Gateway/Policy 回调**，并非真实企业 IdP、完整 Hatchet Agent Run 创建、OSS 签名或 M7 整阶段最终 Gate。后续原任务 1.1～2.3 是否关闭依实际集成证据而定。

## Test-first and failure injection

正常验收：同一会话内不同 SDK 产生文本、工具、文件和审批事件 → 统一 API/页面关联 Turn/Run/Step、流式进度和最终结果。

安全负例：用户读取其他项目的 Run/SSE/OSS 引用 → 安全拒绝且不泄漏事件/链接。

## Exit gate

在已授权的 API/旧 UI 接入中稳定浏览历史、模型/工具结果和 Artifact/审核，跨用户和跨项目访问拒绝。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。
## 2026-10-13 限定收口裁决

平台可控合同由已验证的 PostgreSQL/Native Hatchet/SDK、注入式可信 Gateway/Policy Port、安全 SSE/ArtifactRef 和已授权结果页构成。合成 Tool/Approval/Artifact 事件只证明 **真实 PG 中的消费投影合同**；企业 IAM、外部 OSS 签名/Tool/审核来源及旧业务 Portal 的真实联测 **NOT VERIFIED**，不可报告为已验收。责任归原 M6/M8/M9 及外部 Owner，不新增任何 M7 引擎。正式证据及例外：`docs/retrospectives/DEV_M7_FINAL_CLOSEOUT_20261013.md`。Production NO-GO。
