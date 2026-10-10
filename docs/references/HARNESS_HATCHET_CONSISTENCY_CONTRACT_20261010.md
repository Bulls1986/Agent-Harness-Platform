# HC-02 · Harness ↔ Hatchet Execution Consistency Contract

> **2026-10-10 · DECIDED / Architecture Implementation Contract**（故障语义、事实 Ownership 和最小一致性策略冻结；具体数据库 DDL 与真实注入待实施验收）。
> 依赖：[ADR-031](THIN_HARNESS_CONTROL_PLANE_DECISION_20261010.md)、[Accepted Failure/Receipt](FAILURE_IDEMPOTENCY_AND_RECOVERY.md)、[Domain/Event](DOMAIN_MODEL_AND_STATE_CONTRACT.md)、[Recovery](TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md)、[Mapping HC-01](HATCHET_WORKFLOW_MAPPING_CONTRACT_20261010.md)。
>
> **禁止两套权威竞争：** Hatchet 保存 WorkflowRun/TaskRun 技术事实；Harness 保存 Run/Plan/Step/Attempt/Execution 的必要业务事实、Approval/Verification/Receipt、事件游标与可重建投影。Provider History 是核对依据，不是平台 Domain/Event 的替代。

## 1. 一致性目标及明确不承诺

- **控制层至引擎：** 不采用跨 Harness PostgreSQL 与 Hatchet PostgreSQL 的分布式 2PC。采用**同事务领域事实 + Outbox、稳定幂等键、Provider Binding 与对账**。
- **引擎至控制层：** 以 Provider 的真实技术状态 + 平台 Receipt/Evidence 判断业务完成；`Inbox/Domain Event` 去重、单调修订与幂等投影应对重复/乱序/丢失事件。
- **安全性优先于可用性**：不能证明「Workflow 是否已创建」「Tool 是否已生效」时，进入 `UNCERTAIN/UNKNOWN` 安全状态并查询/人工介入，而不是直接再执行一次。
- **不承诺**跨独立系统 Exactly Once Delivery/Execution、原生 Token 恢复到中断的某个字符、外部副作用事务一致性或无限重放。
- **业务终态不可重开**：业务 Run Terminal 写入须满足版本、审批、Receipt 和 Verification；Provider 独立 Task Finished 只能触发重新核对，不能绕过平台 Terminal CAS。

## 2. 最小持久化实体（逻辑字段，不是最终 SQL）

| 数据 | 平台必须记录的最小关键字段及唯一性 |
|---|---|
| `Run/Step/Attempt/Execution` | 平台 ID、冻结版本、状态投影/事实版本、EvidenceRef、SideEffectClass |
| `ProviderBinding` | Platform run/segment ID + provider workflow ID、adapter/definition version、binding_revision；同 Provider ID 不跨 Run 重绑 |
| `WorkflowOutbox` | `command_id`, `run_id`, `segment_id`, `kind`, `payload_ref/digest`, `dedup_key`, `delivery_state`, `attempt_count`, `next_retry_at` |
| `ProviderObservationInbox` | `provider_event_id?`, `provider_task_ref`, `source_sequence?`, `fingerprint`, `observed_at`, `projection_revision`; 去重键稳定 |
| `DomainEvent` | 平台 `event_id`, `run_id`, `run_sequence`（单 Run 单调）、`event_type`, `fact_revision`, `payload_ref`, `timestamp` |
| `SideEffectIntent/Receipt` | `execution_id`, `operation`, `target`, `idempotency_key`, `class`, `preconditions`, `dispatch_mark`, `external_reference`, `observed_result`, `reconciliation_state` |
| `Approval/RecoveryPoint` | requester/principal/resource/action/policy context、decision、opaque checkpoint/runtime/workspace refs、恢复所需 PIN 引用 |

**隔离存储**：Harness Schema 拥有以上业务事实；Hatchet Schema 独立拥有其 Workflow/Queue/Retry History；OSS 保存大 Payload。可以共用 PostgreSQL 实例，不能共用业务 Table Ownership/迁移脚本。

## 3. Outbox → Hatchet 创建的不可确定窗口

