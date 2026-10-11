# DEV-M4 持久一致性、Receipt 与任务级恢复

## ADDED Requirements

### Requirement: 实施与结果服从架构边界

PG transactional Outbox/Inbox、Provider 查询/ACK-loss Reconciliation、Tool Intent/Receipt/UNKNOWN、故障注入后的任务级恢复；不能以跨库 2PC 或自行重建 Scheduler 解决。 阶段 SHALL 提供可重复的实际环境证据和正确的领域/技术 Owner；不实现额外 Scheduler，不用技术 Workflow History 取代 Harness Domain 状态。

#### Scenario: 交付成功
- **WHEN** 阶段依赖满足且真实系统验收执行
- **THEN** 真实 PG/Hatchet 和非幂等工具在丢 ACK/SIGKILL/并发重试下可核对且不盲目重复副作用。

### Requirement: 必须覆盖正常流程与失败路径

每条需求 MUST 先编写可失败的正/负例，再实现最小代码，并在实际环境测试、CI 和架构审查通过后关闭。

#### Scenario: 创建 ACK 丢失
- **WHEN** Provider Workflow 已接受而 Harness 创建调用超时
- **THEN** 进入 BLOCKED_UNKNOWN，查询 Provider 并对账，不盲目重复创建

#### Scenario: 副作用 UNKNOWN
- **WHEN** 外部工具已经写入，Worker 在返回 Receipt 前 SIGKILL
- **THEN** 核对实际副作用；未知则人工介入或保持阻断，绝不自动重放

### Requirement: 未验证的结果不可升级为阶段完成

若真实测试失败、SKIPPED、BLOCKED 或缺失，里程碑 SHALL 标注证据不足与 OPEN；禁止把规划 4/4 误认作代码交付或生产上线。

#### Scenario: 真实门禁未完成
- **WHEN** 某个阶段必过 Gate 未通过或相关依赖尚未 Ready
- **THEN** DEV-M4 保持 OPEN，保留原因与整改任务