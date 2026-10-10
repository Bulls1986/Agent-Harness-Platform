# HC-03 · Hatchet Worker ↔ ExecutionContext ↔ Cube Sandbox Binding Contract

> **2026-10-10 · DECIDED / Architecture Implementation Contract**（安全边界与操作语义冻结，Cube/Worker 跨故障真实联动仍待验）。
> 依赖：[Accepted Execution Lease/Fencing](EXECUTION_LEASE_FENCING_HEARTBEAT.md)、[Identity](IDENTITY_AND_AUTHORIZATION_PROPAGATION.md)、[Task Recovery](TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md)、[Workspace/Git](WORKSPACE_AND_GIT_MODEL.md)、[Mapping HC-01](HATCHET_WORKFLOW_MAPPING_CONTRACT_20261010.md)、[Consistency HC-02](HARNESS_HATCHET_CONSISTENCY_CONTRACT_20261010.md)、[ADR-031](THIN_HARNESS_CONTROL_PLANE_DECISION_20261010.md)。

## 1. 权威与强制粒度

- **Hatchet Engine**：领取/派发/重分配 Task 的唯一 Durable Owner；内部 Worker 心跳/调度不由 Harness 重实现。
- **Harness 可信 Execution Boundary**：对每一次真实受控动作 `execution_id` 颁发/续签/撤销执行资格；基于平台原子事实 CAS `owner_id + fencing_epoch + lease_expiry + capabilities`，不另造全局分布式锁服务。
- **AgentRuntime SPI**：执行 Pydantic/OpenAI/OpenCode/MAF 所选 Runtime，通过统一授权 Context/Tool Bridge；不能用 Hatchet Task ID、Worker ID 或模型/用户自报字段替代授权。
- **SandboxProvider SPI / Cube**：按获准 `IsolationScope` 获取/创建/续连/释放 Cube Sandbox 和 WorkspaceRef。Sandbox ID 是 Locator/Binding，不是 Capability/凭据。
- **Session 生命周期独立**：`Conversation/Session ≠ Run ≠ Attempt ≠ Worker ≠ Sandbox`。一个共享 Worker 可执行多个逻辑 Session；无 Shell/Files 需求应是 **0 Sandbox**。同 Scope 重用 Sandbox **可以**但不是硬性 1 Session ↔ 1 Sandbox。
- **Coding 默认 Harness-in-Cube**：OpenCode 2 的原生 FS/Shell/PTY/Git/LSP/Plugin 若不能用可信 Tool Adapter 全路径安全重定向，必须在 Cube Guest 执行；**禁止以共享 Host 执行再靠 Session ID 自动隔离**。

## 2. 可信 ExecutionContext（逻辑 Port，不是裸用户传入 JSON）

```yaml
ExecutionContext:
  run_id: platform-run
  step_id: platform-step
  attempt_id: platform-attempt
  execution_id: platform-execution
  plan_version: 3
  provider_binding_ref: opaque
  principal_ref: initiator-and-executor-binding
  isolation_scope: canonical-scope-ref
  workspace_ref: immutable-or-versioned-workspace-ref
  runtime_adapter_version: frozen-exact-version
  environment_digest: immutable-oci-digest
  capabilities: [files.read, files.write, shell.exec]
  execution_owner: worker-lease-identity
  fencing_epoch: 13
  lease_expires_at: provider-independent-expiry
  policy_decision_ref: signed-or-server-side-fact
  sandbox_binding_ref: optional-opaque-ref
```

该结构由 Harness 根据当前持久 Run/Policy/Grant/ProviderBinding 生成，**不信任**来自 Hatchet Workflow payload、Agent prompt、用户参数、SDK Session、Sandbox ID 或自报 `scope` 的授权字段。Workflow Payload 只允许非机密的业务关联/冻结摘要，长期 SSO Token/Secret 不进入引擎持久输入、Prompt 或 Cube Guest。

验证要求：匹配 **run/step/attempt/execution + current owner + fencing epoch + scope + capabilities + version + expiry**；任一缺失、未知、过期或不一致返回 `UNAUTHORIZED / STALE_EXECUTION_OWNER / LEASE_EXPIRED / CAPABILITY_NOT_GRANTED / SCOPE_MISMATCH`，**Fail Closed**。

