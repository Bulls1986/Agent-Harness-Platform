# 失败、幂等与副作用契约

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-002

## 1. 核心决策

平台必须将以下三个维度严格分离：

~~~text
执行结果（Execution Outcome）
        ↓
失败分类（Failure Classification）
        ↓
副作用语义（Side Effect Semantics）
        ↓
恢复决策（Recovery Decision）
~~~

禁止将“执行失败”直接等同于“可以重试”。

平台 V1 冻结以下五条硬原则：

1. **执行结果、失败原因、副作用类型三者分离。**
2. **未知执行结果（UNKNOWN）禁止盲目重试（Blind Retry）。**
3. **重试（Retry）只处理“同一意图再次尝试”；重规划（Replan）处理“方案本身需要改变”。**
4. **所有有副作用的能力必须声明副作用契约（Side Effect Contract）。**
5. **高风险副作用无法确认结果时，默认停止自动化并进入人工介入（Human Intervention）。**

## 2. 执行尝试状态（Attempt State）

执行尝试（Attempt）采用：

| 状态 | 中文含义 | 说明 |
|---|---|---|
| CREATED | 已创建 | Attempt 已建立，尚未进入队列 |
| QUEUED | 排队中 | 已进入调度队列 |
| RUNNING | 执行中 | 已由执行器接管 |
| SUCCEEDED | 执行成功 | 可确认目标执行成功 |
| FAILED | 执行失败 | 可确认执行未达到成功条件 |
| CANCELLED | 已取消 | 由用户/平台/策略取消 |
| UNKNOWN | 执行结果未知 | 无法确认副作用是否已经发生 |

其中 UNKNOWN 是正式的一等状态，不允许降级成普通 FAILED。

## 3. 超时（Timeout）的语义

超时描述的是失败原因，不是独立的顶层执行结果。

例如：

~~~text
status = FAILED
failure_type = TIMEOUT
~~~

如果请求已经发出，且无法确认副作用是否发生：

~~~text
status = UNKNOWN
failure_type = TIMEOUT_AFTER_DISPATCH
~~~

因此必须区分：

- **执行结果（Outcome）**：我们知道执行最终发生了什么。
- **失败分类（Failure Type）**：为什么没有正常完成或为什么结果不可确认。

## 3.1 Cancellation 与 Timeout 的关系

Cancel 与 Timeout 必须分离：

- Cancel 是停止继续执行的显式控制意图；
- Timeout 是 Execution Limit / deadline 到期后的 Failure Type / termination cause。

活动 Execution 收到 Cancel Request 后可进入 `CANCELLING`；只有确认停止后才能进入 `CANCELLED`。

如果 Cancel/Timeout 时请求已经 dispatch 且副作用结果无法确认：

~~~text
UNKNOWN
→ Reconciliation
~~~

不得因为已经发送 cancel 信号就把未知副作用降级为 CANCELLED。

详见 CANCELLATION_TIMEOUT_PROPAGATION.md。

## 4. 失败分类（Failure Classification）

V1 至少支持：

| FailureType | 中文 |
|---|---|
| TRANSIENT_INFRA | 临时基础设施故障 |
| PROVIDER_UNAVAILABLE | 服务提供方不可用 |
| RATE_LIMIT | 限流 |
| TIMEOUT | 超时 |
| TIMEOUT_AFTER_DISPATCH | 请求发出后的超时 |
| EXECUTOR_CRASH | 执行器崩溃 |
| SANDBOX_CRASH | 沙箱崩溃 |
| TOOL_ERROR | 工具错误 |
| SEMANTIC_FAILURE | 语义失败 |
| VERIFICATION_FAILURE | 验收失败 |
| POLICY_DENIED | 策略拒绝 |
| APPROVAL_REJECTED | 审批拒绝 |
| USER_CANCELLED | 用户取消 |
| UNKNOWN_OUTCOME | 执行结果未知 |

失败分类不能自行决定是否重试，必须继续结合副作用语义与恢复策略。

## 5. 副作用类型（Side Effect Class）

每个工具、能力或具体执行动作（Execution）必须声明副作用类型。

| SideEffectClass | 中文 | 典型行为 |
|---|---|---|
| PURE | 纯操作 / 无副作用 | read、grep、git diff |
| IDEMPOTENT | 幂等操作 | 重复执行结果等价，例如 mkdir -p |
| DEDUPLICATED | 可去重操作 | 外部系统支持 idempotency key |
| VERIFY_BEFORE_RETRY | 重试前必须核验 | git push、某些创建类 API |
| COMPENSATABLE | 可补偿操作 | 可通过补偿动作撤销/回收 |
| NON_RETRYABLE | 不可自动重试操作 | 高风险不可逆副作用 |

副作用类型由 Capability / Tool Contract 声明，Harness 不得仅根据命令文本猜测。

同一种协议动作可能具有不同语义。例如 HTTP POST：

- 支持幂等键并由服务端去重：DEDUPLICATED。
- 创建不可逆资源且无去重能力：VERIFY_BEFORE_RETRY 或 NON_RETRYABLE。

## 6. 重试（Retry）与重规划（Replan）

### 6.1 重试（Retry）

定义：

> 在目标与计划步骤（Step）意图不变的情况下，再次尝试完成同一个 Step。

典型原因：

- 临时网络故障
- Provider 503
- 限流
- Worker crash
- Sandbox transient failure

领域动作：

~~~text
Same Run
Same Step
New Attempt
~~~

### 6.2 重规划（Replan）

定义：

> 当前方案、策略或步骤无法满足验收标准，需要改变计划。

典型原因：

