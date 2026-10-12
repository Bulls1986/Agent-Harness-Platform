# sandbox-worker-binding Specification

## Purpose
定义 Agent Harness 在受控 Coding Runtime 中使用 Cube MicroVM 的执行边界：Harness PostgreSQL 持有 Run、Scope、Workspace、Owner、Lease、Fencing 和恢复/隔离终态；Hatchet 负责 Native Workflow/Retry，Cube 负责沙箱生命周期，OpenCode 通过公开 API 在真实 Guest 内执行。正常故障在没有未确认副作用时恢复原沙箱和 Session；未知 Native Tool 副作用必须阻止续跑，并在真实 Destroy ACK 后将原 Run 置为 BLOCKED_UNKNOWN，等待独立外部回执对账。此 POC 合同不承诺生产 IAM、外部副作用回滚、OCI/Git Revision 可复现或跨宿主 HA。

## Requirements

### Requirement: 实施与结果服从架构边界

SandboxProvider→Cube Scope/Lease/Fencing/WorkspaceRef 绑定、按需分配释放和 OpenCode Coding Guest；模型-only 0 Sandbox，禁止 Host Shell 兜底。 阶段 SHALL 提供可重复的实际环境证据和正确的领域/技术 Owner；不实现额外 Scheduler，不用技术 Workflow History 取代 Harness Domain 状态。

#### Scenario: 交付成功
- **WHEN** 阶段依赖满足且真实系统验收执行
- **THEN** 真实 Worker A→B 可信重连同 Workspace；跨 Scope 和旧 Owner 被拒，Shell/Git 仅在 Cube。

### Requirement: 必须覆盖正常流程与失败路径

每条需求 MUST 先编写可失败的正/负例，再实现最小代码，并在实际环境测试、CI 和架构审查通过后关闭。

#### Scenario: Cube 创建请求已发出但 Provider Binding ACK 丢失

- **WHEN** Harness 持久记录了 `CREATING`，真实 Cube 可能已经 Create 但客户端没有保存新 Sandbox ID，或者 Worker A 失联而 Lease 到期
- **THEN** Harness MUST NOT 重新 Create；只有当前 PG Owner 经 Scope/Workspace/Environment/Fencing 授权、完整校验 Cube Native List/Connect/GetInfo 的 **唯一同一 Allocation 元数据和 Sandbox ID**，才可将 `BLOCKED_UNKNOWN` 原子确认成 `ACTIVE`；无、重复、冲突或 Provider 查询错误继续 UNKNOWN，不创建空白 Workspace 或 Host fallback

#### Scenario: 可信接管
- **WHEN** Worker A 在授权 Cube 中工作后中断
- **THEN** Worker B 持有新 Lease 绑定同一 Workspace，恢复操作和已有文件

#### Scenario: 真实物理 Worker 与真实 Cube 统一故障门禁（DEV-M5-B03）
- **WHEN** 真实 Hatchet Worker A 已为同一 Run/Execution 在真实 Cube Guest 写入数据，A 进程组被操作系统 SIGKILL，Hatchet 将原 Workflow Task Retry 分配给独立 B 进程
- **THEN** B MUST 通过 PG Fencing 更新 Owner Epoch，使用原生 Cube SDK 连接持久化的**原 Sandbox ID**并验证原 Guest 字节；旧 A Epoch/错误 Scope 的访问 MUST 在可信执行边界拒绝；Provider ACK 确认资源释放，记录 OS PID/exit code、Workflow/Run/Execution/Provider ID 和实际 Guest 证据；拆开的 Worker 与 Cube 两项 PASS 不能替代本场景。

#### Scenario: 拒绝过期及越权
- **WHEN** 旧 Owner 或其他 Scope 访问 Workspace/执行 Shell
- **THEN** Fencing 和执行权限拒绝，禁止宿主 Shell 旁路

#### Scenario: OpenCode Native Tool 结果未知且原 Guest 必须销毁
- **WHEN** 原生 OpenCode Guest Shell 已开始运行，但 HTTP ACK 不明、Worker Lease 过期、PG Guest Effect 仍为 DISPATCHED
- **THEN** B MUST NOT 接管或重派此工具；可信隔离流程 MUST 复核原 Scope/Workspace/Environment 和 Native Cube ID/可信元数据，再经 Provider Destroy ACK 验证原 Guest 被销毁，并在 PG 同一事务记录父 Run BLOCKED_UNKNOWN；未知外部 Tool Effect 继续留存等待独立对账。没有 Destroy ACK 时状态必须继续不确定；不得把销毁当作业务成功或外部效果回滚。

### Requirement: 未验证的结果不可升级为阶段完成

若真实测试失败、SKIPPED、BLOCKED 或缺失，里程碑 SHALL 标注证据不足与 OPEN；禁止把规划 4/4 误认作代码交付或生产上线。

#### Scenario: 真实门禁未完成
- **WHEN** 某个阶段必过 Gate 未通过或相关依赖尚未 Ready
- **THEN** DEV-M5 保持 OPEN，保留原因与整改任务
