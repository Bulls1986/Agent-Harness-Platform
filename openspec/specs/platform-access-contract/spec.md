# platform-access-contract Specification

## Requirements

### Requirement: 实施与结果服从架构边界

统一 Conversation/Turn/Run、文件引用、Typed SSE、Run/Agent/Recipe 选择、项目与授权上下文输入和用户能看懂的执行结果；Inspector 仅调试，企业 IAM 仍外部。 阶段 SHALL 提供可重复的实际环境证据和正确的领域/技术 Owner；不实现额外 Scheduler，不用技术 Workflow History 取代 Harness Domain 状态。

#### Scenario: 交付成功
- **WHEN** 阶段依赖满足且真实系统验收执行
- **THEN** 在已授权的 API/旧 UI 接入中稳定浏览历史、模型/工具结果和 Artifact/审核，跨用户和跨项目访问拒绝。

### Requirement: 必须覆盖正常流程与失败路径

每条需求 MUST 先编写可失败的正/负例，再实现最小代码，并在实际环境测试、CI 和架构审查通过后关闭。

#### Scenario: 统一 Run 视角
- **WHEN** 同一会话内不同 SDK 产生文本、工具、文件和审批事件
- **THEN** 统一 API/页面关联 Turn/Run/Step、流式进度和最终结果

#### Scenario: 权限和事件隔离
- **WHEN** 用户读取其他项目的 Run/SSE/OSS 引用
- **THEN** 安全拒绝且不泄漏事件/链接

### Requirement: 未验证的结果不可升级为阶段完成

若真实测试失败、SKIPPED、BLOCKED 或缺失，里程碑 SHALL 标注证据不足与 OPEN；禁止把规划 4/4 误认作代码交付或生产上线。

#### Scenario: 真实门禁未完成
- **WHEN** 某个阶段必过 Gate 未通过或相关依赖尚未 Ready
- **THEN** DEV-M7 保持 OPEN，保留原因与整改任务