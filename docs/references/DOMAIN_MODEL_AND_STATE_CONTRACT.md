# Domain Model & State Contract

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-001

## 1. 决策摘要

平台 V1 核心领域关系冻结为：

~~~text
Conversation
  │
  └─ Turn [1..N]
       │
       └─ Run [1..N]
            │
            ├─ Plan [v1..N]
            │    └─ Step [1..N]
            │         └─ Attempt [1..N]
            │
            ├─ RecoveryPoint [0..N]
            ├─ Artifact / Evidence
            └─ Terminal Result
~~~

核心原则：

- Conversation 是长期用户会话容器。
- Turn 表示一次新的用户意图输入。
- Run 表示对某个 Turn 的一次完整执行实例。
- Step 表示“要完成什么”。
- Attempt 表示“第几次实际尝试完成该 Step”。
- Plan 独立版本化；Replan 产生新版本，不覆盖历史 Plan。
- 一个 Turn 可以对应多个 Run，例如 Regenerate、Rerun、A/B 执行。
- 一个 Run 一旦进入终态，不允许 reopen。
- Workspace、Sandbox、Runtime Session 均不等同于 Run。

## 2. Conversation

Conversation 表示用户与平台的长期会话边界。

职责：

- 聚合多个 Turn。
- 关联长期 UI 会话。
- 关联 Runtime Session Binding。
- 可引用长期上下文，但不直接拥有单次执行状态。

Conversation 不等同于具体 Agent Framework 的 Session ID。

~~~text
Platform Conversation
      ↓
RuntimeSessionBinding
      ├─ runtime_type
      ├─ runtime_session_id
      └─ provider_metadata
~~~

Provider/Runtime 原生 ID 只作为 binding / metadata，不作为平台领域主键。

## 3. Turn

Turn 表示一次新的用户意图。

典型情况：

~~~text
用户："修复这个 bug"
→ Turn T1

用户："顺便把结构优化一下"
→ Turn T2
~~~

即使 T2 延续了 T1 的 Workspace，也仍然是新的 Turn。

Turn 可以拥有多个 Run：

~~~text
Turn T1
├─ Run R1
└─ Run R2   ← regenerate / rerun / alternate execution
~~~

因此：

> Turn : Run = 1 : N

## 4. Run

Run 是平台最核心的执行边界。

至少承载：

- run_id
- turn_id
- lifecycle state
- budget
- policy context
- trace correlation
- recipe/version binding
- environment binding
- plan versions
- step/attempt execution
- recovery points
- artifact/evidence lineage
- terminal result

Run 可以暂停和恢复，但只有非终态 Run 可以 Resume。

### 4.1 终态不可重新打开

终态至少包括：

- COMPLETED
- FAILED
- ABORTED
- CANCELLED

一旦 Run 进入终态：

> **Run immutable as a completed execution history; never reopen.**

后续用户请求必须进入新 Turn / Run，或者在同一 Turn 下创建新的 Run。

## 4.2 Identity Binding

Run 必须保留发起者（Initiator）身份作为不可变审计事实，可通过 security_context / principal binding 引用。

V1 不要求 tenant_id：

~~~text
Run
├─ initiator_principal_id
├─ security_context_ref?
└─ policy_context
~~~

具体 Execution 的 Executor / Service Principal 单独记录，不覆盖 Run 的 Initiator。

身份历史事实可以冻结，但敏感动作的 Authorization 必须在 Execution 时按当前有效权限重新评估。

详见 IDENTITY_AND_AUTHORIZATION_PROPAGATION.md。

## 5. 新 Turn / 新 Run / 新 Attempt 判定

| 场景 | 领域动作 |
|---|---|
| 用户发送新的正常消息 | New Turn + New Run |
| 用户在已完成任务后说“继续改” | New Turn + New Run |
| 用户说“这个方案不行，换一种” | New Turn + New Run |
| UI Regenerate / Rerun | Same Turn + New Run |
| 使用另一个模型/Recipe 对同一输入重跑 | Same Turn + New Run |
| Model timeout / transient infrastructure error | Same Run + New Attempt |
| Sandbox transient failure | Same Run + New Attempt |
| Verification fail 后自动修复 | Same Run + Replan / New Attempt |
| 自动 Replan | Same Run + New Plan Version |
| WAITING_APPROVAL 后用户批准 | Resume Same Run |
| WAITING_INPUT 后用户补充缺失信息 | Resume Same Run |
| Run 已进入终态 | Never reopen |

