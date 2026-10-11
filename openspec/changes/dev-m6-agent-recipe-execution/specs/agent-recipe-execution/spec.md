# DEV-M6 多 Agent Recipe 与审批验证

## ADDED Requirements

### Requirement: 实施与结果服从架构边界

Recipe/Plan JSON/YAML 版本、跨 SDK A→B→C、Artifact/Evidence 引用、验证失败阻断、WAITING_APPROVAL/INPUT 及任务级恢复；不开发完整 BPMN。 阶段 SHALL 提供可重复的实际环境证据和正确的领域/技术 Owner；不实现额外 Scheduler，不用技术 Workflow History 取代 Harness Domain 状态。

#### Scenario: 交付成功
- **WHEN** 阶段依赖满足且真实系统验收执行
- **THEN** 基于合成通用任务真实运行规划→Coding→验证三 Agent 跨 SDK Recipe，后继只接收已验证结果，审批前工具不可执行，任务级失败可恢复。

### Requirement: 必须覆盖正常流程与失败路径

每条需求 MUST 先编写可失败的正/负例，再实现最小代码，并在实际环境测试、CI 和架构审查通过后关闭。

#### Scenario: 真实异构 Recipe
- **WHEN** 规划 Agent 针对合成通用任务完成已验证结构化输出并提供 ArtifactRef
- **THEN** Coding Runtime 与测试 Runtime 分别按冻结 Recipe 执行、保留 Evidence

#### Scenario: 审批拒绝
- **WHEN** 写侧操作需要审批而尚未批准
- **THEN** 保持 WAITING_APPROVAL，拒绝执行工具，批准后仅发生一次操作

### Requirement: 未验证的结果不可升级为阶段完成

若真实测试失败、SKIPPED、BLOCKED 或缺失，里程碑 SHALL 标注证据不足与 OPEN；禁止把规划 4/4 误认作代码交付或生产上线。

#### Scenario: 真实门禁未完成
- **WHEN** 某个阶段必过 Gate 未通过或相关依赖尚未 Ready
- **THEN** DEV-M6 保持 OPEN，保留原因与整改任务