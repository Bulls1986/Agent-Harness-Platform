# DEV-M3 · Plan v2 业务闭环、非 PURE Replan 与旧 Attempt 安全退出（2026-10-13）

## 归属、事实 Owner 与范围

直接推进原有 DEV-M3 / DEV-HC-01 / openspec change `dev-m3-run-plan-domain`，不建立新路线或附加里程碑。按 Accepted HC-01（Versioned Plan/Step/Attempt/Workflow Segment）、HC-02（UNKNOWN→真实 Receipt 对账）、HC-03（可信 Scope/Owner/Fencing）、G01/G02/G03/G08/G09/G20 实施。

Hatchet 仍持有原生 Workflow/Task/Retry/终止技术事实；Harness PG 只持有最小业务 Step/Attempt、冻结 Plan、Provider Binding、Verifier Result、外部已确认 ReceiptRef 和 Event，不另起调度器/Engine History。

## Red → Green 故障矩阵

1. **真实 v2 Segment 有执行资格但无业务 Step/Attempt/终态**：原版 `ReplanV2` 只允许准入第二个 Hatchet Workflow，不能记录真实 v2 Step/Attempt 或业务 Run Completed。先写 `test_replan_v2_execution_pg.py`，5/5 在真实 PostgreSQL 以缺失方法报错（RED）。
2. **非 PURE 副作用未分级**：原版 `promote` 对任意 Tool Intent 全部拒绝，无法把可信外部回执已完成与 UNKNOWN 区分；也没有将 frozen effect policy 关联到 Segment。先写 `test_replan_non_pure_pg.py`，3/3 缺失显式 policy 参数（RED）。
3. **旧 Provider 已真正 COMPLETED 但原 PURE Step 完成回调丢失**：原版只要旧 Step=RUNNING 就永久阻挡 Replan，无法保留旧 Attempt 并安全进入新版本。先写 `test_replan_orphaned_attempt_pg.py`，4/4 缺少 opt-in 的可信静止旧 Attempt 处理（RED）。
4. **取消与新 Segment 创建的竞争**：原版 `claim`/`bind` 未检查当前 Run 状态，取消后仍可派发或绑定新的 Provider。2 个真实 PostgreSQL 负例重现该缺陷（RED）。

## 实现与强制保护

- 新增版本化 `harness_plan_step` 与 `harness_plan_step_attempt` 最小 PG 业务事实，包含 v2、Provider Binding、Step、Attempt、不可变结果。Run row-first 锁/业务状态和冻结 Plan、Segment CONFIRMED、准确 Provider ID、对应 Attempt ID 校验，拒绝过期 Step Writer 与重复提交。旧 v1 POC 表保留历史，不覆盖 v1 Attempt。
- v2 正式 Native Task 必须经过业务 Step start→finish，Provider 实际 Native COMPLETED 后，由可信 Host 验证回传内容与已持久化 v2 Verifier Output 一致，才可原子写 Run COMPLETED；数据库模型/Tool 副作用的真相不能用 Hatchet SUCCEEDED 自动代替。
- 明确副作用处理策略：默认 `PURE_ONLY`，看到任何外部 Tool Intent 都 Fail Closed；只在显式 `CONFIRMED_RECEIPTS_ONLY` 情况，验证所有**历史 v1** Tool Intent 已由 M4 外部证据确认 `CONFIRMED_SUCCESS` 并有独立外部引用，才允许晋升并完成 v2。任何 `UNKNOWN` / `DISPATCHED` / 未确认 / 新 v2 Tool Intent 再次阻断，Run Result 记录已确认执行的 Execution ID 和外部 ReceiptRef，而不是盲执行同一副作用。
- 有旧 PURE Step RUNNING 时，默认仍拒绝 Replan。只有显式 `resolve_inflight_pure=True` 且旧 Provider Native 已真实 `COMPLETED`、旧 Step/Attempt 身份齐备、完全无 Tool Intent，才在晋升新 Plan 的**同一个 PG 事务**中将旧 Attempt/Step 标为 `SUPERSEDED` 并记录证据；不重新执行旧 Workflow，不以 Cancel ACK 当 TERMINATED。
- `claim`/`bind` 原子检查 Run RUNNING+Plan2，统一 Run→Segment 锁顺序；取消后拒绝新创建和迟到 Binding；UNKNOWN 可保留技术不确定证据，但终态 Run 不再追加业务 Event。M4 Segment Reconciler 使用相同锁顺序，保持可靠 ACK 丢失对账。

## 分层验收

- **本机真实 PG 合同（开发门禁）**：新增/既有 v2/非 PURE/旧 Attempt/取消/ACK-loss/双 SDK Step/SSE 等共 43 项真实 PostgreSQL 用例；RED 证据见上，最新全量结果以测试执行与 PR 记录为准。
- **代码静态/架构**：Python 3.12 Compile, Architecture Guards, M3 OpenSpec Strict，须独立 PASS。
- **真正跨组件 Live Gate（CI 必须验证）**：原有 GitHub Actions closed-loop workflow 继续真实 Hatchet+两个 Agent SDK+Inspector，同时新增 4 次 M3 Native Replan 正例：PURE 双独立 Workflow、创建 ACK-loss Native 查询对账、**Native v1 的真实非幂等独立外部 PostgreSQL 账本写入 → LOST_ACK → UNKNOWN 阻断 → 独立查询确认 → v2 新 Provider 终态且无重放**、旧 Native Provider Completed 但 PURE PG Step callback LOST → 同 Run 旧 Attempt SUPERSEDED → v2 业务终态。该 CI 为 synthetic ledger + embedded Hatchet；不是生产 Tool 权限、Cube Guest 或跨宿主全部集成。
- **代码 PR/官方 CI/最新 Head**：待创建 PR 与官方最新 Head 门禁独立报告，不能因本机 PG 绿色冒称阶段 Gate。

## 复盘 / 未关闭风险

根因：早期 M3 POC 以新 Workflow 是否能运行替代完整业务事实验收；对所有 Tool Intent 一刀切阻断，没有可核验的安全继续策略；旧 Provider 静止、业务 Step completion LOST 未被模型化。架构原则已经禁止从 Hatchet 直接产生业务成功，本次通过独立 PG 业务事实 + 可信证据 Gate 补全。

仍需对照原 DEV-M3 1.1～2.3 全范围 Gate：原生 Worker 真正取消/TERMINATED 证据、多 Attempt 同 Plan 安全 Retry 与 Owner Epoch/Lease Fencing、原生跨 Worker/Cube Guest 联合测试、带真实审批/Tool 的通用 Step/Attempt、更加完整的 Plan 版本链（不只 v1→v2），以及生产级错误/容量/策略。若没有对应 Live 验收，M3 保持 ACTIVE，Production NO-GO，不通过改写规格掩盖缺口。