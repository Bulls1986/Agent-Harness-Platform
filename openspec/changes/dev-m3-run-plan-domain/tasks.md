# DEV-M3 领域内核与 Workflow 映射 · Tasks

> 状态：**ACTIVE · DEV-M3 领域安全首段已通过，真实 Replan v2/Segment 仍 OPEN**。工期、Owner 和 Sprint 需要在真实代码/团队容量基线上评估；所有勾选项以运行证据为准。来源 DEV-HC-01 / HC-01。

## 0. 前置与需求冻结
- [ ] 0.1 审阅原有 Accepted ADR/HC 与 G01–G20，识别事实 Owner、安全边界和阻断依赖；OpenSpec 四类规划材料 Strict PASS。
- [ ] 0.2 确认代表性真实业务/失败样本、环境及测试数据，记录本阶段交付与不做范围。

## 已完成的可独立验收切片（不替代后续任务）
- [x] A.1 真实 PostgreSQL Plan v1/Recipe Digest/Provider 冻结、重复 Intent 幂等、拒绝过期 Version 及 Replan 意图 BLOCKED_PROVIDER_QUIESCENCE；**证据**：docs/retrospectives/DEV_M3_M5_FIRST_SLICE_20261011.md（TDD Red→Green、PR #61，CI 38132324088 / 38132324099）。后续必须实测 Hatchet 停机 ACK/Receipt 后才能创建 Plan v2。

## 1. TDD 与集成开发
- [ ] 1.1 先按 HC-01 写状态机/版本/过期 Attempt 失败测试并记录 Red；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.2 实现 Run/Plan/Step/Attempt/Segment 领域事实和独立 Provider Binding；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.3 真实 PG+Hatchet 的 v1→v2 Replan、重复投递、失败阻断；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.4 完成跨 Version/Owner 负例、CI/回归与复盘；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。

## 2. 阶段 Gate 与复盘
- [ ] 2.1 复验 拒绝过期执行者 的拒绝/故障合同，正例、负例和真实集成全部 PASS；无 SKIPPED 冒充通过。
- [ ] 2.2 记录故障根因、设计修正、测试覆盖、可复用护栏及风险，完成复盘与 Backlog 状态更新。
- [ ] 2.3 代码 PR/CI、架构审查通过，确认无后续生产门禁被错误关闭后，勾选 Tasks 并归档该 OpenSpec。