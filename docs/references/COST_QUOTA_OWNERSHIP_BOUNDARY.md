# Cost / Quota Ownership Boundary

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-013

## 1. 核心决策

Cost、Quota、Billing、Chargeback、Showback 与资源额度管理不属于 Harness Platform 核心职责。

平台不建设成本核算或额度账户体系，也不维护供应商价格表。

## 2. 明确不属于 Harness 的能力

- provider / model price table；
- token / runtime / storage usage 换算金额；
- monetary cost accounting；
- invoice reconciliation；
- chargeback / showback；
- user / project / organization quota account；
- subscription / package / entitlement；
- credit / balance / budget deduction；
- financial attribution；
- sandbox / model / storage 资源额度产品。

这些能力如企业确有需求，应由 Portal、Enterprise Governance、FinOps、Billing、IAM/Entitlement 或其他上层系统负责。

## 3. Harness 可以暴露但不拥有的事实

Runtime / Provider 原生 telemetry 中如果已经存在以下数据，Harness 可以通过 Observability 保留：

- input/output token usage；
- runtime duration；
- execution duration；
- sandbox resource telemetry；
- provider/model/runtime identifiers。

这些数据只属于运行诊断 telemetry，不形成 Harness 的 Cost / Quota Domain，也不要求成为权威计费事实。

## 4. 外部治理系统的接入

若上层系统需要限制用户或项目资源使用，可以在进入 Harness 前完成 entitlement / quota decision，或通过既有 Policy / Admission boundary 给出允许/拒绝结果。

Harness 可以消费最终决策，但不维护：

- quota balance；
- cost ledger；
- billing account；
- entitlement lifecycle。

## 5. Execution Limits 与 Quota 必须区分

Harness 仍可以为了执行正确性和防止无限循环定义技术执行限制（Execution Limits），例如：

- max_iterations；
- max_replans；
- max_runtime / timeout；
- recursion / subagent depth limit。

这些是单次 Run / Recipe 的运行安全约束，不是用户额度、项目配额或财务 Budget。

禁止把 Execution Limits 扩展成 Cost / Quota Account。

## 6. 与 Observability 的关系

Observability 可以记录 token usage、duration 等 Runtime 原生 telemetry。

但：

> 可观测到 usage ≠ Harness 负责计算成本或扣减额度。

采样、丢失或指标聚合不能影响任何外部账务系统的正确性；若未来需要正式 Billing，必须由独立系统提供权威账务事实和新的集成契约。

## 7. 不在本契约范围

- 具体 Portal / Billing / FinOps 产品；
- 企业额度策略；
- 供应商账单 API；
- 价格更新机制；
- 财务报表；
- 跨组织结算。

## 8. Accepted Rules

1. Cost / Quota / Billing / Chargeback / Showback 明确不属于 Harness Platform 核心职责。
2. Harness 不维护价格表、余额、额度账户、账本或财务归属模型。
3. Runtime 原生 token / duration / resource usage 可以作为 Observability telemetry 保留，但不形成 Cost Domain。
4. 外部治理系统可以通过 Policy / Admission boundary 控制是否允许执行；Harness 只消费决策，不拥有 quota state。
5. max_iterations / max_replans / timeout 等属于 Execution Limits，只服务单次执行安全，不属于 Quota/Budget。
6. 若未来出现正式计费/额度产品需求，必须新立架构决策，不得从现有 Harness Domain 隐式扩张。