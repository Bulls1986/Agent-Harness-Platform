# DEV-M7 最终限定收口 · 2026-10-13

## 结论与严格边界

**CLOSED（原始平台 API/SDK 可控交付范围）**，而不是 Production GO。DEV-API-01 交付由 Harness 自身持有的接口及安全读合同：Run/Conversation/Turn 事实与不变归属、版本化 API→真实 Hatchet→两个 Agent SDK、幂等提交、PG Typed SSE/游标/撤权、ArtifactRef 元数据、合成类型事件投影、公共只读结果页和本地 Inspector 实际运行。没有添加第二个 Workflow 引擎、通用 Tool/Approval 引擎或企业内部系统代码。

**验收解释与非达成声明**：最初 Proposal 明确「企业 IAM 仍外部」，文件/审核及其他 Tool 事件的真实生产提供方由原 M6/外部 OSS 负责。因此本次针对平台 **消费已持久化事件/引用的合同** 验收，不将企业 Gateway/IdP/Policy 实际接入、OSS 对象签名下载、真实 Tool/审批产生、旧企业 Portal 接入误写为 PASS。以下为显式未验：

- **NOT VERIFIED — 企业身份/权限服务的真实端到端接入。** 验证的是可信外部身份/Policy Port 注入、PG 冻结归属以及合成可信身份的真实 PostgreSQL/HTTP 拒绝矩阵。实际企业 Gateway/IdP、生产 Token/撤权联调仍须在原 M8/M9 的真实外部消费者与生产安全 Gate 中验收。
- **NOT VERIFIED — 真正的 OSS 签名下载、真实 Tool/审批生产来源及企业旧 Portal 联动。** 验证的是 PostgreSQL 已持久 Typed Event/ArtifactRef 的 **受授权消费与用户展示**；Tool/Approval/Artifact 源事件是明确标注的合成测试事实，不能据此宣称通用 ToolRuntime、审批引擎或存储服务已运行。各来源的真实交付归原 M6/外部存储/原 M8 互通与 M9 交付准入，不创建 M7 新系统。
- **NOT VERIFIED — 真实外部 LLM 业务效果及 Production GO。** CI 双 SDK 使用本地确定性模型，仅证明真实 SDK 与 Native Hatchet/PG 的完整技术执行链；M9 仍严格 **Production NO-GO**。

这是一项**明确记录范围例外的有限里程碑验收**：原 Spec「相同 Run 的文本、工具、文件和审批可在授权页面关联展示」的平台读取合同已经通过；**生产来源端到端场景未通过，不作为 M7 已完成事实，而保留在现有后续真实集成/上线 Gate**。该例外不是新的需求，也不改变外部系统的真实状态。若要求把企业联合联调本身视为 DEV-M7 不可豁免的退出门禁，应撤销有限收口结论并将 DEV-M7 保持 ACTIVE；不得隐匿未验证证据。

## 原始阶段 Tasks / 门禁对账

| 原始项 | 平台已完成、可定位证据 | 未验证边界 |
| --- | --- | --- |
| 0.1 / 0.2 | HC-01/02/03、G01–G20 分权设计、M3/M4 已归档依赖；代表性合成用例与真实 PG/Hatchet/SDK，无任何私有业务源码 | 非生产客户真实样本 |
| 1.1 | PR #65/#67/#86/#88/#90/#91 Red→Green，Conversation/Turn/Run/PG Owner、Typed SSE/ArtifactRef、授权负例与可读事件结果页 | 真正的 Tool/Approval 生产源 |
| 1.2 | 受信任 `SecurityContext` + Policy 注入 Port、真实 PG Owner/原子 Run 创建及幂等版本化 API，缺失身份拒绝、同项目不同 USER 404、每页/每批撤权检查 | 企业 Gateway 真实接入 **NOT VERIFIED** |
| 1.3 | 真实 Hatchet Worker 双 SDK 回写（Run COMPLETED、Provider Workflow ID）、PG Typed SSE Cursor、只读 `/ui/conversations/{id}` 展示 Tool/审核/文件合成持久事件与可分页历史、ArtifactRef 授权元数据，不泄露 OSS 路径 | 实际 Tool/审核/存储来源、企业 Portal **NOT VERIFIED** |
| 1.4 / 2.1 | 真实 PG + HTTP 越权负例、同 User/不同项目、不可信 Headers、撤权、失败 ACK、不重复派发、256+ 事件分页、无匿名回退；真实 Native Hatchet 双 SDK/Inspector 端到端 CI | 企业 IdP 生产级行为 **NOT VERIFIED** |
| 2.2 / 2.3 | 事后 Red→Green、原 9 Tasks 平台职责内实现验收、架构回归 + Strict OpenSpec + 正式归档/可追溯 CI | 不宣称 M8/M9/Cube/Receipt/Approval Engine 完成 |

