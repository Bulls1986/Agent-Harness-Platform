# DEV-M7 统一 API、Chat 与用户交互 · Tasks

> 状态：**ACTIVE（授权只读单测 + PostgreSQL Run 归属/不可变性真实集成子切片）**，DEV-M7 全阶段仍 OPEN。工期、Owner 和 Sprint 需要在真实代码/团队容量基线上评估；所有勾选项以完整真实门禁为准。DEV-M7 实施项为 DEV-API-01；M8（DEV-CONSUMER-01）只作为下游合成客户端合同验证，不是 M7 前置，不把消费方业务逻辑并入 Harness。

> 2026-10-11 过程证据：`poc/platform_access/test_authorized_reads.py` 从缺失实现的 Red（ModuleNotFoundError）开始，新增受信任 `SecurityContext` / 持久事实 `RunBinding` / `RunReader` / 外部 Policy 的注入式边界；8 项 HTTP 单测 Green（含跨项目、权限撤销、身份 Header 伪造、非法游标、缺省配置拒绝）；新增独立 CI 工作流 `dev-m7-access.yml`。**当时尚缺**真实 Gateway/IAM、PG 绑定、SSE 权限、ArtifactRef、真实 UI、CI/Live 证据；PG 绑定后续由 A.2 子切片补足，整阶段仍有其他真实门禁 OPEN；故 1.1～2.3 均保持未勾选。

> CI 更新：PR #65 上 [访问控制单测工作流](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38137992463) 和 [架构门禁工作流](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38137992419) 已 PASS；这里的「CI/Live 证据尚缺」具体指**真实 Gateway/IAM + PostgreSQL 授权组合、SSE/Artifact/用户端的完整集成 CI 与 Live Gate**，不是新增单元工作流。阶段仍 OPEN。

## 已完成、独立验收的开发子切片（不替代整阶段 Gate）

- [x] A.2 `PgFacts.create` 在真实 PostgreSQL 16 固定 Project/Initiator，`PgRunReader` 按 Run PG 归属读取并在 HTTP 政策拒绝前屏蔽历史无 Scope Run；禁止数据库归属 UPDATE/原地补绑；**证据**：docs/retrospectives/DEV_M7_PG_RUN_BINDING_20261011.md（2 次 Red→Green、PG 5 项和已有 8 项 HTTP 单测，CI 38140021577 / 38140021573）。真实企业 Gateway/IdP、完整 SSE、ArtifactRef/OSS、Conversation/Turn、UI 仍 OPEN。

> 2026-10-13 DEV-M7 原范围集成推进：在已有 PR #65/#67 的受信任授权 Run 读取/真实 PG 归属基础上，补充 PostgreSQL Conversation→Turn→Run 事实、版本化 `/api/v1`、授权 SSE/游标、ArtifactRef 元数据、取消请求与只读结果 UI。真实 PG+HTTP 跨项目/跨用户/撤权负例已写；PR [#86](https://github.com/Bulls1986/Agent-Harness-Platform/pull/86) 最新 Head 真实 PG/HTTP+OpenSpec [CI 38360300342](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300342) 和 [架构 CI 38360300381](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300381) 均 SUCCESS、已合并 main；真实 PG 14/14、授权单元 8/8，共 22/22，无 SKIPPED。**本切片不声称真实企业 IdP、现网旧 UI/OSS 签名/Agent 创建运行完整集成已完成；这些属于本阶段原 1.1～2.1 未完成验收项，保持 OPEN，不增设新任务编号。** 证据：docs/retrospectives/DEV_M7_PLATFORM_API_INTEGRATION_20261013.md。

> 2026-10-13 原始 **1.2/1.3 的统一执行入口**在研：版本化 `POST /api/v1/turns/{turn_id}/runs`，可信 Agent/Recipe admission + Model Binding、`Idempotency-Key`、同 PG 事务 Run/Outbox/Turn 关联及真实 Hatchet `execute` 提交；拒绝无权限、未知配置、重复不安全 dispatch、以及确认不明后 HTTP 盲重派。真实 PG TDD 7 项 + 既有 M7 回归 22 项本地 PASS；`poc.platform_access.verify_public_api_hatchet` 已加入**现有**真实 Hatchet/双 SDK CI。PR [#88](https://github.com/Bulls1986/Agent-Harness-Platform/pull/88) 最新 Head 实际 Hatchet/双 SDK/原有 Replan/Inspector [CI 38363098226](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38363098226) SUCCESS；M7 PG/HTTP [CI 38363098215](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38363098215) 29/29 无 SKIPPED、架构 [CI 38363098214](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38363098214) SUCCESS，已合并 main 6189e63。**仅这条原生合成模型 API 执行子切片已通过**，整阶段外部 Gateway/OSS/既有 Portal 原验收仍 OPEN。不新增 A.x 或新阶段。

## 0. 前置与需求冻结

> 现状：DEV-M2 Token SSE/游标实测已完成有限切片；DEV-M3 真实 Replan/完整 Domain Gate 未完成。0.1/0.2 尚无全阶段冻结与真实 Gateway/PG/权限/失败样本的完整证据，因此维持未勾选，不能据此宣称可进行整阶段验收。
- [ ] 0.1 审阅原有 Accepted ADR/HC 与 G01–G20，识别事实 Owner、安全边界和阻断依赖；OpenSpec 四类规划材料 Strict PASS。
- [ ] 0.2 确认代表性真实业务/失败样本、环境及测试数据，记录本阶段交付与不做范围。

## 1. TDD 与集成开发
- [ ] 1.1 先写 Conversation/Turn、Typed SSE、ArtifactRef、权限负例；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.2 实现外部 SecurityContext 对接与稳定 API/会话关系；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.3 真实模型/文件/工具事件可读 UI 和游标恢复；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.4 跨身份/项目拒绝、CI/用户体验复盘；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。

## 2. 阶段 Gate 与复盘
- [ ] 2.1 复验 权限和事件隔离 的拒绝/故障合同，正例、负例和真实集成全部 PASS；无 SKIPPED 冒充通过。
- [ ] 2.2 记录故障根因、设计修正、测试覆盖、可复用护栏及风险，完成复盘与 Backlog 状态更新。
- [ ] 2.3 代码 PR/CI、架构审查通过，确认无后续生产门禁被错误关闭后，勾选 Tasks 并归档该 OpenSpec。