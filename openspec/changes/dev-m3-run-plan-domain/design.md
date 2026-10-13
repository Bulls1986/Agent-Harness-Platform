# Design · DEV-M3 领域内核与 Workflow 映射

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

DEV-M1/M2 现有 Run 闭环；HC-01。映射 DEV-HC-01 / HC-01。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

Run/Plan/Step/Attempt 领域事实与状态机、Plan 版本、Replan 新 Segment、Workflow ID Binding，不重写 Hatchet DAG/Queue。

### 第二开发切片：模型-only PURE Replan v1→v2（真实 PG + Hatchet）

- 旧 v1 Provider 的技术状态由实际 Hatchet `runs.get_status(workflow_run_id)` 查询；仅 **COMPLETED** 且不存在 PG RUNNING Step、当前 Platform Run/Plan/Provider Binding 未变化、具备冻结的 Replan Intent 时可原子冻结 Plan v2。CANCELLED/取消 ACK、RUNNING、FAILED、UNKNOWN 或外部查询失败一律 Fail Closed。
- `ReplanV2` 原子创建同 Run 的 Plan v2 / Segment PENDING + 稳定 Command Key；新 Segment 使用单独 Outbox PENDING→DISPATCHING→CONFIRMED，创建 ACK 不明为 BLOCKED_UNKNOWN，不盲目重投。旧 v1 `harness_run.provider_workflow_id` 保留以供历史查询，v2 Provider ID 在 Segment Binding 中单独保存。
- 旧版本的 POC `start_step/finish_step/complete` 增加计划版本防护，避免 v2 提交后旧 Attempt 抢写终态；v2 Worker 准入同时校验冻结版本、PG Segment CONFIRMED 及实际 Hatchet Workflow ID。
- `verify_replan_v2_hatchet.py` 真实运行两个独立 Hatchet WorkflowRun，记录 native v1 COMPLETED、v2 Provider Binding、同 Run 的 PG 事件。此路径只支持 PURE/确定性模型任务，**没有验证运行中 Cancel/TERMINATED、非幂等 Tool/Receipt、真实多 Worker 接管、通用 v2 Step/Attempt 完整终态**；因此不能以此关闭整个 DEV-M3 Gate。

### 2026-10-13 第三开发切片：Step 准入/迟到完成的最小领域保护

- M1 的 PostgreSQL POC 层 `start_step` 必须证明 Run 正处于 RUNNING 与冻结 Plan v1，禁止 CREATED/Outbox PENDING 时尚无有效 Provider Binding 就执行 SDK。此项不产生额外 Hatchet 或 Scheduler。
- `finish_step` 在同一事务持有 Run 行锁并同时核验 RUNNING + Plan v1，防止 CANCEL_REQUESTED / CANCELLED 之后过期 Worker 重新写入 Step 终态和 Event；既有 Model/Verification 限制不变。
- 这只涵盖当前模型-only Plan v1 状态保护，不代表已实现版本化 Step/Attempt 全量域模型、同一 Plan 内过期 Attempt 隔离或真实 Provider 安全停机。这些继续按原 M3 1.1～2.3 验收，生产 NO-GO。

### 2026-10-13 第四开发切片：单次 Attempt 身份与重复派发拒绝

- Run/Plan v1 下新增最小 PG `harness_step_attempt(run_id,step_id,ordinal,attempt_id,plan_version,state)`，与 Harness Step 事实一起提交，不镜像 Hatchet Task History。
- `start_step` 接收独立 Attempt ID；同一个 RUNNING Step 即使原 Hatchet 投递重复也不得再次调用 SDK；没有可信失败终态和 Tool Receipt 的再次执行仍拒绝。已有 COMPLETED 的 PURE 输出按冻结输入复用，不产生新 Attempt。
- `finish_step` 同时匹配当前 Plan、Step 状态与最新 Attempt ID、版本、状态，在更新 Step 以及事件前拒绝过期结果。SDK 的 Attempt ID 只是业务关联，并非 HC-03 的工具执行授权；模型文本流及 v2、多 Attempt、非 PURE 恢复属于后续原 M3/M4/M7 Gate。

## Test-first and failure injection

正常验收：已有 Run 在执行 Plan v1 时收到经批准的 Replan → 生成 v2 Plan 和新的 Workflow Segment，旧 Plan/Attempt 仅留审计而不会覆盖。

安全负例：旧 Worker 携带旧 Plan Version/Attempt 提交完成事实 → 平台拒绝旧写入，业务终态未被污染。

## Exit gate

一条真实 Hatchet Run 经 Replan 生成 v2 Plan/独立 Segment，旧 Attempt 不得继续完成。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。