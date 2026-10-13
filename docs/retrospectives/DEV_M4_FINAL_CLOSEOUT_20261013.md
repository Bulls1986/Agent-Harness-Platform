# DEV-M4 正式阶段收口验收与范围冻结（2026-10-13）

## 原始验收合同
**仅闭合 DEV-M4 / DEV-HC-02 最初 Proposal/Specs：**真实 PostgreSQL、Hatchet 与模拟非幂等外部系统在创建 ACK 丢失、实际 SIGKILL 与并发重试时可对账，UNKNOWN 不盲重放。没有引入跨数据库分布式 2PC 或第二套 Scheduler。只有本归档 PR 最新 Head 的全部适用 CI 通过并合并 Main，此 CLOSEOUT 才正式生效。

## 已证实的原始交付
- **A.1（Provider 创建 ACK 丢失）**：真实 Hatchet v2 Segment `BLOCKED_UNKNOWN`，原生查询多页/元数据逐行精确匹配/唯一性确认后补录已有 Workflow Binding；错误/缺失/多个匹配皆停 UNKNOWN。真实 [CI 38142456717](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38142456717) PASS。
- **A.2（独立外部非幂等 DB）**：另一 PostgreSQL 的无幂等写入已 Commit，Worker 子进程 SIGKILL，Harness Receipt 未保存；旧状态标 UNKNOWN，0/2/伪造/不可查询结果拒绝；只在独立查询唯一匹配回执后补录，双 Reconciler 并发只一条业务事件。见 DEV_M4_NONIDEMPOTENT_TOOL_RECEIPT_SIGKILL_20261011.md。
- **A.3（Hatchet Native Retry）**：真实 Native Task Retry 使用原有不可变 Execution/Attempt，PG Server-clock Owner/Fencing 7→8，重试只核对，不重新写。原有 M4 CI PASS。
- **A.4（物理 Worker 交接）**：实际 OS Worker A SIGKILL(-9)、独立进程 B Native Retry 同一 WorkflowRun，原外部账本只有 1 条 Effect，Receipt 为 CONFIRMED_SUCCESS。已知 [CI 38145779308](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38145779308)、[CI 38341410826](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38341410826) SUCCESS。
- **原始 Inbox/投影必要缺口**：先写真实 PG Red（模块与去重逻辑不存在）；新增受信任 Adapter 入口 `ProviderObservationInbox`，锁定 Run/冻结 Provider Binding、对相同 Native 观察 Key/哈希幂等，对不同或乱序 Provider sequence Fail Closed，防止业务 Terminal 被重复/旧观察改写。新实例与两并发 Observer 只持久化一条 `provider.observed` Event。真实 PostgreSQL **6/6 PASS，0 SKIPPED**；补入已有物理 Worker A→B 同一 Native 结果观察重复投递联测，由 **本归档 PR 最新 Head CI** 验证。
- **现有 Outbox**：Run+稳定命令键同 PG 事务持久化；v2 Segment 持久 Claim/Binding 及 ACK 丢失后 Provider Lookup；不能在 UNKNOWN 时自动重新创建 Workflow。

## 原 Tasks 0.1～2.3 与 Exit Gate
原合成环境、Accepted HC-01/02/03、PG/Provider 所有权未修改；已通过 Red→Green/并发/无回执/乱序/真实 SIGKILL；适用 CI 执行真实 PG、Native Hatchet、非幂等外部账本，不以 SKIPPED 替代 PASS；最终原 OpenSpec Tasks 全部打勾、按标准归档、形成正式 Spec；本归档 PR 最新 Head 严格验证/架构审查和主干合并后 M4 状态 CLOSED。

## 严格非目标、残余风险
- 本验收仅涵盖可重复的**合成单宿主 Hatchet Fleet + PostgreSQL**，不是任意外部副作用的 Exactly Once，也不是所有 Provider 通用 Inbox 插件。
- 通用 ToolRunner/Approval/Policy、跨宿主部署、任意多次 Attempt 受控恢复/长时故障、高并发负载、Cube Guest/OCI 和生产 IAM/容量/安全均不因 M4 关闭被虚构为已完成，交回既定后续 M5/M6/M9 或后续版本评审。
- 外部系统无法给出唯一可信 Effect 时，继续 **UNKNOWN 阻断人工对账**，不因 Hatchet Native Retry 而重新执行。
- **Production NO-GO** 不变。

## 复盘
之前将 HC-02 长期理想状态（跨宿主、完整 Tool Runtime、任意系统 Exactly Once）持续追加为 M4 的新退出条件，导致无法收口。本轮坚持最初 Proposal 的有限实际交付：Outbox/Inbox + ACK-loss + 非幂等 Receipt + 真实 SIGKILL 受控恢复。新增代码仅是原来明确承诺而缺失的 Inbox 去重；其余已有 CI 直接引用，不重复研发第二套调度/引擎。
