# DEV-M3 最终验收与阶段范围冻结（2026-10-13）

## 结论
**DEV-M3 / DEV-HC-01：CLOSED（最初 Proposal 所定义的限定交付范围）**；整个平台仍然 Production NO-GO。本次仅归档计划和证据，不改动运行时代码、不新增里程碑或额外收口门禁。

> 原 Proposal 交付：一条真实 Hatchet Run 经 Replan 生成 v2 Plan / 独立 Segment，旧 Attempt 不得继续完成。

## 按原任务逐项对账

| 原 Tasks | 原始验收与客观证据 | 判定 |
| --- | --- | --- |
| 0.1 / 0.2 | Accepted HC-01/02/03、G01–G20 未变；真实 PG/Embedded Hatchet、独立合成账本，不含企业私有业务材料 | PASS |
| 1.1 | 版本冻结、迟到 Worker、重复派发、错 Attempt、ACK-loss、UNKNOWN 的 Red→Green 负例及回归（PR #61/#80/#81/#83） | PASS |
| 1.2 | PostgreSQL Run/Plan/Step/Attempt、独立 Segment/Provider Binding、版本化业务事实和不可变结果 | PASS |
| 1.3 | 真实 Hatchet 旧 WorkflowRun v1 COMPLETED → 冻结 v2 → 独立新 WorkflowRun；ACK 丢失对账、Provider 准入和业务完成 | PASS |
| 1.4 / 2.1 | 错 Plan、错 Provider/Attempt、取消/旧写回拒绝；真实 PG 合同和 Native 故障样本 | PASS |
| 2.2 | 开发复盘、风险边界、里程碑和 Backlog 回写 | PASS |
| 2.3 | 主干代码 Merge + 官方实机/架构 CI PASS；本归档 PR 经最新 Head CI 后合并即生效 | PASS（归档合并时） |

## 可核查证据
- [PR #80](https://github.com/Bulls1986/Agent-Harness-Platform/pull/80) 和 [PR #81](https://github.com/Bulls1986/Agent-Harness-Platform/pull/81)：Provider/Attempt 准入、终态与迟到写防护，均 Merge。
- [PR #83](https://github.com/Bulls1986/Agent-Harness-Platform/pull/83)：v1→v2 独立 Segment，PG v2 Step/Attempt/Run 业务终态、已核验回执与旧 PURE Attempt 的安全隔离，Merge `f6fb667b7d1cd4711bb7d64b3ad37f833dbf8e15`。
- [实际 PostgreSQL/Hatchet/双 Agent SDK/Inspector CI #38343878631](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38343878631)：SUCCESS，覆盖 Native PURE、新 Segment ACK-loss、非 PURE UNKNOWN→账本对账、旧 PURE 完成回调丢失四条合成真实执行路径。
- [架构护栏 CI #38343879325](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38343879325)：SUCCESS；不以跳过测试作为通过。

## 不重复加入 M3 的后续需求
通用多 Attempt Retry、Inbox 和 ToolRuntime 属现有 **M4**；物理 Worker 恢复、Cube Scope/Lease/Fencing 属 **M5**；Approval/Recipe 属 **M6**；Gateway/API 属 **M7**；100 Active Runs、IAM/运维/回滚属 **M9**。任意 vN 在线 DAG 热修改不在 M3 最初交付中。安全约束继续生效，但没有外加一个“大而全”M3 收口定义。

## 复盘
此前把 HC-01/02/03 的长期完整架构能力等同于 M3 必须一次做完，造成 Scope Creep。今后以最初 Proposal、Specs、Exit Gate 为准，只有确实违背本阶段原承诺的缺陷才能阻塞，其他问题进入原有后续阶段。本次未合并的 A.6 代码不包含在归档或主干中，不把未评审增强冒称已交付。
