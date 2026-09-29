# Execution Lease / Fencing / Heartbeat 契约

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-008

## 1. 核心定位

本契约只解决平台自有执行平面中的一个问题：

> 当 Execution 被 Worker / Executor 接管、失联、迁移或重新分配时，平台如何保证只有当前有效 Owner 可以继续代表该 Execution 写入状态和发起新的受控执行。

本契约不建设新的分布式调度系统，也不接管 Framework / Durable Engine / Sandbox Infrastructure 内部的 Worker ownership。

## 2. 适用边界

平台负责：

~~~text
Harness Kernel
→ ExecutionScheduler
→ Executor / Worker
→ Execution
~~~

平台不负责重新实现：

~~~text
MAF / Durable Task 内部 Worker ownership
Temporal Worker ownership
CubeSandbox CubeMaster / Cubelet ownership
Provider 自身的分布式协调
~~~

这些底层组件若已有公开且可靠的 ownership / recovery 机制，由其自身负责。

## 3. 粒度

Lease / Fencing 的最小治理粒度是执行动作（Execution），不是 Run、Step 或 Attempt。

建议作为 Execution 的执行基础设施元数据：

~~~text
ExecutionOwnership
├─ execution_id
├─ owner_id
├─ fencing_token
├─ lease_expires_at
└─ last_heartbeat_at
~~~

这组字段用于执行资格控制，不创建新的业务状态机。

## 4. Lease

租约（Lease）表示：

> 某个 Owner 在有限时间内拥有该 Execution 的当前执行资格。

Lease 到期意味着：

- 当前 Owner 不再被平台视为有效 Owner；
- Execution 可以进入重新分配判断；
- 但不意味着该 Execution 可以被安全盲重试。

Lease TTL、heartbeat interval、grace period 等具体数值不在架构中冻结，由 POC 和生产 SLO 调优。

## 5. Heartbeat

心跳（Heartbeat）的唯一职责是：

> 证明当前 Owner 仍然活跃，并在满足条件时续租当前 Lease。

Heartbeat 不承担：

- Observability Metrics；
- Runtime Topology；
- Participant Health Model；
- Durable Workflow scheduling；
- 业务状态判断。

## 6. Fencing Token

栅栏令牌（Fencing Token）表示 Execution ownership 的代际。

每次合法 ownership transfer 时：

~~~text
fencing_token = previous_token + 1
~~~

例如：

~~~text
Worker A
token = 12

A 失联 / Lease 失效

Worker B 接管
token = 13
~~~

A 后续携带 token=12 的状态更新、结果提交或新的平台控制执行请求必须被拒绝：

~~~text
STALE_EXECUTION_OWNER
~~~

旧 token 一旦失效，不得重新恢复有效。

## 7. 当前 Owner 权限

只有当前有效 Owner 才可以：

- 续 Lease；
- 更新 Execution 运行状态；
- 提交 ExecutionResult；
- 提交与该 Execution 绑定的 Evidence / Receipt；
- 请求新的平台控制副作用执行。

旧 Owner / stale token 不得通过延迟消息、网络恢复或 Worker resurrection 再次取得这些权限。

## 8. Lease 失效与副作用边界

Lease 失效不能替代失败、幂等和副作用契约。

### 8.1 明确尚未执行

若可以证明 Execution 尚未真正 dispatch 或尚未产生副作用：

~~~text
Lease lost
→ FAILED / TRANSIENT_INFRA
→ Retry Policy
→ New Attempt / Execution
~~~

### 8.2 结果不确定

若旧 Owner 可能已经发出外部副作用：

~~~text
Lease lost
→ UNKNOWN
→ Reconciliation
~~~

禁止：

~~~text
Lease expired
→ acquire new lease
→ blind replay external side effect
~~~

Fencing 只阻止旧 Owner 继续产生新的受控操作，不能撤销或判断已经发出去的外部副作用。

## 9. 与 Reconciliation 的关系

~~~text
Lease
→ 谁当前拥有执行资格

Heartbeat
→ 当前 Owner 是否仍活跃

Fencing
→ 旧 Owner 是否已经失效

Reconciliation
→ 已经发出去但结果未知的副作用到底发生没有
~~~

四者不得混为一套机制。

## 10. V1 实现原则

V1 不新增独立的：

- Distributed Lock Service
- ZooKeeper
- etcd Lease Coordinator
- Redis Lock Framework
- Leader Election Service

优先使用 ExecutionScheduler 已有的权威持久化层，通过原子更新 / Compare-And-Swap 实现：

- claim
- renew
- ownership transfer
- fencing token increment
- stale update rejection

具体存储实现可以替换，但语义必须一致。

## 11. 失败与恢复关系

本契约服从 FAILURE_IDEMPOTENCY_AND_RECOVERY：

- Worker crash 不自动等于安全 Retry；
- UNKNOWN 禁止 blind retry；
- 非 PURE Execution 必须遵守 Side Effect Contract；
- fencing_token 不能替代 idempotency_key；
- Fencing 不能提供任意外部副作用的 Exactly Once Execution。

## 12. 不在本契约范围

ARCH-TODO-008 不负责：

- Framework / Durable Engine 内部 Worker scheduling；
- Durable Task Scheduler；
- Workflow replay engine；
- Sandbox infrastructure scheduling；
- Global service discovery；
- Leader election；
- Runtime Topology；
- Observability；
- Cancellation / Timeout 传播协议（由 CANCELLATION_TIMEOUT_PROPAGATION.md 定义）；
- 外部副作用的具体 Reconciliation 实现。

Cancellation / Timeout 传播已由 CANCELLATION_TIMEOUT_PROPAGATION.md 冻结。取消可以使当前 Owner 停止继续执行，但不能替代 Fencing 对 stale owner 的拒绝，也不能证明已发出的副作用未发生。

## 13. Accepted Rules

最终冻结：

1. Lease / Fencing 的粒度是 Execution。
2. Lease 表示当前执行资格，Heartbeat 只负责活性与续租。
3. Fencing Token 随 ownership epoch 单调递增，旧 token 永久失效。
4. 只有当前 Owner 可以更新 Execution、提交结果和申请新的平台控制副作用。
5. RUNNING Execution 丢失 Lease 后不得 blind handoff；明确未执行才可按失败策略重试，结果不确定必须进入 UNKNOWN → Reconciliation。
6. Framework / Durable Engine / Sandbox Infrastructure 内部 ownership 由其自身负责，平台不重复实现。
7. V1 优先使用现有权威状态存储做原子 claim / renew / fencing，不新增独立分布式锁基础设施。
