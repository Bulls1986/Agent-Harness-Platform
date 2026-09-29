# Harness Kernel 与可插拔组件抽象

> 状态：讨论参考

## 1. 核心目标

平台不直接抽象成“很多 Agent”，而是：

~~~text
Harness Kernel
  +
Pluggable Components
  +
Recipe/Profile
~~~

核心定义：

> **Harness = 状态 + 生命周期 + 控制**  
> **Component = 可替换能力**

## 2. Harness Kernel

Kernel 应尽量不依赖模型厂商或某个 Agent Framework。

负责：

- Task lifecycle
- Run state
- State transition
- Scheduler
- Retry
- Timeout
- Cancellation
- Recovery
- Checkpoint
- Budget
- Event
- Approval
- Component invocation

Kernel 本身不负责“思考”。

## 3. Capability Component

组件接口应以能力命名，而不是强制命名为 Agent：

- Planner
- Executor
- Verifier
- Replanner
- ContextProvider
- SandboxProvider
- ModelProvider
- ArtifactStore
- StateStore
- PolicyEngine

### 为什么 Component ≠ Agent

例如 Verifier 可以是：

~~~text
Verifier
├─ UnitTestVerifier
├─ E2EVerifier
├─ LintVerifier
├─ ArchitectureVerifier
├─ SecurityVerifier
├─ AcceptanceCriteriaVerifier
└─ LLMReviewVerifier
~~~

很多验证逻辑根本不需要 LLM。

## 4. Plan 作为一等对象

Plan 不能只是一串自然语言 TODO。

建议至少包含：

~~~text
Plan
├─ id
├─ version
├─ goal
└─ steps[]
    ├─ id
    ├─ objective
    ├─ dependsOn[]
    ├─ status
    ├─ acceptanceCriteria[]
    └─ executionPolicy
~~~

复杂场景可支持 DAG。

## 5. Acceptance Criteria

验收标准应成为平台对象，而不是只存在 Prompt。

可能类型：

- CommandCriterion
- TestCriterion
- FileCriterion
- MetricCriterion
- RuleCriterion
- HumanCriterion
- SemanticCriterion

## 6. Failure / Replan

Replan 不能等同于“再问一次模型”。

~~~text
Failure
  ↓
FailureClassifier
  ↓
ReplanPolicy
~~~

可能决策：

- RETRY
- REPLAN_STEP
- REPLAN_SUBTREE
- REPLAN_ALL
- WAIT_HUMAN
- ABORT

典型失败类型：

- MODEL_ERROR
- RATE_LIMIT
- COMMAND_FAILED
- TIMEOUT
- TEST_FAILED
- BUILD_FAILED
- ARCHITECTURE_FAILED
- POLICY_DENIED
- ENVIRONMENT_FAILED
- REQUIREMENT_AMBIGUOUS

## 7. Recipe / Profile

Recipe 用于组合组件，而不是再造一个 Agent 概念。

~~~yaml
recipe: software-development

planner:
  type: maf

executor:
  type: codex

sandbox:
  type: docker

verifiers:
  - unit-test
  - lint
  - architecture
  - acceptance

stateStore:
  type: postgres
~~~

不同业务场景通过不同 Recipe 组合：

- software-development
- document-processing
- data-analysis
- operations
- incident-response

## 8. 组件版本冻结

一次 Run 必须记录：

- recipe_version
- component_versions
- prompt_versions
- policy_version
- tool_versions
- model/provider
- protocol_version

否则无法可靠 Replay 与审计。
