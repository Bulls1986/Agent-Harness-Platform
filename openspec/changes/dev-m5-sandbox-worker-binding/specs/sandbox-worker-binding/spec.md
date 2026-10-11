# DEV-M5 Cube 可信执行与 Coding Runtime

## ADDED Requirements

### Requirement: 实施与结果服从架构边界

SandboxProvider→Cube Scope/Lease/Fencing/WorkspaceRef 绑定、按需分配释放和 OpenCode Coding Guest；模型-only 0 Sandbox，禁止 Host Shell 兜底。 阶段 SHALL 提供可重复的实际环境证据和正确的领域/技术 Owner；不实现额外 Scheduler，不用技术 Workflow History 取代 Harness Domain 状态。

#### Scenario: 交付成功
- **WHEN** 阶段依赖满足且真实系统验收执行
- **THEN** 真实 Worker A→B 可信重连同 Workspace；跨 Scope 和旧 Owner 被拒，Shell/Git 仅在 Cube。

### Requirement: 必须覆盖正常流程与失败路径

每条需求 MUST 先编写可失败的正/负例，再实现最小代码，并在实际环境测试、CI 和架构审查通过后关闭。

#### Scenario: 可信接管
- **WHEN** Worker A 在授权 Cube 中工作后中断
- **THEN** Worker B 持有新 Lease 绑定同一 Workspace，恢复操作和已有文件

#### Scenario: 拒绝过期及越权
- **WHEN** 旧 Owner 或其他 Scope 访问 Workspace/执行 Shell
- **THEN** Fencing 和执行权限拒绝，禁止宿主 Shell 旁路

### Requirement: 未验证的结果不可升级为阶段完成

若真实测试失败、SKIPPED、BLOCKED 或缺失，里程碑 SHALL 标注证据不足与 OPEN；禁止把规划 4/4 误认作代码交付或生产上线。

#### Scenario: 真实门禁未完成
- **WHEN** 某个阶段必过 Gate 未通过或相关依赖尚未 Ready
- **THEN** DEV-M5 保持 OPEN，保留原因与整改任务