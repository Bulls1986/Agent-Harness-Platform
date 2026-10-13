# DEV-M3 · Step 准入与取消后迟到提交防护（2026-10-13）

## 原计划归属和边界

本切片仅属于现有 `DEV-HC-01 / DEV-M3` 的 1.1（拒绝测试）与 1.2（业务状态不可逆保护）的**局部推进**，不创建新的里程碑或业务对象。代码基于 `origin/main` 的独立 Git Worktree 开发，不合并或覆盖并行 Inspector 未提交修改。影响 G01（Run 终态不可写）、G02（领域状态由 Harness 控制）、G08（Cancel ACK 不代表未确认副作用）、G20（真实验收等级）；不改变 Accepted HC-01/02/03。

## Red：实际问题

在 Docker Desktop 的真实 PostgreSQL 16 数据库 `harness_poc` 上，先为 `poc.closed_loop.test_facts_pg` 添加两项可复现拒绝测试：

1. **未绑定 Provider 就启动 Step**：`Run CREATED / Outbox PENDING`、尚无 Hatchet WorkflowRun Binding 时，旧 `start_step` 允许启动 SDK Step，造成无可信调度 Owner 的提前执行。RED 为 `UnsafeDispatch not raised`。
2. **取消后旧 Worker 写回**：`Run CANCEL_REQUESTED` 或 `CANCELLED`、原 Step 仍处于 RUNNING 时，旧 `finish_step` 只检查 `plan_version=1`，未检查 Run state，允许迟到结果写入及发出 `step.completed`。RED 同为 `UnsafeDispatch not raised`。

两项 Red 在真实 PG 运行，均实际 FAIL（2 tests / 2 failures），并非 mock / skip。

## Green：最小修复

- `PgFacts.start_step` 必须在 `Run RUNNING && plan_version == 1` 且已走原 Hatchet Binding 流程的条件下开始执行；CREATED/PENDING 不准执行。
- `PgFacts.finish_step` 在原有数据库事务内持有 Run 行锁，校验 `(state,plan_version)==('RUNNING',1)`，使 Cancel Requested/Terminal 与延迟 Step 回调串行化，阻止它们污染领域 Step、Event 和最终 Run 结果。
- 保留既有 `finish_step` SDK 事件合同、Plan 版本验证、业务完成检查、运行时/Agent SDK/Hatchet Provider 的架构分工；不另造调度器。

## 验证结果

- **真实 PG GREEN**：`poc.closed_loop.test_facts_pg`、`poc.closed_loop.test_plan_guard_pg`、`poc.closed_loop.test_replan_v2_pg` 共 **15/15 PASS（2026-10-13）**，包含取消前后拒绝写回、Provider 未绑定拒绝、Plan v1→v2 旧版本隔离及 Segment 防重复创建。测试直连本机 Docker 的 PostgreSQL，并非外部 Hatchet 联合 E2E。
- **补充离线门禁**：`python -m unittest discover -s tests -p test_architecture*.py -q` **8/8 PASS**；`openspec validate --specs --strict` **3/3 PASS**；`python -m unittest poc.closed_loop.test_real_model -q` **5/5 PASS**（离线合同，不等于实际外部 LLM 调用）。分支 PR/CI 与实际 Hatchet 联合门禁尚未完成，不以这些结果代表阶段退出。

## 未收口事项

M3 仍 **ACTIVE/OPEN**：完整版本化 Step/Attempt/Execution 事实、并发同版本过期 Attempt 的 Fencing、运行中 Hatchet Cancel/TERMINATED、非 PURE Receipt/UNKNOWN 参与 Replan、跨 Segment 新 Provider 真实执行/终态，以及 PR 最新 Head CI 都不在本切片验收范围。取消后是否有实际未完成 Tool 副作用属于 HC-02/03 的证据门禁，不能由本次仅模型-only 状态拒绝测试推断安全。

## 复盘与复用护栏

**根因：** M3 的老 Demo 把 `plan_version==1` 误当作可写入充分条件；Run 状态在模型-only 取消流程和旧 Provider 迟到结果之间缺少第二次核验。**经验：** 每个业务事实写入必须同事务、锁定并核对当前 Run 的可写状态和冻结 Plan/Attempt/Execution 资格；凭据/Provider 是否曾经有效，不代表此刻仍有效。**后续编码护栏：** M3 新的 Step/Attempt 入口统一增加“未绑定 Provider / 终态 / 旧 Plan / 旧 Attempt”负例；不要依靠仅成功路径的 E2E 掩盖迟到回调。