- 测试失败
- 架构门禁失败
- 实现方向错误
- 当前方案缺少必要能力
- Acceptance Criteria 无法由当前路径满足

领域动作：

~~~text
Same Run
New Plan Version
New/Updated Step
New Attempt
~~~

硬规则：

~~~text
基础设施失败（Infrastructure Failure）
→ 重试策略（Retry Policy）

语义失败（Semantic Failure）
→ 重规划策略（Replan Policy）
~~~

## 7. 状态核对（Reconciliation）

任何 UNKNOWN 都必须优先进入状态核对（Reconciliation），禁止直接重试。

~~~text
RUNNING
   ↓
UNKNOWN
   ↓
RECONCILING
   ├─ 确认成功 → SUCCEEDED
   ├─ 确认未执行 → 可进入 Retry
   ├─ 确认失败 → FAILED
   └─ 仍无法判断 → WAITING_HUMAN / FAIL_SAFE
~~~

例如 git push：

~~~text
执行 push
  ↓
网络断开
  ↓
UNKNOWN
  ↓
读取 remote ref
  ↓
remote ref == target commit
  ↓
SUCCEEDED
~~~

而不是重新执行 push。

## 8. 无法自动核对时的安全策略

当 UNKNOWN 无法自动确认：

- 低风险、可证明幂等或可安全去重：按 Tool Contract 继续处理。
- 高风险副作用：进入 WAITING_HUMAN。
- 无法人工安全确认且操作不可逆：FAIL_SAFE，停止自动执行。

硬规则：

> **宁可暂停，也不重复执行一个结果未知的高风险副作用。**

## 9. 不承诺“恰好一次执行”（Exactly Once Execution）

平台不对任意外部副作用承诺 Exactly Once Execution。

现实保证采用：

~~~text
至少一次投递（At-least-once Delivery）
+
幂等（Idempotency）
+
去重（Deduplication）
+
栅栏（Fencing）
+
状态核对（Reconciliation）
~~~

对于高风险操作，可采用：

~~~text
至多一次意图（At-most-once Intent）
+
重试前核验（Verify Before Retry）
~~~

平台真正承诺的是：

> 当发生重复、超时、Worker 崩溃、响应丢失时，系统能够识别不确定性，并依据副作用契约安全恢复。

## 10. Step / Attempt / Execution 三层

领域执行层级冻结为：

~~~text
计划步骤（Step）
   ↓
执行尝试（Attempt）
   ↓
执行动作（Execution）
~~~

示例：

~~~text
Step S1：修复代码

Attempt A1
├─ Execution E1：读取文件
├─ Execution E2：修改文件
├─ Execution E3：运行测试
└─ Execution E4：git push
~~~

副作用语义属于具体 Execution，而不是整个 Attempt。

核心标识：

- step_id
- attempt_id
- execution_id
- idempotency_key
- fencing_token（具体算法由 ARCH-TODO-008 冻结）

## 11. 副作用回执（Side Effect Receipt）

所有非 PURE 的 Execution 都应产生副作用回执。

建议最小字段：

~~~text
SideEffectReceipt
├─ execution_id
├─ operation
├─ target
├─ side_effect_class
├─ idempotency_key
├─ precondition
├─ started_at
├─ completed_at
├─ external_reference
├─ observed_result
├─ verification_method
└─ compensation_reference
~~~

例如：

~~~yaml
operation: git.push
target: origin/feature-a
side_effect_class: VERIFY_BEFORE_RETRY

precondition:
  remote_ref: abc123

desired_result:
  remote_ref: def456

verification_method:
  type: git-ls-remote

observed_result:
  remote_ref: def456
~~~

副作用回执是 Recovery、Audit、Reconciliation 与后续人工介入的重要事实依据。

## 12. 恢复决策矩阵

| 情况 | 默认动作 |
|---|---|
| 纯操作失败 | 可重试 |
| 幂等操作临时失败 | 可重试 |
| 支持幂等键且可服务端去重 | 可重试 |
| 副作用操作明确未执行 | 可重试 |
| 副作用操作结果未知 | 先状态核对 |
| 状态核对确认成功 | 标记成功 |
| 状态核对确认未执行 | 重试 |
| 状态核对确认失败 | 失败/按策略处理 |
| 状态核对仍无法判断 | 高风险 → 人工介入 |
| 验收失败 | 重规划 |
| Policy 拒绝 | 停止/等待授权 |
| 用户取消 | 取消 + 必要清理/状态核对 |

## 13. 与后续待办的边界

本契约只冻结语义，不提前规定全部分布式实现。

后续由以下待办继续细化：

- Workspace/Git 的具体副作用与核对方式 → ARCH-TODO-003
- RecoveryPoint 跨层一致性 → ARCH-TODO-005
- Execution Lease / Fencing / Heartbeat → ARCH-TODO-008
- Cancellation / Timeout 向各层传播 → CANCELLATION_TIMEOUT_PROPAGATION.md（已冻结）
- Tool / MCP 的准入与信任由外部 Governance 负责；具体调用的 SideEffect 声明仍由本契约约束，详见 MCP_TRUST_OWNERSHIP_BOUNDARY.md

## 14. Accepted Rules

最终冻结：

~~~text
Outcome ≠ Failure Type ≠ Side Effect Class

UNKNOWN
→ Never Blind Retry
→ Reconciliation First

Retry
→ Same Intent / Same Step / New Attempt

Replan
→ Plan Strategy Changes

Non-PURE Execution
→ Must Declare Side Effect Contract
→ Must Produce Side Effect Receipt

High-Risk Unknown Outcome
→ Human Intervention / Fail Safe
~~~
