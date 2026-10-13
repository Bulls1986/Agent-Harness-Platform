# DEV-M4 持久一致性、Receipt 与任务级恢复 · Tasks

> 状态：**CLOSED（原始 DEV-HC-02 限定范围；本归档 PR 最新 Head 真实 M4 CI 通过并合并后正式生效，Production NO-GO 不变）**。任务与原始 Proposal/Spec 对账，不额外追加跨宿主或通用 Tool 平台。

## 0. 前置与需求冻结
- [x] 0.1 审阅原有 Accepted ADR/HC 与 G01–G20，识别事实 Owner、安全边界和阻断依赖；OpenSpec 四类规划材料 Strict PASS。
- [x] 0.2 确认代表性真实业务/失败样本、环境及测试数据，记录本阶段交付与不做范围。

## 已有证据的独立开发子切片（不替代完整阶段 Gate）

- [x] A.1 基于真实 PostgreSQL / Hatchet SDK 1.42.1 + Engine v0.110.5，验证 PURE v2 Segment 创建 ACK 丢失后的 `BLOCKED_UNKNOWN`，只经元数据精确匹配、完整分页和唯一 Native Provider ID 对账补录，拒绝盲目重建/不明旧 Workflow；**证据**：docs/retrospectives/DEV_M4_SEGMENT_ACK_RECONCILIATION_20261011.md（初始 Red CI 38142140618、过滤泄漏 Red CI 38142256547、真实 PG/Hatchet Green CI 38142456717）。仅限该场景；Receipt UNKNOWN、非幂等 Tool、SIGKILL、跨 Worker 仍 OPEN。

- [x] A.2 HC-02 非幂等 Tool Intent/Receipt 的真实双 PostgreSQL 事务与故障注入：外部账本允许重复副作用，独立 Worker 进程在外部 Commit 之后、Harness Receipt 之前遭受 SIGKILL，Harness UNKNOWN 阻断重派，只依据唯一且匹配的外部证据补记 Receipt；两 Reconciler 并发去重、旧 Owner/Fencing/Plan、外部重复/缺失记录、跨 M3 PURE Replan/旧模型终态负例；**证据**：docs/retrospectives/DEV_M4_NONIDEMPOTENT_TOOL_RECEIPT_SIGKILL_20261011.md（Red→Green、独立双库 CI）。仅此子切片完成；真实 Hatchet Worker A→B 接管、非幂等 Tool Runtime 全链路、自动故障观察、正式 Receipt 策略和 Cube Gate 仍 OPEN。

- [x] A.3 真实 Hatchet Task Native Retry → Non-PURE Tool Receipt UNKNOWN 集成（固定 Hatchet SDK 1.42.1 / Embedded Engine v0.110.5，三套独立 PG）：首次 Attempt 的外部 Tool 子进程 Commit 后 SIGKILL，Hatchet 原生 Retry=1，新 Attempt 仅对账不重新写；PG Server-clock Owner/Fencing 7→8 CAS 在重试 Handler 中拒绝旧 Owner、确认唯一 Receipt。**证据**：docs/retrospectives/DEV_M4_HATCHET_NATIVE_RETRY_RECOVERY_FENCING_20261011.md（真实 Native Provider ID/Retry Count/非幂等写入次数/CI）。**物理 Hatchet Worker A SIGKILL / 独立 Worker B 接管未测**，M4 整阶段 OPEN。

- [x] A.4 真实 Hatchet 多进程 Fleet 的**物理 Worker A 进程组 SIGKILL→独立 Worker B 进程**，Hatchet 原生 Retry 重新派发同一 WorkflowRun，PG Owner A/7→B/8 Fencing 后只查询原 Non-PURE UNKNOWN Receipt，外部非幂等账本仍 1 次写入。**证据**：docs/retrospectives/DEV_M4_M5_PHYSICAL_WORKER_TAKEOVER_20261011.md（CI 38145779308：A exit -9、A/B 不同 OS PID、native Retry=1、Receipt CONFIRMED_SUCCESS）。仅限无 Cube 的同宿主 CI Fleet；通用 ToolRunner、Inbox、长时故障/跨宿主 Gate 仍 OPEN。

