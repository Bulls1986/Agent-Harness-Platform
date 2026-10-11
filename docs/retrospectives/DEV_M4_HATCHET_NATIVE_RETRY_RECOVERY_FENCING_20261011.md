# DEV-M4 / DEV-M5：Hatchet 原生 Task Retry + 持久 UNKNOWN Receipt 与 PG Fencing（2026-10-11）

## 范围与门禁分层

这次是 M4/M5 联动的**平台通用、合成数据开发切片**，不触碰任何私有消费者或其代码。分两道独立证据：

1. **真 Hatchet Task Native Retry / HC-02**：Pinned Python SDK `1.42.1` + Embedded Engine `v0.110.5` 使用 Engine 自身的 retries=1（没有外置调度器）。首个 Task Attempt 登记 PG Intent/Dispatch；独立外部 PG 不提供幂等，写入一次后 Tool 子进程在返回 Receipt 之前被系统 SIGKILL；Task 上报失败，Hatchet 自己重新派发 Task；重试 Handler 只读 UNKNOWN、查外部唯一 Effect、补持久 Receipt，绝不再次调用写入。
2. **PG Server-side Owner/Fencing / HC-03**：`harness_tool_recovery_authority` 原子记录 Owner ID、Fencing Epoch、Lease Expires At。接管只能在 PG 时钟确认 Lease 过期，且原 Tool 已 UNKNOWN、Plan Version/Run/Provider 绑定一致时进行；新的 Owner 可核对 Receipt，不得到重新派发 Tool 的权限。Receipt 事务在相同 Run/Tool/Owner 锁下二次校验 Owner+Epoch+Lease，拒绝旧 Owner 的迟到写入或“查询期间夺权”的 TOCTOU。

**严格不宣称**：第 1 项的 `SIGKILL` 是 Tool 子进程，不是整个 Hatchet Worker A；第 2 项的 B 是**受信任 PG 领域执行 Owner**，不是已经实测的另一台 Hatchet Worker B，也未涉及 Cube/Workspace/OCI/Policy/Sandbox/Runtime tool-bridge。此切片不会关闭 DEV-M4、DEV-M5、任何生产准入。

## Red → Green 实际证据

- 首轮正式 M4 Tool SIGKILL/Receipt 已见 [PR #70](https://github.com/Bulls1986/Agent-Harness-Platform/pull/70)，本轮不重新造工具和外部账本。
- 新增 `verify_hatchet_tool_receipt_retry.py` 和 CI 强制执行真实 Hatchet 重试（3 个 PostgreSQL 数据库：Harness、Hatchet、非幂等外部账本）。第一次 [Green CI 38144717124](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38144717124)：11/11 已有双 PG 测试 PASS、真实 Hatchet Workflow `2acc7b16-dd4c-4378-abfc-896c62c02139`，`native_retry_count=1`、`tool_dispatch_events=1`、`external_effect_count=1`、Receipt `CONFIRMED_SUCCESS`。
- 第二道 PG Owner/Fencing 先加 `test_tool_recovery_owner_pg.py` 再实现，[Red CI 38144912825](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38144912825) 因 `tool_recovery_owner` 不存在失败，真实 PG/工具门禁先行。
- 实现 `ToolRecoveryOwner`，并将 `ToolReceiptJournal.reconcile` 写入事务与当前 Owner+Epoch+Lease 的校验绑定；[中间 Green CI 38144996290](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38144996290) 实际 PG/Native Hatchet CI SUCCESS、旧 Inspector/架构 CI SUCCESS。
- 将 PG 领域 Owner A→B 的 Epoch 7→8 交接也并入真实 Hatchet 原生重试 Handler，首个 Attempt 等待 POC 受信任 PG Intent/Binding；后续 Retry MUST 从 PG 获取新 Permit 才可核对外部 Receipt。最终结果及 CI 以 PR #71 最新 Head 为准；本复盘不能提前声明整个 Worker 接管通过。

## 核心负例与经验

- **不以“Engine Retry”取代 Tool 决策**。即使 Hatchet 自动重复投递 Task，Tool 状态不是 `RECORDED` 就绝不再次外部调用。
- **Lease 到期不意味着副作用未发生**。B 仅可接管 UNKNOWN 的查询权；确认唯一 Receipt 后复用原 Attempt 结果，不产生新的写请求。
- **线程/SDK 不可信**。Owner/Epoch 不是 Workflow Payload、自报 Session 或环境变量授权依据；PG Row-Lock/CAS 和服务器时钟才是当前子切片的可信执行事实。
- **PG 不重建 Engine Scheduler**。Task 的实际 retry、排队和任务计数完全由 Hatchet 负责。Harness 只持有 Execution 控制权和 SideEffect Receipt。
- **不可撤回已经发出的外部请求**。Owner Revocation/Fencing 只能阻止后续经控管入口的动作、Outcome/Receipt 写入；旧进程已在外部落盘的行为必须对账。没有外部证明就 UNKNOWN/等待人工。

## 待完成的真实阶段门禁

- Hatchet **Worker A 实际进程 SIGKILL** 后，由**另一进程 Worker B** 接收同一 Workflow Task、在真实技术调度下取得可信执行许可；包括 A 延迟恢复及 B Lease 续约/撤销。
- 真 Cube Allocation、Sandbox/WorkspaceRef、OpenCode Guest Shell/Files/Git、跨 Scope/Environment/OCI 与资源回收。
- 多类型 Tool Adapter 及审批/Policy、真实外部系统 Receipt 可信查询、额外长期不确定/并发/乱序边界。
- DEV-M3 多 Plan/Step/Attempt 通用业务终态、M4 通用 Outbox/Inbox、M9 高负载/生产。阶段状态均 OPEN，Production NO-GO。