```mermaid
sequenceDiagram
    participant API as Harness API
    participant PG as Harness PG (Run + Outbox)
    participant OUT as Outbox Dispatcher
    participant H as Hatchet Engine
    participant R as Reconciler
    API->>PG: 单事务 Run/Segment + CREATE_WORKFLOW Outbox
    OUT->>PG: Claim command (CAS)
    OUT->>H: ensure workflow (dedup_key)
    alt Provider ACK + workflow id
      H-->>OUT: workflow_run_id
      OUT->>PG: Upsert Binding; mark OBSERVED
    else 调用或 ACK 超时，不知是否创建
      OUT->>PG: DELIVERED_UNCERTAIN (not FAILED)
      R->>H: 按幂等键/元数据/公开查询核对
      alt 已找到唯一 Workflow
        H-->>R: workflow_run_id
        R->>PG: 幂等补录 Binding
      else 无法确定唯一性
        R->>PG: BLOCKED_UNKNOWN
        Note over R,H: 不盲目创建第二个 Workflow
      end
    end
```

- `dedup_key` = Platform `run_id:segment_ordinal:command_kind:command_revision` 稳定编码（可哈希）；不得以 Worker ID/随机 UUID 重试创建。
- 触发前写 Outbox；触发后平台事务提交失败，**不得依赖内存中的 Provider ID 继续执行**；须先通过 Provider 可查询的去重键/元数据证明确切状态，再写入 Binding。
- Hatchet 的原生 Idempotency 配置、Query/Metadata/ChildKey 具体行为、SDK 1.42.1 与 Engine v0.110.5 兼容性**需真实 POC**；若不能在该版本可靠查询已有 Run，`BLOCKED_UNKNOWN` + 告警/人工或升级 Provider 能力，不自行构建完整 Queue。
- 分布式 Outbox Dispatcher 可多实例，但领取/完成要数据库 CAS；重复发送不会产生多个可执行业务 Segment 才算通过门禁。ACK≠业务完成。

## 4. Hatchet Event → 平台状态投影

1. Worker/Adapter 的真实 `TaskResult/TaskFailure`、Hatchet 查询的 Provider State、Agent Typed Events 到平台各自受约束的 Input Port；统一校验 `ProviderBinding/run_id/segment_id/definition_version`，未知 Provider ID Fail Closed。
2. `Inbox` 按 `provider_event_id`（若有）或稳定指纹/版本去重；同 Run 的 `DomainEvent.run_sequence` 仅由平台赋予，`Last-Event-ID` 从持久事件游标重放。**Hatchet History 不等于可直接广播的 Token SSE**。
3. Provider Task SUCCEEDED → 核对 Receipt/Artifact/Verifier → 可形成业务 `Step.Completed`；验证失败 → `Verification.Failed`，后继不放行。Provider Task FAILED → 分类 Failure/UNKNOWN → 受控恢复；不能因 Provider Completed 直接写 Run COMPLETED。
4. 投影只沿有效 `binding_revision` 与已冻结的 `plan_version` 更新，使用状态/事实 CAS 拒绝 stale Worker 与乱序事件；业务 Terminal Run 不重新打开。
5. 崩溃恢复时优先**主动对账 Provider 状态** + 已存领域事实；如果没有持续 Provider 事件推送的可靠保障，使用低频**核对作业只读取/修复投影**，不承担任务领取/重调度职责。

## 5. SideEffectReceipt：业务外部写入的不确定 ACK 窗口

- **先记录 Intent**：非 PURE Tool 执行前记录 `execution_id/op/target/side_effect_class/idempotency_key/precondition` 和当前有效 owner/fencing；必须通过授权 Gate 后才将 Intent 标为已 dispatch。
- **真实调用发生**：携带外部系统允许的幂等键/预条件（若可用）。Provider 接受/返回 external_reference 或结果则保存 Receipt/Evidence；崩溃后无 ACK 不得推断「未发生」。
- **ACK 丢失**：平台对 `execution_id` 标记 `UNKNOWN`（在有关状态投影显示待对账），阻断该 Execution/Step 的无依据重试及所有依赖它的副作用后继。
- **对账**：优先查询外部系统的事务/工单 ID、Git 远端 Ref/Commit、对象 Storage Digest 等；允许结论 `CONFIRMED_SUCCESS / CONFIRMED_NOT_EXECUTED / CONFIRMED_FAILURE / STILL_UNKNOWN`，保留证据与决议 Principal/Time。
- **继续**：已确认成功 → 复用 Receipt 产生原 Attempt 的 Outcome、不重复发送；确未执行 → 可产生 New Attempt 并用冻结参数/新 Fencing 再试；仍 UNKNOWN → 待人工/Fail Safe，不能以 Hatchet Retry 直接重放。
- 需要限制：未经外部服务配合，`Intent before call` 本身无法证明操作已经成功；`Fencing` 也不能撤销已发出的外部请求。本合同**不声称任意副作用 Exactly Once**。

