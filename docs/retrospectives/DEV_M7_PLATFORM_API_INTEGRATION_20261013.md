# DEV-M7 · PostgreSQL Conversation/Turn、版本化 API、授权 SSE 与 ArtifactRef 联合切片（2026-10-13）

## 范围与事实 Owner

本工作属于原始 DEV-M7 / DEV-API-01 / `dev-m7-platform-access-contract` 已规划范围，不新增里程碑、Agent 调度器、企业 IAM/Policy 产品、OSS 签名服务或特定业务消费者源码。继续复用已在 Main 的受信任 `SecurityContext` / `RunBinding` / `PgRunReader` (PR #65/#67)，M2 持久化 Typed Event、M3 版本化 Run 与 M4 一致性事实不发生 Owner 变更。

## Red → Green 记录

- **Red**：先写真实 PostgreSQL、HTTP 集成合同 `poc.platform_access.test_platform_api_pg`；最初 `PgConversationStore` 和 `create_platform_app` 均不存在。增加的新测试明确要求持久 Conversation→Turn→Run、同源用户可读页面、跨用户/跨项目 404、SSE Cursor/撤权和 ArtifactRef 不漏存储链接。
- **Green**：按最小职责实现 `PgConversationStore` 的 PG 表与作用域/不可变 Turn→Run 绑定，`create_platform_app` 中版本化 `/api/v1`、Type SSE、游标、授权元数据 ArtifactRef、用户可读的只读 HTML 和持久取消请求；不新增另一个 Provider/Task 状态机。
- **现有安全合同增强**：即使外部 Policy 误允同项目普通用户的 Run，当前 USER 必须是 PG 记录的 Initiator；SERVICE 仍由外部 Gateway + 当前 Policy 决定。任何伪造 Header 都不作为身份来源。为 SSE Last-Event-ID 限制整数长度，避免超长数值导致异常。
- **失败发现与修复**：初版跨项目 HTTP 负例发送不完整 Turn JSON 导致 FastAPI 在权限判断前返回 422；测试改用合法请求，确保真正覆盖越权 404；未修改用户实际请求合同以绕过错误。真实身份适配器没有接入企业 IdP，所以此项只能称合成身份 + 真实 PG/HTTP 集成，**不是**企业 Gateway/Policy Live PASS。

## 本切片验证范围

| Gate | 目标 | 证据 |
|---|---|---|
| 已有授权单元 | 8 项缺身份、权限撤销、跨项目、伪造 Header、游标 | `poc.platform_access.test_authorized_reads` 原 CI |
| 已有 PG Read | 5 项真实 PG Run Scope/Owner immutability | `poc.platform_access.test_pg_reader` 原 CI |
| 新 PG + HTTP | 持久 Conversation/Turn/Run 关系、相同 Run 不得绑定另一 Turn、跨项目与同项目不同 User 404、Typed SSE 游标和撤权、Artifact 元数据、用户可读页面、Cancel Requested 非 CANCELLED | `poc.platform_access.test_platform_api_pg`，本 PR 最新 Head CI 为准 |
| 架构/Spec | G01/G03/G08/G10/G11/G12/G15/G20、原 DEV-M7 OpenSpec Strict | 本 PR 最新 Head 官方 CI |
| 实际 Agent Runtime | 同一个公开 API 创建/选择 Agent 并经 Hatchet 真实执行、真实模型/Tool/文件/Approval/旧 UI/Artifact Storage | **未验证，不称为 PASS** |
| 真实企业 IAM/Policy/OSS | 外部 Gateway 确认用户身份、当前 Policy、OSS 下载签名与用户实际入口 | **未接入（平台仅提供必需的可信 Adapter 注入点）** |

## 安全与架构约束

- `/api/v1/runs/{id}/stream` 只回放 PG 已持久的可信 Typed Event（不会把 buffered full result 冒充 Token-level live）；每个分页前重验当前 Gateway 身份、PG Run Binding/Initiator 和外部 Policy；撤权后中止。
- Artifact 只存 / 只回 `artifact_id,run_id,digest,media_type,size_bytes` 元数据，不能以客户端构造的任意 OSS 路径发预签名 URL；Artifact 存储服务需独立可信 Adapter 和实时授权。
- `POST /api/v1/runs/{id}/cancel` 只触发平台注入的确定性 `CancelRequested` 事实，不以 API ACK 宣称底层 Agent/Worker/Cube TERMINATED，也不改变 UNKNOWN 副作用。
- UI 仅服务端验证后返回静态 HTML，浏览器通过同源授权 API 读取，动态数据只用 DOM `textContent`（无 HTML 拼接）；该页面是合成 UI 参考，不取代企业 Portal。

## 复盘与未收口的原里程碑条件

本次完成了多个原始已计划能力的集成交付，而非任意拓展 M7。最有价值的回归是：项目相同不意味着同一用户；SSE 不应仅在建连时鉴权；ArtifactRef 不能泄露可直接下载地址；取消 ACK 不是执行终止；持久 Run 所属与 Turn 所属必须在 PG 中一致。

**DEV-M7 保持 ACTIVE，Production NO-GO**：没有接入真实企业 Gateway/IdP 与外部 Policy、没有经统一 Public API 发起真实多 SDK Agent Run 的端到端证据、也没有真实 OSS Artifact 下载、Approval 事件的完整 UI 联测。当前原 OpenSpec 1.1～2.3 的整阶段门禁不勾选、不归档。后续继续按**原定范围**集中联调，不从本切片衍生新 M7 阶段或新架构产品。
## 2026-10-13 公共 API 启动真实 Native Run 联合验收候选（原 M7 1.2/1.3）

- **Red**：真实 PG/HTTP 先写 `test_public_run_launch_pg`，因公共 API 不接受 `start_run` 注入导致全部 6 项报缺失实现；未用内存替代 PG。
- **Green**：复用原 `PgFacts.create` 的同事务 `create_in_tx`，由 `PgConversationStore` 用 Turn 行锁、可信 Owner 和受控 `Idempotency-Key` 冻结 Run/Outbox/Turn Binding，拒绝无权限、未知 Agent/Recipe、缺配置及失败后盲重派；以与原 Inspector 相同的 `execute` Process Adapter 交由真实 Hatchet Worker/两个 SDK 完成。实际 PG+HTTP 启动/幂等/失败合同新增 7 项，连同原有 M7 22 项在本地 **29/29 PASS、0 SKIPPED**。
- **Native 真实 Gate**：`verify_public_api_hatchet.py` 已纳入原 `closed-loop-poc.yml`，校验端到端同一 `run_id/turn_id`、真实 `provider_workflow_run_id`、Native Pydantic AI→OpenAI Agents SDK Step Results、Run.COMPLETED、PG Typed SSE Cursor、跨身份和撤权拒绝。此处真实 Hatchet/SDK 使用**确定性本地模型**，不是外部 LLM Live；最终官方最新 Head CI 未验收前，绝不能宣称 LIVE PASS。
- **复盘/边界**：HTTP 首次提交 ACK 可能未知，重复请求仅返回相同持久 Run，不直接重派；Provider 创建 ACK 的进一步对账仍由既有 HC-02 负责。本 PR 没有增加第二 Engine、Run Scheduler、企业 IAM/OSS、M5/M6/M9 需求。M7 整阶段仍 ACTIVE。

## PR #86 最新 Head 官方验收与合并（补记）

- [PR #86](https://github.com/Bulls1986/Agent-Harness-Platform/pull/86) 最终 Head `2401f306`，两条官方 CI 全部 SUCCESS：真实 PG/HTTP/原 OpenSpec [38360300342](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300342)、架构 [38360300381](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300381)。
- 真实 PG16 CI **14/14 PASS**（原 PG Scope 5 项 + 新版 Conversation/Turn/Run/ArtifactRef/SSE/Cancel/UI 合同 9 项；0 SKIPPED）；独立授权单元 **8/8 PASS**，合计 **22/22**。
- 合并至 Main，提交 `eb224ff9981d93555bbe75ee88e3d235c65c7184`，没有合并任何私有业务或外部 IAM 适配器。
- 架构首次失败仅因 `DEVELOPMENT_MILESTONES.md` 和 `DEVELOPMENT_BACKLOG.md` 使用加粗 `**ACTIVE**：`，与既有阶段校验 `| ACTIVE：` 不一致。恢复现有规范写法后两条 CI PASS，**没有修改状态语义或验收合同**。
- 此实测只证明合成 Server-side Gateway Policy 注入 + 真实 PostgreSQL/HTTP 的限定集成。原 DEV-M7 的真实企业 IdP、公开入口实际启动 Agent、OSS/Approval/既有 Portal 完整 Gate **仍 OPEN**；生产 NO-GO。

## 2026-10-13 原生公共 API 实际执行结果与阶段判定（最终补录）

[PR #88](https://github.com/Bulls1986/Agent-Harness-Platform/pull/88) 已合并 Main `6189e6377a1f00826a99419a817ba995a9b1710c`，三条 Head CI 均 SUCCESS：
- [实际 Native Hatchet/双 SDK/Inspector/Replan CI 38363098226](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38363098226)；新增 `M7 Real versioned Public API creates actual Hatchet workflow and two SDK Results` 和原 Native/Replan/Inspector 均 **SUCCESS**。
- [M7 真实 PostgreSQL/HTTP/原 OpenSpec 38363098215](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38363098215)：原授权 8 + 原 PG/HTTP 14 + 新 PG Run 启动/幂等/阻断 7，**29/29 PASS，0 SKIPPED**。
- [架构护栏 38363098214](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38363098214)：**SUCCESS**。

官方 Native 运行中，`platform_run_id=run-83876c5046df54db2ec02f51f12b6697`，`hatchet_workflow_run_id=0d63b110-a9a7-4578-986b-1d1a1d50785f`，`conversation_id=conversation-dd2ec47b12ab475e9aec331b4f4c62ca`，`turn_id=turn-6c91452af813435cbea7c5ca89cb10dc`。业务 Run `COMPLETED`、14 条连续序号的 PG Event、两个 SDK 的真实运行结果经版本化 API/SSE 校验；**Native 派发 1 次**且相同 `Idempotency-Key` 的 HTTP 重试没有再创建 Provider Workflow。无权限与撤权 API 读均拒绝。

**严格限定证据层级**：真实 Hatchet Embedded + 实际 PG + Pydantic AI/OpenAI Agents SDK，但两 SDK 使用**确定性本地模型**；Gateway/Policy 是服务端注入的**合成可信 Adapter**。这并未验证企业 IdP、外部真实 LLM、OSS 授权下载、审批事件 UI 或既有 Portal 联动。先前本文件“原生 CI 待验”是开发过程快照，以本最终证据为准。DEV-M7 **ACTIVE**、原 1.1～2.3 未通过的部分保持 OPEN；Production NO-GO。M5/M6/M8/M9 均不加入 DEV-M7 退出条件。
