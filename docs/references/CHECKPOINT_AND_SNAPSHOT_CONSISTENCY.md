# Checkpoint 与恢复隔离契约

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-005

## 1. 核心定位

平台不重新实现底层 Runtime 的 Checkpoint / Resume 机制，也不通过 fork / patch 为 Runtime 补能力。

平台只定义统一的恢复领域模型与 Adapter 边界：

~~~text
平台恢复点（RecoveryPoint）
        ↓
Runtime Adapter
Workspace Adapter
Sandbox Provider
        ↓
各自底层实现
~~~

核心原则：

> 平台统一恢复语义与引用；底层 Framework / Provider 实现真实恢复能力。

## 2. 恢复点（RecoveryPoint）

RecoveryPoint 是平台拥有的轻量领域对象，用于关联一次可恢复状态所需要的外部引用。

建议最小字段：

~~~text
RecoveryPoint
├─ recovery_point_id
├─ run_id
├─ step_id
├─ attempt_id
├─ runtime_type
├─ runtime_checkpoint_ref?
├─ workspace_state_ref?
├─ repository_revision_set?
├─ environment_fingerprint?
├─ sandbox_snapshot_ref?
└─ created_at
~~~

说明：

- recovery_point_id 由平台生成。
- runtime_checkpoint_ref 对平台是不透明引用（Opaque Reference）。
- workspace_state_ref 由 Workspace 能力负责解释。
- sandbox_snapshot_ref 为可选，不是 RecoveryPoint 合法性的统一前提。
- Repository Revision Set 与 Environment Fingerprint 用于恢复关联与审计。
- RecoveryPoint 不保存 Runtime Checkpoint 内部结构。

## 3. Runtime 恢复能力（Runtime Recovery Capability）

不同 Runtime 可以声明不同恢复能力。

示例：

~~~text
RuntimeRecoveryCapabilities
├─ checkpoint
├─ resume
├─ durable_wait
└─ snapshot_restore
~~~

规则：

- Adapter 必须显式声明当前 Runtime 实际支持的能力。
- 平台不得把不支持的能力模拟成“支持”。
- Runtime 不支持某项恢复能力时，Capability 返回 false。
- 不因平台统一接口要求而 fork / monkey patch /复制 Runtime 内部实现。

## 4. Runtime Adapter 边界

Runtime Adapter 负责将平台恢复语义映射到底层 Framework。

~~~text
RecoveryPoint
   ↓
Runtime Adapter
   ↓
resume(runtime_checkpoint_ref)
~~~

平台只要求 Adapter 返回统一结果，不解释底层 Checkpoint 内容。

标准化恢复结果至少应能够表达：

- RECOVERED
- RECOVERY_UNAVAILABLE
- RECOVERY_FAILED
- RECOVERY_INCOMPATIBLE

若底层 checkpoint 丢失、版本不兼容或无法恢复：

> Adapter 返回标准化失败；平台不得猜测、重建或修改 Framework 内部状态。

## 5. Workspace 与 Sandbox 的边界

Workspace 与 Sandbox 的恢复能力独立于 Runtime。

建议恢复协调顺序：

~~~text
RecoveryPoint
   ↓
Workspace restore / bind
   ↓
Environment / Sandbox prepare
   ↓
Runtime Adapter.resume(...)
~~~

平台只做轻量协调，不建立跨组件分布式事务。

某一阶段失败时，返回标准恢复失败结果，由 Run 状态机按既有失败策略处理。

## 6. Sandbox Snapshot 的定位

Sandbox Snapshot 是 Provider 能力，不是平台统一恢复机制。

允许：

~~~text
sandbox_snapshot_ref = optional
~~~

如果 Provider 支持 Snapshot，可通过 Sandbox Provider 恢复。

如果不支持：

- 平台不能要求 Provider 实现。
- 可通过 Workspace + Environment 重新准备执行环境，前提是对应 Runtime / Recipe 支持该恢复路径。
- 不把 Sandbox Snapshot 当作所有 Runtime 的共同硬依赖。

## 7. 不恢复底层 Runtime 内部状态

平台不得依赖：

- MAF checkpoint 内部 executor state 布局
- Temporal history 内部实现细节
- ADK session/checkpoint 私有结构
- Provider 私有序列化格式

这些都只能通过 Adapter 持有 Opaque Reference。

因此：

~~~text
Platform Domain Model
→ stable

Runtime Checkpoint Implementation
→ replaceable
~~~

## 8. 与 Workspace/Git 的关系

Workspace 状态恢复由 ARCH-TODO-003 定义的 Workspace / Repository / Git 模型负责。

005 只保存：

- workspace_state_ref
- repository_revision_set

不重新定义：

- Git checkout / worktree
- dirty state
- commit/push
- multi-repo workspace
- Workspace retention

## 9. 与副作用恢复的关系

RecoveryPoint 不能替代副作用语义。

外部副作用仍必须遵守 ARCH-TODO-002：

~~~text
Side Effect Contract
→ Side Effect Receipt
→ Reconciliation
→ Retry / Compensation / Human Intervention
~~~

Sandbox / Runtime 恢复成功，不表示外部副作用已经被回滚。

## 10. 不在本契约范围

ARCH-TODO-005 不负责：

- Runtime 内部 Checkpoint 算法
- 自定义 Checkpoint Engine
- 分布式两阶段提交（2PC）
- 跨 Runtime / Workspace / Sandbox 补偿协议
- Snapshot GC / 长期保留策略
- Execution Lease / Fencing
- Cancellation propagation
- Workspace 实际恢复实现
- E2E / Integration Environment 恢复
- HA / DR

这些分别由现有或后续 Backlog 处理。

## 11. Accepted Rules

最终冻结：

~~~text
平台拥有 RecoveryPoint 领域模型
        ↓
Adapter 暴露底层真实能力
        ↓
底层 Framework / Provider 实现恢复
~~~

硬规则：

1. RecoveryPoint 是轻量引用模型，不是新的 Checkpoint Engine。
2. Runtime checkpoint 对平台保持 Opaque。
3. Runtime Recovery Capability 必须显式声明。
4. 不支持就是不支持；平台不模拟、不 fork、不 patch。
5. Workspace / Sandbox / Runtime 各自恢复，通过 Adapter 隔离。
6. 平台只做轻量恢复协调，不建立跨组件分布式事务。
7. 外部副作用恢复继续遵守 ARCH-TODO-002。
