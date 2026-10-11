# DEV-M5 Cube 可信执行与 Coding Runtime · Tasks

> 状态：**PLANNED**。工期、Owner 和 Sprint 需要在真实代码/团队容量基线上评估；所有勾选项以运行证据为准。来源 DEV-HC-03 / HC-03。

## 0. 前置与需求冻结
- [ ] 0.1 审阅原有 Accepted ADR/HC 与 G01–G20，识别事实 Owner、安全边界和阻断依赖；OpenSpec 四类规划材料 Strict PASS。
- [ ] 0.2 确认代表性真实业务/失败样本、环境及测试数据，记录本阶段交付与不做范围。

## 1. TDD 与集成开发
- [ ] 1.1 先写无 ExecutionContext、越权、旧 Lease/Fencing 的拒绝测试；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.2 完成真实 Cube Provider Allocate/Bind/Release 与 WorkspaceRef；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.3 OpenCode Shell/Files/Git 和 Worker A→B 实机接管；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.4 模型-only 0 Sandbox、资源释放、跨 Scope 安全/CI/复盘；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。

## 2. 阶段 Gate 与复盘
- [ ] 2.1 复验 拒绝过期及越权 的拒绝/故障合同，正例、负例和真实集成全部 PASS；无 SKIPPED 冒充通过。
- [ ] 2.2 记录故障根因、设计修正、测试覆盖、可复用护栏及风险，完成复盘与 Backlog 状态更新。
- [ ] 2.3 代码 PR/CI、架构审查通过，确认无后续生产门禁被错误关闭后，勾选 Tasks 并归档该 OpenSpec。