**现有权威证据**（非本次发明）：[授权/PG PR #65](https://github.com/Bulls1986/Agent-Harness-Platform/pull/65)、[#67](https://github.com/Bulls1986/Agent-Harness-Platform/pull/67)；[#86 版本化 API](https://github.com/Bulls1986/Agent-Harness-Platform/pull/86) [真实 PG CI 38360300342](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300342)；[#88 Native Hatchet + SDK](https://github.com/Bulls1986/Agent-Harness-Platform/pull/88) [CI 38363098226](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38363098226)；[#90 Inspector](https://github.com/Bulls1986/Agent-Harness-Platform/pull/90) [CI 38366796657](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38366796657)；[#91 Tool/审核/Artifact 只读投影及分页](https://github.com/Bulls1986/Agent-Harness-Platform/pull/91) [PG CI 38374117298](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38374117298)、[Native CI 38374117555](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38374117555)、[架构 CI 38374117309](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38374117309) 全部 SUCCESS。

真实 M7 公共 API Native Run `run-83876c5046df54db2ec02f51f12b6697` 对应 Hatchet Workflow `0d63b110-a9a7-4578-986b-1d1a1d50785f`，完成 14 条持久事件；重复 HTTP 请求仅派发一次。Inspector Docker 本地也真实完成了新 M7 Run，保持原演示路径与数据卷不变。

## 冻结的范围与风险裁决

- **M7 仅承担 Harness Platform 公共 API 和授权数据展示；** 外部 IAM/Policy 的真实集成端、OSS 下载/审批事件生产者由各自原架构 Owner 承担，不追加 M7 工作量。
- **M8**：独立合成消费者验证版本化 **authenticated** Public API（包括真实外部信任边界、Scope、Event/Cancel/Failure 传播），不要求/上传任何 PDLC 私有应用代码。
- **M6**：Recipe/Tool/Approval Engine 实际工作，若有审批事件则须由可信执行引擎以对应 Run ID 写入 PG。无实际事件不以合成样本代替。
- **M9**：企业 Gateway/Policy 及存储真实授权验收、故障/容量/发布/回退与生产安全；原 **NO-GO** 保持。
- 本次不变更任何 Harness Runtime 权限校验逻辑，不重写 Provider/工具事实，不搭建外部企业系统。只有原 M7 交付限定技术合同作证据归档，其余仍遵守 G01–G20 和 HC-01/02/03。

## 测试与合并准入

正式归档 PR 的最新 Head 必须通过架构护栏、M7 真实 PG + HTTP/授权、以及 Native Hatchet/双 SDK/Inspector/E2E 工作流，无 SKIPPED 代替 PASS；归档后的 Canonical Spec 必须存在，原 Tasks 全部有本报告对应证据。**在该 PR 合并前不得报告 M7 已正式合并主干。**

旧审计 [DEV_M7_ORIGINAL_GATE_CLOSEOUT_AUDIT_20261013.md](DEV_M7_ORIGINAL_GATE_CLOSEOUT_AUDIT_20261013.md) 是 *2026-10-13 归档前* 的外部阻断事实；本有限收口决议保留这些未验证事实，但将外部依赖按原 Non-goals 和 M8/M9 的所属环节继续追踪，不能解释为外部 Gate 通过。