## 6. 并发/取消/终态竞态

| 场景 | 决策 |
|---|---|
| Workflow 已完成、平台投影 RUNNING | 查询真实 Provider Outcome + 业务 Evidence/Receipt，CAS 幂等补录、补发业务 Event |
| 平台业务 Step 已 COMPLETED、延迟 Provider retry event 到达 | 不修改历史业务终态；核对后记录诊断/异常重复执行告警 |
| Cancel 请求与 Task SUCCEEDED 同时发生 | 持久 `CancelRequested`；传播到 Engine/Runtime/Cube；以已认证 Outcome/Receipt/实际终止证据 CAS 裁决，不把 ACK 等于 CANCELLED |
| Worker A 重启在 Worker B 领取后上传结果 | HC-03 拒绝旧 Lease/Fencing；只允许 Reconciliation 使用旧 Trace/不可逆 Receipt 的读取证据，不能接收其状态提交 |
| Approval 决议重复/乱序送达 | 同 `approval_request_id` 与 Principal+Decision 去重；Pending 状态和合法 Principal/Policy 检查后只唤醒一次原 Run |
| Engine 不可访问但 Harness 可用 | 查询可返回 Provider Unavailable；只维护业务事实和等待/错误标识，不自行用第二引擎派发任务 |
| OSS Artifact 先落盘但业务事实未落库 | 依 StorageRef/Digest 做幂等绑定/孤儿清理；Recoverable Run 引用在取消/恢复期间 PIN，不因无当前 UI Session 自动 GC |

## 7. 对外最小接口草图（平台 Port，非原生 SDK 签名）

```python
class WorkflowOutboxPort:
    async def enqueue_once(self, run_id, segment_id, command, key): ...
    async def reconcile_provider_binding(self, command_id): ...

class ProviderStatePort:
    async def get_state(self, provider_workflow_run_id): ...
    async def find_existing(self, dedup_key): ...  # must be confirmed on target Hatchet version

class DomainProjectionPort:
    async def apply_observation(self, binding, observation, expected_revision): ...
    async def append_event(self, run_id, typed_event): ...

class SideEffectReconciliationPort:
    async def register_intent(self, execution, operation, policy): ...
    async def record_receipt(self, execution_id, receipt, fencing): ...
    async def reconcile(self, execution_id): ...
```

所有外部写入应有显式结果 `APPLIED / ALREADY_APPLIED / UNKNOWN / REJECTED_STALE / UNSUPPORTED`，不能把超时当 `FAILED_NOT_EXECUTED`。

## 8. 故障注入与验收（全部为待验证门禁）

- C01 Run+Outbox 事务提交前崩溃：没有孤立可执行 Workflow；提交后 Worker 不在线，恢复可自动补投。
- C02 Provider 已创建 Workflow 但 ACK 丢失，Dispatcher 再发：**一个业务 Segment 最多一个有效 Provider Workflow**；无法确证时 BLOCKED_UNKNOWN。
- C03 Provider Task 完成但 Harness 事务失败：重复 Provider 事件和主动查询仅写一次业务 Step Completed / Event sequence。
- C04 并发两 Reconciler、两个 Outbox Dispatcher：同键最多一个有效绑定，CAS/唯一约束一致；无双写 Tool。
- C05 非幂等模拟外部账本已经改变、SDK ACK 丢失，A 崩溃 B 接管：外部动作恰一次记录、平台 UNKNOWN 阻断直至 Receipt 对账（真实引擎+可控外部服务）。
- C06 取消/完成/审批消息乱序：终态不可重开，业务 Event 顺序可重放，旧 Owner 不可更改 Receipt。
- C07 停机后 Last-Event-ID/SSE 恢复：只恢复**已持久化平台 Event**，不伪造 Token；OS/OSS 引用仍可回放。

**结论：一致性策略 DECIDED；Outbox/Inbox/Provider 查询兼容、真实丢 ACK/非幂等回执、跨 Worker 一体化属于 P0 实施验收。**
