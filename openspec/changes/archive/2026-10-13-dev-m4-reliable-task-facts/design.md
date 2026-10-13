# Design · DEV-M4 持久一致性、Receipt 与任务级恢复

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

DEV-M3 Domain/Segment；HC-02。映射 DEV-HC-02 / HC-02。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

PG transactional Outbox/Inbox、Provider 查询/ACK-loss Reconciliation、Tool Intent/Receipt/UNKNOWN、故障注入后的任务级恢复；不能以跨库 2PC 或自行重建 Scheduler 解决。

### 第一开发切片：PURE v2 Segment 创建 ACK 丢失后原生对账

- 在 `ReplanV2.claim` 已持久写为 `DISPATCHING` 后，Hatchet 可能已经创建 Workflow，但客户端创建调用或 PG Binding ACK 丢失；转为 `BLOCKED_UNKNOWN`，**不得**自动重新创建 Workflow。
- `SegmentReconciler` 根据冻结的 `(run_id,plan_version=2,command_key)` 请求受信任的 Hatchet Adapter 查询已存在 Provider Run；只有 **唯一且元数据精确匹配**的本机 Workflow ID 可原子补入冻结的 Segment/Plan Binding，写一次 `workflow.segment.reconciled` 领域事件并幂等重验。
- 在固定版本 Python SDK 1.42.1 / Engine v0.110.5 的实际测试中，`list_runs(additional_metadata=...)` 曾返回不符合 Filter 的其他 Run。因此 `HatchetSegmentLookup` 必须逐项本地核验 Provider 返回的 `additional_metadata`、Provider 实际 `metadata.id`，执行有上限的**完整分页**；过滤被忽略不算成功，不完整或多匹配继续 UNKNOWN。
- 单元与真实 PG 负例包括缺/多候选、错误 Run/Command/Version、复用旧 Workflow、Provider 异常、分页不完整、重复对账；真实 Hatchet 验证 `additional_metadata` 的查询兼容，以及故意丢失应用层创建 ACK 后无需重新创建就能恢复新 Segment 准入。
- 本切片只覆盖 **PURE、可观察的本地 Hatchet v2 Segment**，不是任意副作用的 Exactly Once 执行证明；不涉及非幂等 Tool/Receipt、真实 SIGKILL、跨 Worker、全量 Outbox/Inbox、Provider 全局唯一性/可见性与生产准入。

### 第二开发切片：非幂等 Tool Intent/Receipt 与独立 PostgreSQL 真实 SIGKILL

- Tool Intent 由 Harness PG 记录不可混淆的 Execution/Run/Plan/Step/Attempt/Owner/Fencing/Operation/Target/Intent Key/SideEffectClass（本切片仅 NON_RETRYABLE）；同 Execution 可以幂等重复登记，冲突事实拒绝；同 Intent Key 不能登记为另一个 Execution。
- **派发先落库**：RECORDED→DISPATCHED 后外部 Tool 才可执行；DISPATCHED、UNKNOWN、CONFIRMED_SUCCESS 均不得盲目重新派发，Owner/Fencing/Plan Version 不匹配立即拒绝。故障观察者根据 Worker 故障或丢 ACK 将其显式标记 UNKNOWN。本次故障观察者由测试驱动，不是已集成 Hatchet 事件监听。
- 用单独 `ledger_poc` PostgreSQL 和真实 SIGKILL 子进程验证：外部账本没有写入幂等保障，写入提交后进程被强制终止。恢复仅查询 **唯一、字段匹配**的外部 Effect/Receipt；0 条、2 条、伪造字段、不可查询均继续阻断。新的 Journal 实例或两个并发 Reconciler 可幂等补记同一 Receipt，不重新执行写入。
- 与 M3/旧 POC 的负例联合验证：存在任何非 PURE Tool Intent 的 Run 不允许由 `ReplanV2.promote` 走 PURE 路径；冻结 Replan Intent 后不能新登记/Dispatch Tool；旧模型-only `complete` / `acknowledge_cancel` 不能忽略已记录非 PURE Tool 后宣称无副作用业务终态。
- 此切片不提供企业身份/审批、真实 Lease/Fencing 颁发或替换 Tool Runner，不承诺外部 Tool Exactly Once，也不构成完整 Hatchet Worker SIGKILL/A→B 接管、工具结果确认策略、非 PURE 多 Plan Recovery/生产门禁 PASS。

### 第三开发切片：真实 Hatchet Native Retry 与 Tool Receipt 恢复

