# DEV-M9 生产交付与运营验收

## ADDED Requirements

### Requirement: 实施与结果服从架构边界

自托管部署 Runbook、配置/Secret 与 OTel 接入、权限安全/故障恢复/灰度回滚、100 Active Runs 真实资源与性能测量；不自建 IAM/备份平台。 阶段 SHALL 提供可重复的实际环境证据和正确的领域/技术 Owner；不实现额外 Scheduler，不用技术 Workflow History 取代 Harness Domain 状态。

#### Scenario: 交付成功
- **WHEN** 阶段依赖满足且真实系统验收执行
- **THEN** Harness 平台安全隔离、可靠恢复、真实容量、部署/回滚 Gate 全部 PASS 后才允许 Production GO；特定私有应用的等价性、迁移和上线不构成平台 Gate。

### Requirement: 必须覆盖正常流程与失败路径

每条需求 MUST 先编写可失败的正/负例，再实现最小代码，并在实际环境测试、CI 和架构审查通过后关闭。

#### Scenario: 真实容量与恢复
- **WHEN** 在确认环境下运行 100 Active Runs 并杀 Worker/断网络
- **THEN** 记录延迟/吞吐/内存/CPU/Cube 密度及恢复证据，不用 Mock 替代

#### Scenario: 生产 NO-GO
- **WHEN** 业务功能通过但权限、Receipt UNKNOWN、隔离或回退 Gate 未通过
- **THEN** 必须维持 Harness Production NO-GO 且不得开放未通过门禁的生产执行入口

### Requirement: 未验证的结果不可升级为阶段完成

若真实测试失败、SKIPPED、BLOCKED 或缺失，里程碑 SHALL 标注证据不足与 OPEN；禁止把规划 4/4 误认作代码交付或生产上线。

#### Scenario: 真实门禁未完成
- **WHEN** 某个阶段必过 Gate 未通过或相关依赖尚未 Ready
- **THEN** DEV-M9 保持 OPEN，保留原因与整改任务