# run-plan-domain Specification

## Purpose
冻结并验证原始 DEV-M3 限定交付：真实 Hatchet Workflow 经批准 Replan 生成同一平台 Run 的 v2 Plan 与独立 Segment，业务事实由 Harness 管理，且旧 Attempt 不得改写新版本；生产级通用恢复归原有后续阶段。

## Requirements

### Requirement: 实施与结果服从架构边界

Run/Plan/Step/Attempt 领域事实与状态机、Plan 版本、Replan 新 Segment、Workflow ID Binding，不重写 Hatchet DAG/Queue。 阶段 SHALL 提供可重复的实际环境证据和正确的领域/技术 Owner；不实现额外 Scheduler，不用技术 Workflow History 取代 Harness Domain 状态。

#### Scenario: 交付成功
- **WHEN** 阶段依赖满足且真实系统验收执行
- **THEN** 一条真实 Hatchet Run 经 Replan 生成 v2 Plan/独立 Segment，旧 Attempt 不得继续完成。

### Requirement: 必须覆盖正常流程与失败路径

每条需求 MUST 先编写可失败的正/负例，再实现最小代码，并在实际环境测试、CI 和架构审查通过后关闭。

#### Scenario: 合法 Replan
- **WHEN** 已有 Run 在执行 Plan v1 时收到经批准的 Replan
- **THEN** 生成 v2 Plan 和新的 Workflow Segment，旧 Plan/Attempt 仅留审计而不会覆盖

#### Scenario: 拒绝过期执行者
- **WHEN** 旧 Worker 携带旧 Plan Version/Attempt 提交完成事实
- **THEN** 平台拒绝旧写入，业务终态未被污染

### Requirement: 未验证的结果不可升级为阶段完成

若真实测试失败、SKIPPED、BLOCKED 或缺失，里程碑 SHALL 标注证据不足与 OPEN；禁止把规划 4/4 误认作代码交付或生产上线。

#### Scenario: 真实门禁未完成
- **WHEN** 某个阶段必过 Gate 未通过或相关依赖尚未 Ready
- **THEN** DEV-M3 保持 OPEN，保留原因与整改任务