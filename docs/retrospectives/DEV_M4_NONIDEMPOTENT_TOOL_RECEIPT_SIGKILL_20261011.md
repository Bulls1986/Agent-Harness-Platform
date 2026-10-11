# DEV-M4 非幂等 Tool Intent / Receipt UNKNOWN · 真实双库 SIGKILL 子切片（2026-10-11）

## 本轮目的与边界

在**两套不同的真实 PostgreSQL 数据库**中验证 HC-02 的危险窗口：Harness 事务已经记录 Tool Intent/Dispatch；独立外部账本不可幂等地完成写入；调用进程在外部数据库 Commit 之后、Harness Receipt 写入之前遭受操作系统 `SIGKILL`。恢复方不得重放同一个 Tool，必须通过可信外部事实核对。此 POC 不等于通用 Tool Runner/Runtime/Hatchet Worker 接管，也未通过完整 M4、M5 或生产门禁。

- Harness PostgreSQL 的 `harness_tool_intent` 是**唯一业务事实**：`execution_id`、Run/Plan、Step/Attempt、Owner/Fencing、Operation/Target/Intent Key、SideEffectClass（此切片仅 `NON_RETRYABLE`）、状态与 ReceiptRef。其状态：`RECORDED → DISPATCHED → UNKNOWN → CONFIRMED_SUCCESS`；正常读取外部 Receipt 可从 `DISPATCHED` 对账，不能由 Provider Task 成功代替 Receipt。
- `synthetic_external_effect` 位于独立 `ledger_poc` 数据库中，**故意不对 execution_id/idempotency_key 设置唯一约束**：相同 Tool 二次调用一定会产生两次效果，借此测试“禁止盲重试”是真实 Gate 而不是被外部幂等能力掩盖。
- `nonidempotent_fault_worker.py` 独立 Python 进程从持久 Harness PG 读取已 Dispatch 的冻结事实，在调用外部 Ledger 后使用 `SIGKILL` 强制结束；在 `before-commit` 负例中先杀进程，缺失外部记录仍不可推断可重试。
- 故障观察者随后显式调用 `mark_unknown(..., EXECUTOR_CRASH)`（**本次为测试驱动，未集成真实 Hatchet Worker Crash Event Dispatcher**），新的 Journal 实例在读取唯一、字段完全匹配的 `EffectEvidence` 后原子补记 `CONFIRMED_SUCCESS`。未查询到/多条/冲突/无法连接一律拒绝自动确认为成功，继续 UNKNOWN；没有实现“可靠证明未执行后生成新 Attempt”的流程。
- `dispatch` 只能一次从 RECORDED 迁移，需匹配持久 Run 的 Plan Version、Owner/Fencing；任何已 Dispatch/UNKNOWN 的重入均拒绝。测试的 `require_confirmed` 是受控下游保护 Port，**还没有正式挂到所有 AgentRuntime Tool 工具入口**。

## 测试先行与真实故障证据

1. 先提交 `test_tool_receipt_fault_pg.py`、强制双数据库和 SIGKILL 的独立 CI 工作流。最初 [Red CI 38143300354](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38143300354)：两个独立 PG 数据库实际已创建，测试因尚不存在 `tool_receipt` 模块报 `ModuleNotFoundError`。
2. 增加 PostgreSQL Tool Journal、独立外部非幂等账本、子进程 SIGKILL 故障注入。首次 [Green CI 38143468488](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38143468488) **6/6 PASS、0 SKIPPED**，确认外部 Ledger 写入一次、SIGKILL (-9)、持久 UNKNOWN 无重复写入、查外部唯一证据后成功确认、两个 Reconciler 并发只确认一次。
3. 回归包括外部已提交与未提交两个 Crash 点、外部产生两条同键写入时拒绝确认、Owner/Plan/Fencing/Attempt 漂移、伪造 Receipt、不重复派发/无自动下游放行、重连/并发。
4. 最终 CI 证据请以 PR #70 最后 Head 的工作流结果为准，不预先用早期 Green 代表最终提交通过。独立架构 CI 同步检查 G01～G20。

## 设计与故障复盘

- **没有外部副作用 ≠ 已证实未执行**：独立账本查询的“无匹配”可能源自事务/可见性、网络、检索延迟；不能据此自动生成新 Attempt。
- **数据库内幂等**不等于跨数据库 Exactly Once；故意不提供外部去重，保证“第二次真的会多写”，由控制层审慎禁止 Dispatch 重入。
- **只有唯一且完全匹配的可信外部证据**才能更新 Receipt：Execution、Operation、Target、Intent Key、不可为空的 external_reference；多条效果需人工/异常处理，不能当作无事发生。
- **旧执行者与 Recovery 权限尚不完全闭环**：现有测试验证执行前 Owner/Fencing 和冻结 Plan；没有验证真实分布式 Lease 权威、可信审批、跨 Worker 夺权、运行中异步请求已经发出后的 Owner Revoke。本次 demo 将冻结字段注入到独立 Tool 进程，并不暴露为公共 HTTP 请求合同。
- **日志/对象**仅使用合成 Run/ID/账本，不携带任何外部业务消费者私有数据，也没有写 Host Shell 工具入口。

## 仍未通过的正式 M4/M5 Gate

真实 Hatchet Worker A 崩溃→B 经 HC-03 Lease/Fencing 接管；SDK/Tool 实际双库之外的执行抽象；重复/乱序 Provider Inbox 和通用多 Segment Outbox；外部未执行时的可信 Negative Receipt/新 Attempt；非幂等 Tool 的恢复、终态/Approval/Artifact/Verifier 全链路；真实 Cube Sandbox；生产安全、100 Active Runs。以上 OpenSpec 0.1/0.2、1.1～2.3 仍 OPEN，仅独立 A.2 可据 CI 勾选。
