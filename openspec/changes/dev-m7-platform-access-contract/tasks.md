# DEV-M7 统一 API、Chat 与用户交互 · Tasks

> 状态：**ACTIVE（仅授权只读子切片单测）**，DEV-M7 全阶段仍 OPEN。工期、Owner 和 Sprint 需要在真实代码/团队容量基线上评估；所有勾选项以完整真实门禁为准。正式外部消费方接入以 DEV-CONSUMER-02 为前置，不把消费方业务逻辑并入 Harness。

> 2026-10-11 过程证据：`poc/platform_access/test_authorized_reads.py` 从缺失实现的 Red（ModuleNotFoundError）开始，新增受信任 `SecurityContext` / 持久事实 `RunBinding` / `RunReader` / 外部 Policy 的注入式边界；8 项 HTTP 单测 Green（含跨项目、权限撤销、身份 Header 伪造、非法游标、缺省配置拒绝）；新增独立 CI 工作流 `dev-m7-access.yml`。**尚缺**真实 Gateway/IAM、PG 绑定、SSE 权限、ArtifactRef、真实 UI、CI/Live 证据；故 1.1～2.3 均保持未勾选。

## 0. 前置与需求冻结
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
