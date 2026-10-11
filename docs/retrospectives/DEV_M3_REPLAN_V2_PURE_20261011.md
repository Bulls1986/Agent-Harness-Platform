# DEV-M3 · PURE Replan v1→v2 独立 Workflow Segment 真实验证（2026-10-11）

## 范围

本切片实现 **同一个 Platform Run 下持久化 Plan v2、独立 Segment Outbox 和真实 Hatchet v2 WorkflowRun**；只覆盖模型/Verifier **PURE、无外部副作用** 场景。未覆盖真实取消旧 Worker 的 TERMINATED ACK、非幂等 Tool Receipt/UNKNOWN 对账、跨 Worker/Lease 和完整业务 Step/Attempt/Artifact 终态。M3 全阶段依然 OPEN，Production NO-GO。

坚持事实归属：Harness PG 为 Run/Plan/Segment 的业务权威，Hatchet Engine 为 Workflow/Task/队列/重试权威；Provider ID 只是不可伪造的外部绑定引用。无第二套 Scheduler；不假设热修改现有 Hatchet DAG。

## Red → Green 证据

1. PR #68 先加入真实 PostgreSQL `test_replan_v2_pg.py` 与强制 CI 测试；[Red CI run 38141097324](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38141097324) 因模块未实现失败。
2. 增加 `ReplanV2` 及独立的 `harness_replan_segment_v2`/冻结 Plan v2：仅可信 Hatchet Adapter 报告类型化 `COMPLETED` 时可提交；RUNNING/CANCELLED/FAILED/未知/超时、活动 Platform Step 均拒绝。PG CAS 将版本 1→2 与 Segment PENDING 一次事务持久化；不因重复 Intent 产生第二条 Segment。
3. `claim(key)` 将 Segment Outbox PENDING→DISPATCHING，真实 Workflow ID `bind(key,id)` 后变为 CONFIRMED；创建 ACK 未知标记 BLOCKED_UNKNOWN，重复 claim/伪 Provider Binding 不放行。
4. 老版 POC `PgFacts.start_step/finish_step/complete` 增加版本 fencing；旧 Plan 的新 Step 被 Replan Intent 阻止，v2 提交后旧 Attempt 不得补写业务完成或旧 Run 终态。新 Segment 的 `admit` 必须同时匹配版本、确认的 PG Provider 绑定和当前 Run。
5. [真实 PG/双 SDK/架构 Green run 38141229702](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38141229702) **SUCCESS**。加入实际 v1→v2 Hatchet proof 后 [CI run 38141333840](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38141333840) **SUCCESS**：PG/API/Model/SSE/M3 回归 26/26，架构负例 8/8，旧最小闭环及 Inspector 重启通过。
6. 真实 Hatchet proof（2026-10-11）：Platform Run `m3-hatchet-660d9f99b95141569ff7eb50aeac427e`；原 Workflow `2cedb384-e346-47c9-9de3-f26253176776` 原生状态 **COMPLETED**；新 Workflow `0ee0de88-a445-4076-9df6-8f206410fce3`，独立且 PG `CONFIRMED`；Run 保持同一标识、Plan 版本为 2、8 条持久 Event。结果标注 `PASS_LIMITED_PURE_M3`，`tools_or_receipts=NOT_TESTED`、`old_worker_cancel_ack=NOT_TESTED`。

## 失败模式与保护

- **Provider 取消请求或 Cancel ACK ≠ 已完全停止**：只有真实 Native `COMPLETED` 为本 PURE 切片的准入。其它状态一律保留 v1 阻断，不创建新的有权限 Segment。
- **无副作用并不等于可随意重试**：已经派发而绑定 ACK 不确定的 v2 Segment 保持 BLOCKED_UNKNOWN，不盲目重放 workflow.create。
- **旧 Step 与异步终态竞态**：Version fencing 保护 legacy Step/Run 写入口。严格声明本次不是完整统一 Step/Attempt 的多版本实现，尚缺泛化的 v2 业务完成路径和旧 Worker 接管实测。
- **状态展示**：保留旧 Intent 原始 BLOCKED 历史；当 Run 已冻结 v2 时，Inspect 投影呈现 COMMITTED，同时 Segment 的 PENDING/DISPATCHING/CONFIRMED 单独表示技术绑定状态。
- **资源关闭日志**：在真实 Embedded Engine 测试结束时可观察到 Python resource_tracker semaphore warning；该警告不等于 Gate 失败，但进程退出资源卫生仍须独立检查。

## 下一步真实 Gate

1. M3 完整领域 Step/Attempt/Version/Segment 与新的最终业务完成规则，旧 Attempt/Owner 真实 Worker 写侧拒绝。
2. Hatchet 运行中停止/取消的 **TERMINATED/真实 Worker 收口**，以及未知状态阻断；不可用本次仅 `COMPLETED` 的安全路径替代。
3. 与 M4 的真实非幂等 Receipt/UNKNOWN、Provider Lookup/Reconcile、ACK-loss 并发故障联动；再覆盖 M5 Worker/Cube Lease/Fencing。
4. 所有 OpenSpec 主阶段 Tasks 0.1/0.2、1.1～2.3 仍未满足整阶段 Gate，不勾选。仅新增可独立验收子切片 A.2。
