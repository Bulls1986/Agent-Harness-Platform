# DEV-M8 现有 PDLC 迁移

## ADDED Requirements

### Requirement: 实施与结果服从架构边界

PDLC-M0 真源码/现网只读盘点→M1 兼容 Facade→M2 Single Writer 影子/灰度→M3 真实 PDLC Recipe→M4 分批切流/回退。保留 OpenCode Coding 和旧会话策略。 阶段 SHALL 提供可重复的实际环境证据和正确的领域/技术 Owner；不实现额外 Scheduler，不用技术 Workflow History 取代 Harness Domain 状态。

#### Scenario: 交付成功
- **WHEN** 阶段依赖满足且真实系统验收执行
- **THEN** 旧 UI/SSO/项目/历史 Session/Agent/Skill/MCP/权限不退化，新增跨专业 Agent 可用、可回退。

### Requirement: 必须覆盖正常流程与失败路径

每条需求 MUST 先编写可失败的正/负例，再实现最小代码，并在实际环境测试、CI 和架构审查通过后关闭。

#### Scenario: 兼容旧资产
- **WHEN** 旧用户使用原 URL/SSO 查看历史项目和 Session
- **THEN** 业务对象、会话顺序、附件、资产及授权一致且 Legacy ID 稳定

#### Scenario: 防双写/回退
- **WHEN** 同一任务切向新 Run 或需要回退
- **THEN** 同一时刻恰一 Writer，副作用对账完成后才能停止/切回，活动旧会话受保护

### Requirement: 未验证的结果不可升级为阶段完成

若真实测试失败、SKIPPED、BLOCKED 或缺失，里程碑 SHALL 标注证据不足与 OPEN；禁止把规划 4/4 误认作代码交付或生产上线。

#### Scenario: 真实门禁未完成
- **WHEN** 某个阶段必过 Gate 未通过或相关依赖尚未 Ready
- **THEN** DEV-M8 保持 OPEN，保留原因与整改任务