## 3. Worker 开始 Step 的绑定顺序

```mermaid
sequenceDiagram
  participant H as Hatchet Engine
  participant W as Worker + AgentRuntime SPI
  participant A as Harness Execution Gate
  participant P as SandboxProvider SPI
  participant C as Cube Sandbox/Guest
  participant F as Harness Task Facts
  H->>W: Dispatch Task (opaque Provider refs)
  W->>A: Verify binding + acquire execution permit
  A->>F: Atomic owner/epoch claim + policy/capability validation
  F-->>A: current permit/expiry or REJECT
  A-->>W: Trusted ExecutionContext (not Session token)
  alt Need files/shell/git
    W->>P: ensure_sandbox(verified scope/workspace + permit)
    P->>F: validate binding revision + lease epoch
    P->>C: connect same authorized sandbox or create/restore
    C-->>P: SandboxRef + WorkspaceRef + generation
    P-->>W: Bound capability-scoped Tool/Guest endpoint
  else Pure model/non-shell run
    Note over W,P: Zero Sandbox; no idle VM allocation
  end
  W->>A: Verify permit before each controlled side-effect Tool
  W->>C: Authorized Guest Tool invocation (only when bound)
  W->>F: Outcome/Receipt/Event with current fencing
```

- 真正调用外部 Tool 前仍需 **HC-02 侧效 Intent**，不能仅凭 Worker 已启动就允许对外写。
- Runtime SDK 可以因并发共享 Worker 实例，但每个 Run 请求的 Tool/WorkspaceRef 路由必须来自当前 ExecutionContext；不得通过进程全局可写 cwd/sandbox 单例泄漏。
- 若拒绝权限，AgentRuntime 不能静默回退到 Host Shell、本地 Workspace 或另一个已有 Sandbox；错误必须进入平台可诊断 Event/Outcome。

## 4. Sandbox 绑定与复用策略

建议逻辑持久字段：`sandbox_binding_id`, `provider_sandbox_id`, `isolation_scope`, `workspace_ref`, `environment_digest`, `binding_generation`, `lease_owner`, `lease_expiry`, `last_verified_state`, `recovery_capability`。

- **仅当**真实 Principal/Project/Repo/Secret/Policy Scope 允许，且 WorkspaceRef/Revision/OCI Environment 与当前 Run 冻结版本兼容时，才能在同 Sandbox 上复用多个 Session 或 Step。
- **No-Sandbox Agent**（如只调用模型、远程只读 HTTP）不得隐式触发 Cube 资源申请；需要本地编译/FS/Shell 的执行才占 Sandbox 资源。
- **执行资格 ≠ Sandbox 生命周期**：执行 Lease 到期禁止再发新命令，但 Workspace/Sandbox 是否暂留由 Provider Policy/资源预算决定；禁止自动销毁仍承载活跃其他有效 Scope 绑定的 Sandbox。
- **Workspace ≠ Sandbox**：如果 Cube 实例不复存在，可以创建新实例并依据受信任 Git Revision/OSS Artifact/CheckpointRef 恢复 Workspace；无法恢复同一代码事实时显式 `WORKSPACE_RECOVERY_UNSUPPORTED`，不能以空目录冒充原 Workspace。
- 生产环境不承诺跨隔离 Scope 的文件共享；同一 Sandbox ID 不意味着获得该 Sandbox 的读取/操作授权。

## 5. Worker A 崩溃、Worker B 接管的安全语义

