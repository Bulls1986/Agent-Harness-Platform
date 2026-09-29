# Task Recovery Coverage & Recovery Semantics 契约

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-010

## 1. 核心定位

本契约只定义任务级恢复（Task-level Recovery）：

> 一个 Run 为了在 Worker / Runtime / Sandbox / 进程故障后安全继续，平台必须持久化哪些事实，以及在当前 Runtime / Workspace Capability 下最多可以恢复到哪里。

本契约不定义平台基础设施 HA / DR / Backup，不负责数据库、对象存储、磁盘或集群容灾。

## 2. 恢复事实

平台必须持久化足以解释当前任务位置与安全恢复决策的事实：

~~~text
Run
├─ lifecycle_state
├─ frozen recipe/runtime/policy/environment versions
├─ initiator/security context reference
├─ Plan versions
│  └─ Step states
│     └─ Attempt states
│        └─ Execution states
├─ RuntimeBinding
│  ├─ runtime_type
│  ├─ native_instance_id?
│  └─ runtime_checkpoint_ref?
├─ RecoveryPoint [0..N]
├─ Workspace / Repository Revision references
├─ Environment Fingerprint
├─ Approval / Waiting state
├─ Artifact / Evidence references
├─ SideEffectReceipt
└─ Reconciliation state
~~~

平台保存恢复所需的事实和引用，不复制 Runtime 内部 checkpoint 内容。

## 3. RuntimeBinding 与 RecoveryPoint

RuntimeBinding 用于定位当前 Run / Attempt 所绑定的底层 Runtime 实例；RecoveryPoint 用于引用可恢复状态。

规则：

- native_instance_id / runtime_checkpoint_ref 对平台保持 Opaque。
- MAF / Temporal / ADK 等 Runtime 的内部 history / checkpoint 不进入平台领域模型。
- RecoveryPoint 可以关联 runtime checkpoint、workspace state、repository revision set、environment fingerprint 与可选 sandbox snapshot。
- checkpoint reference 存在不代表一定可恢复；恢复时必须由 Runtime Adapter 实际验证。

## 4. 任务恢复能力

Run 启动前应基于已冻结 Runtime / Workspace / Sandbox Capability 解析任务恢复能力。

建议最小能力：

~~~text
TaskRecoveryCapability
├─ durable_wait
├─ step_resume
├─ runtime_checkpoint_resume
├─ workspace_restore
└─ sandbox_snapshot_restore
~~~

这些能力描述真实 Provider 能力，不允许平台伪装支持。

## 5. 恢复粒度

### 5.1 Waiting State Resume

WAITING_INPUT、WAITING_APPROVAL 等平台持久状态必须能够恢复为同一个 Run 的同一等待状态。

~~~text
Same Run
Same Waiting State
~~~

这不依赖 Runtime checkpoint。

### 5.2 Step Boundary Recovery

当 Runtime checkpoint 不可用，但平台持久化状态足以确定已完成 Step 和当前失败 Step 时，可以恢复任务进度到安全 Step Boundary：

~~~text
Same Run
Same Step
New Attempt
~~~

前提是当前 Step / Execution 根据失败与副作用契约可以安全重试。

### 5.3 Same Attempt Resume

当 Runtime 提供真实 checkpoint/resume 能力且 checkpoint 可用时，可以恢复同一次 Attempt：

~~~text
Same Run
Same Step
Same Attempt
Resume Runtime
~~~

这属于 Resume，不属于 Retry，不得错误创建 New Attempt。

MAF Durable / Temporal 等是否能够做到该级别，由对应 Runtime Adapter 的真实能力与 POC 结果决定。

### 5.4 Workspace State Recovery

Coding 任务的 Runtime 恢复与 Workspace 恢复是两个独立维度。

完整恢复可能需要：

~~~text
Platform State
+ Runtime State
+ Workspace State
~~~

Sandbox 实例本身不是必须恢复的对象。允许销毁旧 Sandbox、创建新 Sandbox、重新绑定可恢复 Workspace 后继续任务。

Sandbox Snapshot 是可选加速/Provider 能力，不是任务恢复语义的硬依赖。

## 6. Recovery Degradation Order

故障后必须选择最深且安全的恢复点，建议降级顺序：

~~~text
Same Attempt Resume
        ↓ unavailable / incompatible
Same Step + New Attempt
        ↓ unsafe because outcome uncertain
UNKNOWN → Reconciliation
        ↓ cannot safely continue
Fail / Wait Human
~~~

