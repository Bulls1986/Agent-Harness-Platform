# DEV-M7 版本化公共 API · 组合开发切片

该目录实现现有 DEV-M7 原计划的可复用 Python/FastAPI **入口构件**（不是完整独立企业 Portal，也不是 Inspector 本地调试接口）。

## 使用范围

`create_platform_app(...)` 在受信任 Gateway 认证和当前 Policy 注入后，公开以下版本化 API：

| API | 用途 |
| --- | --- |
| `POST /api/v1/conversations` / `GET /api/v1/conversations` | 当前用户范围内创建、列出会话 |
| `GET /api/v1/conversations/{id}` | 持久化会话、Turn、关联 Run、所选 Agent/RecipeRef |
| `POST /api/v1/conversations/{id}/turns` | 创建有持久 PG 事实的 Turn |
| `POST /api/v1/turns/{id}/runs` | 受信任的 Runtime/Recipe 适配器核准已冻结选择后，携带 `Idempotency-Key`（必填）原子创建 scoped Run/Outbox/Turn Binding，并委托已存在的真实 Hatchet 执行入口；相同 Key 重试只返回原 Run，不盲重派 |
| `POST /api/v1/turns/{id}/runs/{run_id}` | 将已经由可信 Harness 执行入口创建的 Run 关联到 Turn；验证 PG Owner/Scope，不支持凭 HTTP 构造 Provider Binding |
| `GET /api/v1/runs/{id}` / `.../events` | Run/已持久化 Typed Event 与游标 |
| `GET /api/v1/runs/{id}/stream` | 授权 SSE，Last-Event-ID 格式 `{run_id}:{seq}`，每批重新验权，断连后可继续 |
| `POST /api/v1/runs/{id}/cancel` | 仅记录 `CANCEL_REQUESTED`，不伪造 Native Worker Terminated/Cancel ACK |
| `GET /api/v1/runs/{id}/artifacts` / `GET /api/v1/artifacts/{id}` | 仅授权返回 Digest/Media/Size 等 Metadata，无 OSS Presigned URL |
| `GET /ui/conversations/{id}` | 只读、纯 DOM textContent 的简洁会话/结果页面 |

## 集成方式

外部可信 Gateway/IdP Adapter **必须**在服务端验证身份，注入 `resolve_context(request) -> SecurityContext`；外部 Policy Adapter **必须**提供 `authorize(context, binding, action) -> bool` 与 `authorize_create(context, action) -> bool`，只接受显式 `True`。不支持从用户自报的 `X-Principal-Id`、`X-Project-Scope` 获取身份，也没有默认匿名或测试口令回退。

`PgConversationStore(PgFacts())` 与 `PgRunReader(PgFacts())` 使用 Harness 的 PostgreSQL 事实；`cancel_run` 应通过已有受信任控制层 Port 注入，如已审核的 `PgFacts.request_cancel`。运行时代码不依赖企业业务仓库、Hatchet History 表、OSS 私钥或第二套 Scheduler。

本阶段**已经补充**通过受信任 Runtime Adapter 发起 Run 的版本化命令入口：注入 `start_run(run_id, frozen_prompt, outbox_command_key)`、`model_binding()` 和 `admit_recipe(agent_ref,recipe_ref)`；**只有 Adapter 明确支持的 Agent/Recipe** 可进入已有 Hatchet 真实执行链。无执行适配器、未知 Recipe 或缺少幂等键均直接拒绝。首次创建 Run/Turn 绑定/Outbox 在同一个 PG 事务内；同 Key HTTP 重试不二次派发，若首次提交 ACK 不明则保留 Run ID 进入对账。该 API 不负责 Worker Queue/SDK Session 或替代 Hatchet；企业 IdP/Policy E2E、实际 OSS 授权下载和既有 Portal UI 接入仍是原 DEV-M7 未验收条件，非生产功能。

## 官方验证

PR [#86](https://github.com/Bulls1986/Agent-Harness-Platform/pull/86)：

- [真实 PostgreSQL 16 + HTTP API + M7 OpenSpec CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300342)：**22/22 PASS**（14 项 PG HTTP + 8 项授权单测，0 SKIPPED）。
- [架构约束 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300381)：**SUCCESS**。
- 复盘：[DEV_M7_PLATFORM_API_INTEGRATION_20261013.md](../../docs/retrospectives/DEV_M7_PLATFORM_API_INTEGRATION_20261013.md)。

- 新增真实 PostgreSQL 启动合同 `poc.platform_access.test_public_run_launch_pg` 和真实 Native 验收 `poc.platform_access.verify_public_api_hatchet`；后者在现有 `closed-loop-poc.yml` 中执行真实 Hatchet Embedded + Pydantic AI SDK → OpenAI Agents SDK，要求 API 返回的 Run、Workflow ID、Step 结果和 SSE 来自同一个真实执行。**最终结果以该 PR 官方最新 Head CI 为准**；使用本地确定性模型不等于外部真实 LLM 或企业 IdP 已通过。

**状态**：DEV-M7 ACTIVE；平台 Production NO-GO。不同版本及用户/项目访问必须继续遵循原 OpenSpec 和 G01/G10/G11/G15/G20。
