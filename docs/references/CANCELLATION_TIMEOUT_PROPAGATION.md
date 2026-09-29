# Cancellation / Timeout Propagation 契约

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-016

## 1. 核心定位

本契约定义 Harness 内 Run / Step / Attempt / Execution 的取消（Cancellation）与超时（Timeout）传播语义。

核心原则：

> Cancel 控制“不要继续做新的事情”，但不能抹掉已经发生或可能已经发生的事情。

Cancel 与 Timeout 都属于执行控制，但二者语义不同：

- Cancel：显式撤销继续执行的意图；
- Timeout：Execution Limit / deadline 到期产生的失败原因。

## 2. Cancel Request 不等于 CANCELLED

收到 Cancel Request 后，活动执行先进入取消中（CANCELLING）控制状态：

~~~text
RUNNING
→ CANCELLING
→ propagate cancellation
→ confirm termination / reconcile
→ CANCELLED | UNKNOWN | FAILED
~~~

CANCELLED 只能表示平台已经能够确认该执行不再继续，且没有尚未处理的未知副作用。

仅收到下游 ACK 不等于执行已经终止。

## 3. 传播范围

取消只沿 Harness 已知的 ownership / invocation chain 传播：

~~~text
Run Cancel
→ current Step / Attempt
→ active Execution
→ Runtime / Tool / MCP / Sandbox Adapter
→ provider public cancel / abort / terminate capability
~~~

规则：

- 已 terminal 的节点不重新打开；
- 未开始 / 尚未 dispatch 的 pending work 不再发起；
- 正在执行的节点进入 cancellation flow；
- 不为了 cancellation 建设通用 distributed process manager。

## 4. Graceful 与 Force Termination

默认优先 cooperative / graceful cancellation。

超过 grace period 后，如果 Adapter / Provider 明确支持，可以升级为 force termination。

Adapter 至少应表达真实能力，例如：

~~~text
graceful_cancel = supported | unsupported
force_terminate = supported | unsupported
~~~

具体 Runtime / Sandbox 内部如何 kill、abort 或回收资源由 Provider 负责；Harness 不复制其内部实现。

grace period 的具体数值属于部署/Recipe/Provider 配置，不在架构中写死。

## 5. Cancellation Acknowledgement

Adapter 的取消结果至少区分：

~~~text
ACKNOWLEDGED
TERMINATED
UNSUPPORTED
UNKNOWN
~~~

语义：

- ACKNOWLEDGED：已收到取消信号，但不能证明执行已停止；
- TERMINATED：Provider 可确认执行已停止；
- UNSUPPORTED：Provider 不支持该层 cancellation；
- UNKNOWN：无法判断是否已停止或是否已经产生副作用。

Harness 最终状态由 Control Plane 根据真实 termination result 决定。

## 6. Timeout 语义

Timeout 不定义新的 terminal state，而是 Failure Type / termination cause。

若执行未 dispatch，或能够确认安全停止且结果未发生：

~~~text
status = FAILED
failure_type = TIMEOUT
~~~

若请求已经 dispatch，且副作用结果无法确认：

~~~text
status = UNKNOWN
failure_type = TIMEOUT_AFTER_DISPATCH
→ Reconciliation
~~~

不得把 TIMEOUT_AFTER_DISPATCH 简化为 CANCELLED 或普通 FAILED。

## 7. Side Effect Safety

Cancellation / Timeout 不能证明已经发出的外部副作用未发生。

对于非 PURE Execution：

- 若可以确认尚未产生副作用，可以安全终止；
- 若副作用已明确成功，保留成功事实并停止后续工作；
- 若副作用结果未知，进入 UNKNOWN → Reconciliation；
- 不允许因为用户点击 Cancel 或 timeout 到期就 blind retry。

Fencing 只阻止 stale owner 继续发起新的平台受控操作，不能撤销已经发出的外部副作用。

## 8. Run Terminalization

Run 收到取消请求后可以进入 CANCELLING，但不能立即进入终态 CANCELLED。

Run 进入 CANCELLED 前至少需要：

- 不再 dispatch 新 Step / Attempt / Execution；
- 所有已知 active Execution 已终止、已完成，或已经进入 UNKNOWN/Reconciliation；
- 不存在尚未处理的高风险 unknown side effect。

如果 Reconciliation 确认某个副作用已经成功，应保留该 Execution 的真实成功结果；取消请求仍可以使剩余 Run 最终以 CANCELLED 收口。

如果高风险 UNKNOWN 无法确认，则 Run 按既有契约进入 WAITING_HUMAN / FAIL_SAFE，而不是伪装成 CANCELLED。

## 9. Waiting State

WAITING_INPUT / WAITING_APPROVAL 在尚未产生新的 active side effect 时，可以直接撤销等待并终止原 Run。

取消等待：

- 不创建新 Run；
- 不恢复原 pending action；
- 保留已有 Approval Request / Input Request 历史事实。

## 10. Cleanup 边界

Cancellation 不是 rollback。

取消后：

- Workspace 已发生的修改不自动删除；
- Artifact / Evidence 不自动删除；
- 已提交的 SideEffectReceipt 不删除；
- 已形成的 task/event history 不删除；
- 临时 Sandbox / Process / Runtime resource 可以按 Provider 能力释放。

需要补偿的副作用继续走 Side Effect Contract，不由 Cancellation 自动推导补偿动作。

## 11. Runtime / Framework Mapping

Runtime / Framework 若提供公开 cancellation / abort / terminate API，Adapter 应优先使用。

如果 Runtime 只支持 cooperative / best-effort cancellation：

- 平台必须如实标记 capability；
- ACK 不得提升为 TERMINATED；
- 已经 dispatch 的同步 Tool / external action 仍可能完成，因此必须继续服从 SideEffect / UNKNOWN / Reconciliation。

如果能力不存在，显式 unsupported，不 fork / monkey patch /复制内部实现。

## 12. Runtime Topology

Runtime Topology 可以帮助定位仍活跃的 Participant，但不拥有 cancellation 状态机。

Topology 只提供：

- participant identity；
- owner / relation；
- active/stopped status；

Cancellation state 与最终业务状态仍归 Control Plane / Domain Model。

## 13. 不在本契约范围

- Kubernetes / OS 通用进程管理产品；
- Runtime 内部 worker cancellation protocol 的重新实现；
- Sandbox Provider 内部节点 kill / scheduling 算法；
- 外部系统 transaction rollback engine；
- 通用 compensation workflow engine。

## 14. Accepted Rules

1. Cancel Request ≠ CANCELLED；活动执行先进入 CANCELLING。
2. Cancel 与 Timeout 分离；Timeout 是 failure cause，不是 CANCELLED 的别名。
3. Cancellation 只沿 Harness 已知执行链传播，未开始工作停止 dispatch。
4. 优先 graceful cancellation；Provider 支持时可在 grace period 后 force terminate。
5. ACKNOWLEDGED 仅表示收到取消信号，只有 TERMINATED 才能证明下游已停止。
6. 对已经 dispatch 的非 PURE Execution，Cancel/Timeout 后结果不确定必须 UNKNOWN → Reconciliation。
7. Cancellation 不做隐式 rollback，不删除 Workspace/Artifact/Evidence/SideEffect 历史。
8. WAITING_INPUT / WAITING_APPROVAL 可直接取消原 Run。
9. Provider 不支持 cancellation 时显式降级，不 fork / patch Framework。
10. Run 只有在已知活动执行安全收口后才能进入 terminal CANCELLED。