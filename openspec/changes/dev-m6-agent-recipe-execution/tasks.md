# DEV-M6 多 Agent Recipe 与审批验证 · Tasks

> 状态：**ACTIVE / OPEN**。2026-10-14 仅真实 PostgreSQL 合成 Recipe/审批/Receipt 安全合同 9/9 PASS，实际 SDK/Hatchet、OSS、受信任 Tool、恢复和 CI 未验收，不能记为阶段 CLOSED。证据：docs/retrospectives/DEV_M6_RECIPE_SAFETY_SLICE_20261014.md。沿用原任务范围、遵守 HC-01/02/03，不要求特定业务消费者实施。

## 0. 前置与需求冻结
- [x] 0.1 审阅 Accepted ADR/HC 与 G01–G20、确认业务/技术事实 Owner 和原有阻断；M6 OpenSpec Strict PASS。**证据**：docs/retrospectives/DEV_M6_RECIPE_SAFETY_SLICE_20261014.md。
- [ ] 0.2 确认代表性真实业务/失败样本、环境及测试数据，记录本阶段交付与不做范围。

## 1. TDD 与集成开发
- [ ] 1.1 先制定 Recipe Version/Artifact/Approval 合同和失败负例；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.2 实现 Step 类型化交接、Verifier、Approval/RecoveryPoint；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.3 真实跨 SDK 三 Agent 规划→编码→验证 E2E，使用合成通用任务与脱敏 Evidence；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.4 审批拒绝/超时恢复/产物来源/CI/复盘；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。

### 有界开发进度（2026-10-14，未达到阶段退出 Gate）

实际 PG 合成测试已覆盖版本冻结、三 Step 产物引用/Verifier Evidence 字段、审批拒绝/重启、Attempt 并发、M4 Receipt UNKNOWN/确认与终态阻断 9/9。Provider 绑定、Artifact 和外部 Receipt 的业务效果均为**合成测试输入**。原 1.1～1.4 涉及 SDK/OSS/Trusted Tool/恢复/CI 的完整门禁仍未满足，不提前勾选。**证据**：docs/retrospectives/DEV_M6_RECIPE_SAFETY_SLICE_20261014.md。

## 2. 阶段 Gate 与复盘
- [ ] 2.1 复验 审批拒绝 的拒绝/故障合同，正例、负例和真实集成全部 PASS；无 SKIPPED 冒充通过。
- [x] 2.2 记录当前 PG 子切片 Red/Green、架构设计修正、失败根因、测试覆盖与遗留 Gate，Backlog 更新为 ACTIVE / OPEN。**证据**：docs/retrospectives/DEV_M6_RECIPE_SAFETY_SLICE_20261014.md。
- [ ] 2.3 代码 PR/CI、架构审查通过，确认无后续生产门禁被错误关闭后，勾选 Tasks 并归档该 OpenSpec。