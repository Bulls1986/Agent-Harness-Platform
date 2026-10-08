# POC-A / A34：快速验证 MAF Executor → Harness Execution Admission → Tool Adapter

> 2026-10-08。通过 MAF 1.20.0 的公开 `WorkflowBuilder` / `Executor` /
> `@handler`，不使用 DurableTask 内部 API，也不自研状态调度。
> **此测试专门覆盖危险副作用派发门禁；不是 Native MSSQL
> SIGKILL + PostgreSQL 在同一次故障内的联合验收。**

## 为什么无需重新执行 110 秒故障注入

[前两轮真实 Native MSSQL Worker SIGKILL 验证](functions-mssql/A34_RUNNING_EXECUTOR_CRASH.md)
已经证实：`Prepare=1`，中断中的 Executor handler 入口重入 **2 次**，
最终原生 Workflow Completed。对 SideEffect 语义的决策问题因此
收敛为：相同平台 Execution 再次进入，Harness Adapter 是否会
允许第二次工具调用？

## 实现边界

`maf_execution_adapter.py` 仅将 MAF 的公开 Executor handler
挂到平台已有的 `ExecutionOwnership.dispatch` 上：

1. 平台预先创建 RUNNING Run/Attempt/Execution，声明
   `NON_RETRYABLE` 或其他受控 SideEffect Class；
   `Ownership` 来自可信平台，不来自任意工具输入。
2. `dispatch(ownership)` 在 PostgreSQL 校验平台 Run/Attempt/
   Execution RUNNING、owner 和 fencing token、有效 lease，
   **在同一个事务只允许第一次写入 dispatched_at**。
3. 事务提交后才进入注入的 Tool Adapter 回调。
4. 再次进入同一 Execution 时被 `StaleExecutionOwner`
   拒绝，不能再调用 Tool Adapter；A29 RecoveryCoordinator
   对已 dispatch 的 NON_RETRYABLE 结果不明保持
   `UNKNOWN + PENDING Reconciliation`。
5. 这是**保守 at-most-one adapter dispatch admission**
   （数据库门禁），不是端到端 Exactly Once：
   admission 后而真正调用前崩溃，也会进入 UNKNOWN。
   实际外部 Tool 服务是否收到/应用动作须由外部回执核对。

## 快速测试

```sh
python -m unittest discover -s poc/maf/tests -p 'test_maf_guarded_dispatch.py' -v
```

本地真实 MAF 执行链 **2/2 PASS（约 0.2 秒）**：
相同 Execution 经两次独立 `MAF Workflow.run` 进入
Executor；首次模拟工具调用 1 次、第二次 0 次；
首次 Adapter 返回结果丢失的重入也没有第二次调用。

使用现有真实 PostgreSQL 的专项 3 个用例
`test_maf_guarded_dispatch_pg.py` 纳入 CI，验证：
成功响应后的原生 Executor 重入、Admission 后结果未知的
UNKNOWN/同一个 Attempt/Reconciliation、错误 Worker owner/token
不能派发。独立 Worker Crash 的 MSSQL 原生验证无需再次执行。

## 严格待办

- 当前没有将此 Adapter 装入 Docker 中的
  `functions-mssql/function_app.py` 原生 Durable handler；
  实际双 Worker 接管之后的 **真实工具端到端派发抑制**
  仍需一次最小故障验收（不能用这两个独立实验拼作一次）。
- Native Instance ↔ RUNNING Attempt 的持久不可变绑定、
  真实外部副作用/回执、二进制版本不兼容 Worker、
  以及未知结果的自动/人工对账仍 OPEN。
- Platform UNKNOWN 不能阻止 Native Durable 内部重放 Handler，
  必须保证所有危险 Tool 调用统一从受控 Adapter 出口经过
  Admission；不应在 MAF Executor 内直接绕过 Adapter 写业务数据。
- 本方案没有产生新的 Harness Scheduler、Lease 服务或 MAF fork；
  只复用平台 A29 已有表与公开接口。