不得因为缺少 Runtime checkpoint 就默认从整个 Run 起点重跑。

## 7. RUNNING Execution 的特殊处理

恢复前处于 RUNNING 的 Execution 必须结合 ARCH-TODO-008 的 Lease/Fencing 与 ARCH-TODO-002 的 Side Effect Contract 判断。

如果可以证明尚未 dispatch 或未产生副作用，可以进入安全 Retry。

如果外部副作用可能已经发出但结果未知：

~~~text
RUNNING before failure
→ ownership invalidated
→ UNKNOWN
→ Reconciliation
~~~

即使 Runtime checkpoint、Workspace、Platform State 全部存在，也不能绕过 Reconciliation。

## 8. Approval / Input Waiting

WAITING_APPROVAL / WAITING_INPUT 属于平台控制状态：

- 必须持久化 pending request、关联 Run/Step/Execution、requester、policy/action/resource context。
- 恢复后继续同一个 Run，而不是创建新的 Run。
- Runtime 若支持 durable wait，可恢复其底层等待实例；若不支持，平台仍必须保留业务等待事实，并由 Adapter/Workflow 选择安全恢复路径。

## 9. Artifact / Evidence / SideEffectReceipt

恢复不要求复制全部日志内容，但以下引用/事实不能因进程重启丢失：

- 已形成的 Artifact / Evidence references；
- 已完成 Verification 结果；
- Approval Decision；
- 非 PURE Execution 的 SideEffectReceipt；
- Reconciliation state 与结论。

这些事实用于避免已完成工作或外部副作用被重复执行。

## 9.1 Retention / GC 约束

任务恢复依赖与 Retention Policy 必须一致：

- 当前 Run 仍可恢复时，RecoveryPoint 依赖的 Artifact / Evidence / workspace_state_ref / snapshot reference 必须保持 PIN。
- 只有当 Run 不再需要该恢复依赖，或对应 RecoveryPoint 已失效/释放后，Payload 才可进入 GC。
- Artifact / Evidence Payload 即使被后续清理，其最小 Metadata / Lineage / content digest 仍应保留，以解释历史恢复与 Verification 结果。
- 大 Payload 默认由 OSS / Object Storage 承载，平台状态库只保存引用与事实。

详见 ARTIFACT_EVIDENCE_LOG_RETENTION.md。

## 10. MAF 映射

对于普通 MAF Runtime：

~~~text
Platform State
+ external Session / History / Checkpoint capability if available
→ recover to supported boundary
~~~

若无可用 Runtime checkpoint，通常只能恢复到平台能够证明安全的 Step Boundary，并创建 New Attempt。

对于 MAF Durable：

~~~text
Run / Attempt
→ RuntimeBinding
→ native durable instance / checkpoint ref
→ Durable backend
~~~

若 Durable backend 中对应实例仍可恢复，则允许 Same Attempt Resume。Harness 不复制 Durable Task history，也不实现第二套 Durable recovery engine。

## 11. 不在本契约范围

- PostgreSQL / MSSQL / Object Storage 的物理备份；
- 数据库复制、主从、快照、磁盘容灾；
- Control Plane / Scheduler 服务级 HA；
- Kubernetes / Region / Cluster DR；
- 跨 Region Active-Active；
- Runtime 内部 checkpoint 算法；
- Workspace retention / snapshot GC；
- Cancellation / Timeout propagation。

## 12. Accepted Rules

1. 平台任务恢复依赖持久化业务执行事实 + 底层 Recovery Reference，不复制 Runtime 内部状态。
2. WAITING_INPUT / WAITING_APPROVAL 必须恢复同一个 Run 的等待状态。
3. 无 Runtime checkpoint 时，最多恢复到安全 Step Boundary，并通过 Same Step + New Attempt 继续。
4. 有真实 Runtime checkpoint/resume 能力时，允许 Same Run + Same Step + Same Attempt Resume；Resume 不等于 Retry。
5. Runtime State、Workspace State、Sandbox State 是独立恢复维度；Sandbox 实例不是任务恢复硬依赖。
6. RUNNING Execution 故障后不能 blind resume/retry；结果不确定必须进入 UNKNOWN → Reconciliation。
7. 恢复优先选择最深且安全的恢复点，不默认从整个 Run 起点重跑。
8. Runtime/Workspace 不支持某种恢复能力时，平台必须显式降级，不模拟、不 fork、不 patch。
9. 数据库/磁盘/集群 Backup 与 DR 不属于本 Task Recovery Contract。