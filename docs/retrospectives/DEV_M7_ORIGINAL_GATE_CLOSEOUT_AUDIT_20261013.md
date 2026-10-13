# DEV-M7 原始交付合同 · 最终验收对账及未关闭 Gate（2026-10-13）

## 裁决

**DEV-M7 / DEV-API-01 保持 ACTIVE，暂不能归档。** 对照最初 Proposal/Spec，而不是后续扩大后的理想平台范围，已完成 Conversation/Turn/Run、双 SDK 原生执行、受控 SSE、ArtifactRef 元数据、Inspector 演示和跨项目/跨用户拒绝。**未提供外部可信 Gateway/IdP + 当前 Policy 的真实集成证据，也未在统一客户端上通过实际 Tool/审批/对象存储来源的最终用户展示门禁。** 这些并非本次新建的任务，已在原 `1.2/1.3/2.1` 及 Exit Gate 中。不能以合成身份、合成事件或开发调试 Inspector 冒充企业入口已验收。

## 原任务对账，不新增编号

| 原 Task | 已有证据 / 尚缺条件 | 阶段判定 |
| --- | --- | --- |
| 0.1 | 原 HC-01/02/03、G01–G20、PG Owner / Hatchet Worker Owner 与外部 IAM 责任边界不变；原 DEV-M7 OpenSpec Strict 与 Architecture 既有 CI PASS | **PASS** |
| 0.2 | 无客户业务数据：合成产品审核场景、真实独立 PG/Native Hatchet/双 SDK、不同身份及多事件/故障样本，记录合成边界；不把特权 Cube/M5/生产 IAM 纳入 | **PASS（代表性合成样本）** |
| 1.1 | PR #65/#67/#86/#88 Red→Green，真实 PG Conversation/Turn/Run/Typed SSE/ArtifactRef/取消/权限；本次新增 Tool/Approval/Artifact 只读 UI 和 >250 事件分页先 Red 再 Green，原有正常授权/撤权回归未破坏 | **PASS（合同测试）** |
| 1.2 | `SecurityContext` 注入、冻结 Project/Initiator、Versioned API 与 Run 启动均实现；但仅合成可信 Gateway 回调，没有真实企业 IdP/Gateway/Policy 的 E2E | **BLOCKED（原定外部接入门禁）** |
| 1.3 | PR #88/#90 真实 Hatchet 双 SDK 本地确定性模型、Inspector 页面、14 个持久事件；本次真实 PG 验证 Tool/Approval/Artifact typed event + ArtifactRef 展示及分页。**这些 Tool/Approval/Artifact 事件是显式合成的领域投影**，不是实际 Tool、M6 审批或 OSS 下载；缺旧 UI/外部来源联合可视化证据 | **PARTIAL（原定事件来源/用户视角 Gate）** |
| 1.4 | PG/HTTP 跨项目/同项目不同 USER、Policy 撤销、SSE 重新授权、对象 Ref 不暴露 OSS URL、无 Header 冒充；真实 PG + HTTP/原架构 CI；用户页面文字、历史分页异常有复盘 | **PASS（平台 API 安全合同；真实外部身份 Gate 见 1.2）** |
| 2.1 | 已有真实 PG/Native Hatchet 与独立公共 API 正反例，**但 1.2、1.3 外部联合 Gate 没有 PASS**，不接受 SKIPPED、合成替代 | **BLOCKED** |
| 2.2 | 本对账保留 Red→Green、故障根因、可复用护栏、准确 Backlog/里程碑状态；未修改 M5/M6/M8/M9 | **PASS（复盘/证据）** |
| 2.3 | 本 PR 最新 Head 官方 PG/架构/Native 回归必须 PASS 后可合并当前开发子切片，**只有 1.2/1.3/2.1 真正完成才可对全 DEV-M7 归档** | **OPEN（正确保留）** |

## 可复验的现有正式证据

- [PR #65](https://github.com/Bulls1986/Agent-Harness-Platform/pull/65) 和 [PR #67](https://github.com/Bulls1986/Agent-Harness-Platform/pull/67)：注入身份/Policy、PG Run Owner 绑定及不可改绑，合成授权 HTTP/实际 PG 拒绝矩阵 PASS。
- [PR #86](https://github.com/Bulls1986/Agent-Harness-Platform/pull/86)：版本化 Conversation/Turn/Run、Typed Event SSE 和 Cursor、ArtifactRef 元数据、取消、只读结果 UI；[实际 PG/HTTP CI 38360300342](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300342) SUCCESS。
- [PR #88](https://github.com/Bulls1986/Agent-Harness-Platform/pull/88)：版本化公共 API 真正启动 Native Hatchet → Pydantic AI → OpenAI Agents SDK；[实际执行 CI 38363098226](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38363098226) SUCCESS，Run COMPLETED，14 条 Event，Native 派发 1 次。
- [PR #90](https://github.com/Bulls1986/Agent-Harness-Platform/pull/90)：本地 Inspector 现有 Tab 下的公共 API 演示；[CI 38366796657](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38366796657) SUCCESS，真实 PG/SDK、Inspector HTTP 实机证明。
- 本次开发子切片：`poc/platform_access/test_m7_full_event_view_pg.py`，使用真实 PG 且无 SKIPPED。构造同一受限用户的真实 PG Run/Conversation/Turn，持久化 `response.output_text.delta`、`tool.dispatched`、`tool.outcome.unknown`、`approval.requested`、`approval.decision`、`artifact.created` **合成测试事件**；授权 Public API/Typed SSE/ArtifactRef 按原事实读取，非法项目/用户及撤权拒绝，超过 250 Event 时 Cursor 连续、无重复/漏页。结果页 UI 对 Tool/审核/文件增加通俗标签、显式加载后续历史，所有动态文字使用 `textContent`，不暴露 OSS 对象路径。先记录真实失败测试后修复，连同现有 M7 单测本地真实 PG **32/32 PASS、0 SKIPPED**；Node JS Syntax PASS。最终以本 PR 最新 Head CI 为准。

## 已确定的最小外部阻断

**不是要开发新 IAM 或通用 Tool/Approval/OSS 平台。** 需要由已有外部体系提供合规、可重复的测试环境和接入证据：可信 Gateway/Policy 对目标 API 提供真实用户与项目 Context、撤权；独立授权客户端经实际提供的 Tool、Approval 和存储 Adapter 浏览对同一 Run 的事件和文件引用（无需运行 M5 Cube 或开发 M6 新能力）。当外部系统尚未提供时，本平台保留真实接口合同与 `ACTIVE` 状态，不自制“演示鉴权 Token”或把 Inspector 的合成身份挂进正式 API。

原 `DEV-M8` 合成消费者验证属于下游，不得成为 M7 新的前置条件；M9 Production NO-GO 不因 M7 单阶段验收而取消。未修改原里程碑表结构、未创建 A.x 新任务、未上传 PDLC 私有业务代码。

## 本轮复盘

根因不是缺少第二套对话/工作流引擎，而是**受控类型化事件的用户展示**在历史 `250` 条后被静默截断，且旧只读页面向用户输出技术事件名和 JSON。保留公共 API 游标事实 Owner 不变，新增明确的 Tool / 审核 / 文件事件文案和按游标加载；跨次请求的授权仍由同一个已注入的 Policy 处理。测试数据中的 Approval/Tool/Artifact 仅用于展示与安全合同；其真实生产执行归属仍分别留在原有外部系统/M6/对象存储职责。

**正式关闭条件**仍是原 OpenSpec 中的外部可信身份和用户完整事件/文件/审核浏览真实验收；不能仅修改文档将残余风险重新归类掉。
