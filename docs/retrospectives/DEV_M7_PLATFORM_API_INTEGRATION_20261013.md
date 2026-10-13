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
## PR #86 最新 Head 官方验收与合并（补记）

- [PR #86](https://github.com/Bulls1986/Agent-Harness-Platform/pull/86) 最终 Head `2401f306`，两条官方 CI 全部 SUCCESS：真实 PG/HTTP/原 OpenSpec [38360300342](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300342)、架构 [38360300381](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300381)。
- 真实 PG16 CI **14/14 PASS**（原 PG Scope 5 项 + 新版 Conversation/Turn/Run/ArtifactRef/SSE/Cancel/UI 合同 9 项；0 SKIPPED）；独立授权单元 **8/8 PASS**，合计 **22/22**。
- 合并至 Main，提交 `eb224ff9981d93555bbe75ee88e3d235c65c7184`，没有合并任何私有业务或外部 IAM 适配器。
- 架构首次失败仅因 `DEVELOPMENT_MILESTONES.md` 和 `DEVELOPMENT_BACKLOG.md` 使用加粗 `**ACTIVE**：`，与既有阶段校验 `| ACTIVE：` 不一致。恢复现有规范写法后两条 CI PASS，**没有修改状态语义或验收合同**。
- 此实测只证明合成 Server-side Gateway Policy 注入 + 真实 PostgreSQL/HTTP 的限定集成。原 DEV-M7 的真实企业 IdP、公开入口实际启动 Agent、OSS/Approval/既有 Portal 完整 Gate **仍 OPEN**；生产 NO-GO。