## 原始范围冻结与阶段验收证据
- **原 Proposal/Spec 唯一退出交付**：真实 PG/Hatchet + 外部非幂等工具在创建 ACK 丢失、真实 SIGKILL、并发 Recovery/重试时能够凭独立证据对账，不会盲目重复副作用；PG transactional Outbox/Inbox 以及 UNKNOWN 拒绝门禁。没有第二 Scheduler、没有分布式 2PC。
- **0.1/0.2**：Accepted HC-01/02/03、G01–G20 原则和平台事实/Provider 历史 Owner 不变。实测对象仅是合成 Run、Hatchet/三套独立 PostgreSQL/可重复写的模拟外部账本；不含私有业务数据。证据：docs/retrospectives/DEV_M4_FINAL_CLOSEOUT_20261013.md。
- **1.1/1.2**：已有平台 Outbox 稳定命令键、v2 Segment Claim/Binding、可信 Provider Lookup/ACK-loss；独立 Tool Intent→DISPATCHED→UNKNOWN→CONFIRMED_SUCCESS 实际 PG Journal。缺口只补 Provider Observation Inbox：同事务 Run 锁 + Inbox/Domain Event、一致的 Provider Binding 和 sequence 校验、重复事件幂等、乱序/伪造/终态 Fail Closed。真实 PG TDD Red→Green 6/6。证据：docs/retrospectives/DEV_M4_FINAL_CLOSEOUT_20261013.md。
- **1.3**：真实 Hatchet Worker A OS SIGKILL→独立 Worker B Native Retry；外部 ledger 真正 commit 后丢 Receipt；旧 Owner Fencing 后只有一次确认的外部 Effect。Inbox 在原生 B 结果可信控制端观测到时落一次业务观察，第二次读取仅 ALREADY_APPLIED；Provider 结果不直接变为 Run.Completed。见原 A.1～A.4 的真实 CI 证据及本归档 PR 最新 Head。
- **1.4/2.1**：真实 PG UNKNOWN 0/2/伪造外部回执、安全拒绝、并发双 Reconciler、乱序 Inbox、旧 Provider/terminal 拒绝；真实 M4 CI 必须 PASS、SKIPPED 不计。证据：docs/retrospectives/DEV_M4_FINAL_CLOSEOUT_20261013.md。
- **2.2/2.3**：原有故障复盘 + 最终阶段验收，正式规范存入 `openspec/specs/reliable-task-facts/spec.md`；最新 Head 的 M4/架构/里程碑回归通过并合并后原子归档。
- **阶段非目标**：完整通用 Tool/Approval/Policy Runner、Cube Guest、跨主机容灾/Lease 与 M9 生产安全容量不追加为 DEV-M4 退出门禁；M5/M6/M9 原状态保持。仍保留 UNKNOWN 的 Fail Closed 安全约束。

## 1. TDD 与集成开发
- [x] 1.1 先写重复命令/并发 Outbox、ACK 丢失和 Receipt UNKNOWN 失败测试；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [x] 1.2 实现 Outbox/Inbox、Provider 原生 Lookup、Receipt 状态及 Reconcile；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [x] 1.3 真实 SIGKILL/并发/乱序/外部写侧副作用故障注入；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [x] 1.4 恢复决策审计、CI/复盘和 UNKNOWN 安全门禁；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。

## 2. 阶段 Gate 与复盘
- [x] 2.1 复验 副作用 UNKNOWN 的拒绝/故障合同，正例、负例和真实集成全部 PASS；无 SKIPPED 冒充通过。
- [x] 2.2 记录故障根因、设计修正、测试覆盖、可复用护栏及风险，完成复盘与 Backlog 状态更新。
- [x] 2.3 代码 PR/CI、架构审查通过，确认无后续生产门禁被错误关闭后，勾选 Tasks 并归档该 OpenSpec。