## 6. Plan Version

Plan 是 Run 下的独立版本化实体。

~~~text
Run R1
├─ Plan v1
├─ Plan v2
└─ Plan v3
~~~

Replan 不覆盖旧 Plan。

需要保留：

- plan_id
- version
- parent_plan_id / supersedes
- created_at
- reason
- steps
- status

这样平台能够回答：

- 最初计划是什么。
- 为什么发生 Replan。
- 哪个 Plan 最终生效。
- 某个 Step 属于哪个 Plan Version。

## 7. Step 与 Attempt

必须严格区分：

> **Step = Intent / Work Unit**  
> **Attempt = Concrete Execution Try**

示例：

~~~text
Step-03: 修复表格光标
├─ Attempt-1 → verification failed
├─ Attempt-2 → sandbox crashed
└─ Attempt-3 → succeeded
~~~

Attempt 是成本、Evidence、ExecutionResult、Failure 与 Retry 的直接归属单位。

不能通过覆盖 Step 状态来丢失失败尝试历史。

## 8. Workspace / Sandbox / Runtime Session 与 Run 的关系

明确：

~~~text
Run ≠ Workspace
Run ≠ Sandbox
Run ≠ Runtime Session

Conversation ≠ Workspace
Session ≠ Workspace
Sandbox ≠ Workspace
~~~

允许：

~~~text
Run R1 ─┐
        ├─ Workspace W1
Run R2 ─┘
~~~

也允许：

~~~text
Workspace W1
   ↓
Sandbox S1
   ↓ destroy / pause

Workspace W1
   ↓
Sandbox S2
   ↓ continue
~~~

Workspace 的详细模型由 ARCH-TODO-003 单独讨论。

## 9. Platform ID 与 Provider ID

平台拥有核心领域 ID：

- conversation_id
- turn_id
- run_id
- plan_id
- step_id
- attempt_id
- artifact_id
- event_id
- recovery_point_id

Framework / Provider ID 仅作为绑定信息：

~~~yaml
runtime_binding:
  runtime_type: maf
  native_session_id: "..."
  native_response_id: "..."

sandbox_binding:
  provider: cubesandbox
  native_sandbox_id: "..."
~~~

不得让 MAF、CubeSandbox、模型 Provider 或其他厂商 ID 反向成为平台主键。

## 10. Runtime 映射原则

平台领域模型不复制 MAF/ADK/Temporal 的内部对象。

例如 MAF 可映射为：

~~~text
Platform Conversation
        ↓
MAF AgentSession

Platform Turn / Run
        ↓
MAF invocation / workflow execution

Platform RecoveryPoint
        ↓
MAF checkpoint + platform-owned state
~~~

但平台 Conversation/Run/RecoveryPoint 的语义独立存在，Runtime 替换后不改变。

## 11. Current State 与 Event

平台保持：

~~~text
Current State Store
+
Append-only Event Log
~~~

Current State 用于高效查询当前 Run/Plan/Step/Attempt 状态。

Append-only Event 用于：

- UI streaming / replay
- audit
- diagnostics
- recovery assistance
- lineage

平台不要求 V1 采用纯 Event Sourcing。

事件仍必须带：

- event_id
- run_id
- sequence
- type
- schema_version
- actor
- timestamp
- payload

## 12. V1 不在本待办展开的内容

以下内容与本领域模型相关，但由后续待办单独冻结：

- Failure / UNKNOWN / retry semantics → ARCH-TODO-002
- Workspace/Git lifecycle → ARCH-TODO-003
- Runtime Participant / Topology → ARCH-TODO-004
- RecoveryPoint 的跨层一致性 → ARCH-TODO-005
- Registry/schema upgrade compatibility → ARCH-TODO-007
- Execution lease/fencing → ARCH-TODO-008

## 13. Accepted Rules

最终冻结规则：

~~~text
新的用户意图
→ New Turn + New Run

UI Regenerate / Rerun
→ Same Turn + New Run

Infrastructure Retry
→ Same Run + New Attempt

Semantic Verification Failure
→ Same Run + Replan / New Attempt

WAITING_INPUT / WAITING_APPROVAL
→ Resume Same Run

Terminal Run
→ Never Reopen
~~~

该模型作为后续 Failure、Workspace、Checkpoint、Topology 与 Persistence 设计的上游约束。