- Hatchet SDK 1.42.1 / Engine v0.110.5 中 `task(retries=1)` 提供技术重试，Harness 不自建补投 Scheduler。首次 Native Task Attempt 持久记录 Tool Intent/Dispatch；不受外部幂等保护的另一 PostgreSQL 接收 Tool 写入，在外部 Commit 后 Tool 子进程遭受 SIGKILL，Hatchet Task 明确失败，由 Provider 自身执行 Native Retry。
- Task Retry 的第二次实际调用只允许查询原执行的 UNKNOWN 结果；PG 可信 Owner / Fencing 从 A/7→B/8 的逻辑交接在服务端时钟确认 Lease 过期、同 Run/Plan/Provider/Execution 和 UNKNOWN 后 CAS 完成。两次 Attempt 共用原有冻结 Tool Intent / Outcome，不重复触发写入。
- Receipt 最终事务增加当前 Recovery Owner、Epoch 与 Lease 再校验（Run/Intent/Owner 行锁）；旧 A 和两名并发争抢者无法提交冲突 Outcome。若外部无/多条证据或 Lease 过期，保持 UNKNOWN。
- **明确限制**：真实 SIGKILL 发生在独立 Tool 子进程，而非 Hatchet Worker A；新 Native Task Attempt 的 Owner B 是平台逻辑执行者，**未证明物理 Worker B 实际接管**。没有真实 Cube Workspace/Isolation/OCI、审批和外部 Policy，不能关闭 DEV-M4/M5 退出 Gate。

### 第四开发切片：物理 Hatchet Worker 进程故障与独立实例原生接管（实测门禁）

- 在同一外部 Hatchet PostgreSQL 上运行多个 Hatchet Embedded Engine 进程，先启动控制端并执行一次 Schema Migration，其余进程关闭 Migration；**Engine 技术 Task Reassignment 仍由 Hatchet 管理**，Harness 不实施第二套 Worker Recovery Daemon。
- Worker A 进程组收到 **OS SIGKILL (-9)** 的注入点必须位于真正的外部 NON_RETRYABLE Tool Commit 之后、Harness Receipt 之前；控制进程检查其 OS 退出码与外部账本事实，才启动完全独立的 Worker B 进程。不能仅重启 SDK 子 Task 来冒充物理接管。
- Worker B 必须由 Hatchet 原生 Retry/Task Queue 领取同一个 Provider WorkflowRun，查原 Execution `DISPATCHED/UNKNOWN` 并标记不确定，使用 PG Server-clock Owner Lease 过期后的 `A/7→B/8` CAS 获得**仅对账授权**，外部查询唯一可信 Effect 后确认原 Receipt，不派发第二次 Tool。
- 验收同时检查实际 OS `A.pid/exit=-9`、`B.pid`、Hatchet Native Retry Count、相同 Run/Workflow ID、PG Fencing/Receipt 事件各一次、外部账本只有 1 条写入。任何不确定都保持门禁 RED，不能以 DONE 的单条状态替代全链路证据。
- 本切片不覆盖真实 Cube Sandbox/Workspace/Scope/OCI/Guest Tool Bridge、生产身份/审批、跨主机部署、多副作用类型与完整恢复编排；即使通过，不关闭 DEV-M4/M5 整阶段 Gate。

## Test-first and failure injection

正常验收：Provider Workflow 已接受而 Harness 创建调用超时 → 进入 BLOCKED_UNKNOWN，查询 Provider 并对账，不盲目重复创建。

安全负例：外部工具已经写入，Worker 在返回 Receipt 前 SIGKILL → 核对实际副作用；未知则人工介入或保持阻断，绝不自动重放。

## Exit gate

真实 PG/Hatchet 和非幂等工具在丢 ACK/SIGKILL/并发重试下可核对且不盲目重复副作用。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。
## 正式阶段验收与范围冻结（2026-10-13）
最初交付仅为真实 PG/Hatchet + 合成非幂等 Tool 在 ACK-loss、SIGKILL 和并发 Retry 下不盲目重放的可核对任务恢复。A.1～A.4 真实原生引擎、双库及物理 Worker A→B 的证据已经独立通过；仅补最小 `ProviderObservationInbox`：可信 Adapter 读取当前 Native Task 结果，以冻结 Provider Binding/Plan Version 和单调 source sequence 校验，Run 行锁下按 native event key/fingerprint 同事务去重、只生成一条平台观察 Domain Event；Native Task SUCCEEDED **不直接将平台 Run COMPLETED**。纳入现有物理 Worker 联测，在同一个真实 Native Retry 结果上重复观察 2 次，必须只应用一次。仅此为本阶段原有 Inbox/Domain Projection 必要缺口。
阶段保持非目标：通用事件总线/通用 ToolRunner、任意外部系统 exactly-once、跨宿主 Cube 恢复或 M9 安全容量；HC-02 的 UNKNOWN 坚持 Fail Closed。审查者应以本归档 PR 最新 Head 官方 CI PASS 及合并为正式 CLOSED 生效条件；不能以本地孤立单测冒充完整阶段 Gate。