| 阶段 | 必须做什么 | 禁止 |
|---|---|---|
| Hatchet A 失联，Engine 派发 B | 由 Hatchet 负责 Worker/task 故障接管；B 根据 Provider Binding 定位平台 Execution | Harness 新增通用 WorkerRecoveryDaemon 接管引擎职责 |
| B 领取执行资格 | 平台事务核对上一次 owner/expiry、原 Tool Intent/Receipt、增大 Fencing epoch；仅在副作用可证明安全时允许 Resume/New Attempt | Lease 过期就直接重试非幂等 Tool |
| 原 Sandbox 仍存活 | B 通过 SandboxProvider 校验 Scope/Generation/Environment/WorkspaceRef，使用公开 Cube connect，同一 Sandbox 继续 | 凭裸 sandbox_id 或 A 的内存缓存访问 |
| 原 Sandbox 已毁 | 依 Git/OSS/RecoveryPoint 恢复受控 Workspace 或返回明确 UNSUPPORTED/等待人工 | 把新的空 VM 当作旧状态 |
| A 恢复网络并上传旧结果 | 以 stale fencing 拒绝状态写入、授权 Tool、Outcome 终态提交；外部已发生副作用进入 Receipt/核对事实 | 让 A 覆盖 B 的状态/重新得到旧 token |
| B 继续 | 根据 HC-01 的 Same Attempt Resume 或 Same Step New Attempt 语义执行；Version/Scope 不漂移 | 重启整个 Run 重跑已完成步骤 |

**关键限制**：平台 Fencing 只能拒绝**经平台网关的后续受控操作**；对于已经交付给外部系统的 Shell/HTTP/Git 调用，不能假装可追回。因此可能在旧 A 崩溃前发生外部副作用、且无法核验时，必须先 `UNKNOWN → Reconciliation`。如某原生 Guest/SDK 路径无法实施当前 Scope/Fencing，**不赋予生产可写 Capability**，可返回 UNSUPPORTED 或限制为安全只读 POC。

## 6. 资源与调度权责分隔

- Hatchet 的 Queue/Worker/Retry/Concurrency/Backpressure 是**技术排队权威**，Harness 不创建第二套竞争的 Durable 队列与任务调度器。
- Harness 仅提供 `resource_class`、`admission/policy decision`、`sandbox_required`、`scope`、`max_runtime/cancel` 等约束，映射到 Hatchet Queue/Worker/Label/并发配置与 Cube Provider 的可用容量。
- 资源指标分开核对：**100 Idle Sessions**、**100 Active Light Agent Runs**、**100 Active Heavy Coding/Build Executions** 是三类不同负载，不猜 Worker/VM 密度或阈值。
- Engine/Worker 可扩容，但不能因扩容产生每个历史 Session 一个永久进程/Volume/VM；Sandbox 生命周期按活跃执行与策略释放。
- **Hatchet 内置并发设置不能当作 Harness Policy 授权**，也不能代替 CPU/Memory/Cube Slot 外围准入检查。

## 7. 失败与负例验收矩阵（尚待集成验证）

- B01 100 个 Idle Session、零需 Shell 请求：`sandbox_create_count=0`，不因历史会话常驻 100 个 Agent 进程。
- B02 同 Scope、同冻结 Workspace/Environment：两个合法 Session/Runtime 顺序读取同 Sandbox 数据；不同 Scope/过期 Lease/未知 Sandbox ID **拒绝**，不回退 Host。
- B03 Worker A 在完成文件修改后崩溃，B 重新连接真实 Cube 并读取相同 WorkspaceRef；平台 Fencing epoch 递增，旧 A 的后续写被拒绝。
- B04 Cube 实例消失：使用真实 Git Revision/OSS 恢复，或返回 UNSUPPORTED；不假装原文件存在。
- B05 对外有副作用 Tool 调用未 ACK 就 A 崩溃：B 必须先 UNKNOWN/Receipt 对账，不能重复发写操作。
- B06 跨项目/Principal/Repository Revision/OCI Digest/Secret Scope/Capability 不匹配，一律 Fail Closed。
- B07 OpenCode Guest 的 FS/Shell/PTY/Git/LSP/Plugin 入口：未明确隔离的路径不得获得生产写权限；真实 SDK/Tool Bridge 不因原生 session ID 改变 Scope。
- B08 取消/Timeout + Worker Failover：直到实际终止才可确认 CANCELLED；过期 Owner、Session 和 Sandbox 引用不得恢复已失效授权。
- B09 100 并发分类记录 CPU/RSS、Sandbox/Worker 数、队列等待、失败清理与资源回收；结果实测，不以简单 POC 预测容量。

**结论：Worker/Execution/Sandbox Trust Binding DECIDED；真实 Cube 多 Worker/Fencing/授权密度、重连、性能门禁仍在 ARCH-TODO-025～028 中实施验收。**
