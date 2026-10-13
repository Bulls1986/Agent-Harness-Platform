# DEV-M7 统一 API、Chat 与用户交互 · Tasks

> 状态：**ACTIVE · DEV-M7 原始范围正式收口对账（2026-10-13）；实测已验收的子合同不再重复开发，外部 Gateway/事件来源联合 Gate 仍 OPEN，故暂不可归档。** 仅使用现有 DEV-API-01 原任务 0.1～2.3，不另加 A.x。原任务为**整阶段 Gate，不可只按已验证子切片局部打勾**；M8 合成消费者仍然是下游验证，不是 M7 前置。详细证据：`docs/retrospectives/DEV_M7_ORIGINAL_GATE_CLOSEOUT_AUDIT_20261013.md`。

> 2026-10-11 过程证据：`poc/platform_access/test_authorized_reads.py` 从缺失实现的 Red（ModuleNotFoundError）开始，新增受信任 `SecurityContext` / 持久事实 `RunBinding` / `RunReader` / 外部 Policy 的注入式边界；8 项 HTTP 单测 Green（含跨项目、权限撤销、身份 Header 伪造、非法游标、缺省配置拒绝）；新增独立 CI 工作流 `dev-m7-access.yml`。**当时尚缺**真实 Gateway/IAM、PG 绑定、SSE 权限、ArtifactRef、真实 UI、CI/Live 证据；PG 绑定后续由 A.2 子切片补足，整阶段仍有其他真实门禁 OPEN；故 1.1～2.3 均保持未勾选。

> CI 更新：PR #65 上 [访问控制单测工作流](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38137992463) 和 [架构门禁工作流](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38137992419) 已 PASS；这里的「CI/Live 证据尚缺」具体指**真实 Gateway/IAM + PostgreSQL 授权组合、SSE/Artifact/用户端的完整集成 CI 与 Live Gate**，不是新增单元工作流。阶段仍 OPEN。

## 已完成、独立验收的开发子切片（不替代整阶段 Gate）

- [x] A.2 `PgFacts.create` 在真实 PostgreSQL 16 固定 Project/Initiator，`PgRunReader` 按 Run PG 归属读取并在 HTTP 政策拒绝前屏蔽历史无 Scope Run；禁止数据库归属 UPDATE/原地补绑；**证据**：docs/retrospectives/DEV_M7_PG_RUN_BINDING_20261011.md（2 次 Red→Green、PG 5 项和已有 8 项 HTTP 单测，CI 38140021577 / 38140021573）。真实企业 Gateway/IdP、完整 SSE、ArtifactRef/OSS、Conversation/Turn、UI 仍 OPEN。

> 2026-10-13 DEV-M7 原范围集成推进：在已有 PR #65/#67 的受信任授权 Run 读取/真实 PG 归属基础上，补充 PostgreSQL Conversation→Turn→Run 事实、版本化 `/api/v1`、授权 SSE/游标、ArtifactRef 元数据、取消请求与只读结果 UI。真实 PG+HTTP 跨项目/跨用户/撤权负例已写；PR [#86](https://github.com/Bulls1986/Agent-Harness-Platform/pull/86) 最新 Head 真实 PG/HTTP+OpenSpec [CI 38360300342](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300342) 和 [架构 CI 38360300381](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38360300381) 均 SUCCESS、已合并 main；真实 PG 14/14、授权单元 8/8，共 22/22，无 SKIPPED。**本切片不声称真实企业 IdP、现网旧 UI/OSS 签名/Agent 创建运行完整集成已完成；这些属于本阶段原 1.1～2.1 未完成验收项，保持 OPEN，不增设新任务编号。** 证据：docs/retrospectives/DEV_M7_PLATFORM_API_INTEGRATION_20261013.md。

> 2026-10-13 原始 **1.2/1.3 的统一执行入口**在研：版本化 `POST /api/v1/turns/{turn_id}/runs`，可信 Agent/Recipe admission + Model Binding、`Idempotency-Key`、同 PG 事务 Run/Outbox/Turn 关联及真实 Hatchet `execute` 提交；拒绝无权限、未知配置、重复不安全 dispatch、以及确认不明后 HTTP 盲重派。真实 PG TDD 7 项 + 既有 M7 回归 22 项本地 PASS；`poc.platform_access.verify_public_api_hatchet` 已加入**现有**真实 Hatchet/双 SDK CI。PR [#88](https://github.com/Bulls1986/Agent-Harness-Platform/pull/88) 最新 Head 实际 Hatchet/双 SDK/原有 Replan/Inspector [CI 38363098226](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38363098226) SUCCESS；M7 PG/HTTP [CI 38363098215](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38363098215) 29/29 无 SKIPPED、架构 [CI 38363098214](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38363098214) SUCCESS，已合并 main 6189e63。**仅这条原生合成模型 API 执行子切片已通过**，整阶段外部 Gateway/OSS/既有 Portal 原验收仍 OPEN。不新增 A.x 或新阶段。

## 2026-10-13 原始 Gate 冻结与子合同证据矩阵（不代表阶段 Tasks 可勾选）

| Gate | 实际状态 | 界限 |
| --- | --- | --- |
| 0.1、0.2 | 已有子合同证据，阶段 Tasks 仍 [ ] | 固定架构/不做范围；用合成需求与真实故障/PG/Native 样本，不上传私有 PDLC |
| 1.1 | 已有 Red→Green，阶段 Tasks 仍 [ ] | PR #65/#67/#86/#88 原 TDD，当前 Tool/Approval/Artifact UI/Paging Red→Green；真实 PG CI 是合并门禁 |
| 1.2 | **BLOCKED** | SecurityContext/Run Owner/API 完成，但真实企业 Gateway/Policy 联调未经验证 |
| 1.3 | **PARTIAL** | 真实 Hatchet 双 SDK、PG SSE/结果、合成 Tool/Approval/Artifact 展示完成；真实外部事件来源及现有用户入口联合 Gate 未验证 |
| 1.4 | 已有 API 合同证据，阶段 Tasks 仍 [ ] | 跨项目/同项目他人访问、撤权、对象引用禁止泄露、OpenSpec/CI/UI 复盘；真实外部身份另见 1.2 |
| 2.1 | **BLOCKED** | 不把合成事件/Policy 解释为全部真实正/负例已通过 |
| 2.2 | 已有复盘，阶段 Tasks 仍 [ ] | 原需求范围、故障根因、PR/CI/遗留风险有独立复盘，Backlog/里程碑回写 |
| 2.3 | **OPEN** | 仅全部原 Gate PASS 才可正式 archive；本 PR 为部分收口，不改变整阶段 ACTIVE |

详见 [最终范围审计](../../../docs/retrospectives/DEV_M7_ORIGINAL_GATE_CLOSEOUT_AUDIT_20261013.md)。

## 0. 前置与需求冻结

> 现状：DEV-M2 Token SSE/游标实测已完成有限切片；DEV-M3 原始有限交付已正式 CLOSED，真实 PG/Native 与 M7 授权读链路具备；本次复核原固定范围并保留 1.2/1.3/2.1 外部 Gateway、真实事件来源的验收缺口。不能把合成网关/事件当作企业完成证据。
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