# ARCH-TODO-028 · DBOS / Hatchet 分布式恢复与许可门禁

> 2026-10-10；候选 POC 事实更新，**不是 Accepted ADR**。原有 MAF / Temporal / DBOS POC 继续保留。

## 一、官方资料核实结果

1. DBOS 开源 SDK 可以运行 PostgreSQL 持久工作流和队列，上一轮已实测两个真实 SDK（本地确定性模型）、硬进程退出后新进程恢复。但那**不是 Worker A 不重启、Worker B 自动接管**。
2. DBOS 官方 [FAQ](https://docs.dbos.dev/faq) 明确：多个进程要实现正确工作流恢复需要 Conductor；**自托管 Conductor 免费许可证每应用仅一个 Executor，多 Executor 需要付费许可证**。其 [Self-hosting Guide](https://docs.dbos.dev/production/hosting-conductor/) 标注 Conductor 为 proprietary license。因此通用多 Worker 恢复存在 G8 License Cliff。DBOS 暂不能作为「无商业强依赖的 OSS 分布式恢复」正式选择，除非后续找到合规开源替代方案且完整实测。
3. DBOS [Concurrent Executions](https://docs.dbos.dev/explanations/concurrent-executions) 中的 checkpoint ownership token 防止旧 Worker 持续提交历史，**不保证外部工具副作用 exactly-once**，平台保留 UNKNOWN → Reconciliation → Retry/Abort/Human 契约。
4. Hatchet [主仓库 MIT](https://github.com/hatchet-dev/hatchet/blob/main/LICENSE)。官方 [Embedded Mode](https://docs.hatchet.run/v1/embedded) 支持 Python sidecar 与 checksum 验证，多个 Embedded Engine 可经同一外部 PostgreSQL 共享队列。Python 支持 [DAG](https://docs.hatchet.run/v1/from-temporal-to-hatchet) 与 [Durable Event Wait](https://docs.hatchet.run/reference/python/context)。它们是**公开能力**，不代表多 Worker 实测已通过。

## 二、验证路径与真实状态

| 硬门禁 | DBOS | Hatchet |
|---|---|---|
| PG 队列 / 两个真实 Agent SDK 顺序交接 | LIVE PASS（上一轮） | 新增 GitHub CI POC，待真实运行 |
| 单进程硬退出 → 新进程恢复 | LIVE PASS（上一轮） | NOT TESTED |
| **多 Worker A 硬退出且不重启 → B 自动接管** | **G8 许可证阻断，无免许可方案实测** | NOT TESTED（下一 P0） |
| 持久 WAITING_APPROVAL 不常占 Worker | NOT TESTED | NOT TESTED |
| 外部非幂等工具 ACK 丢失 / UNKNOWN 对账 | NOT TESTED | NOT TESTED |
| 实时 Token SSE / 游标重放 | NOT TESTED | NOT TESTED |
| CubeSandbox / Session / WorkspaceRef / Scope / Fencing | NOT TESTED | NOT TESTED |
| 生产准入 | NO-GO | NO-GO |

**此分支新增：** [真实 Hatchet Embedded DAG + Pydantic/OpenAI 两 SDK 测试](../../poc/durable_engine/hatchet_embedded_live.py) 与 [独立 GitHub CI](../../.github/workflows/hatchet-embedded-poc.yml)。两 Agent SDK 使用本地确定性 Model，仍实际通过仓库既有 `AgentRuntimeDispatcher`；不能宣称真实 LLM/token stream。下载或启动引擎失败即 CI FAIL，不允许 Mock 回退。

## 三、跨 Worker 下一阶段验收

- 两个独立 Engine/Worker、同一 PostgreSQL；真实记录 Worker/PID 与 Run/Attempt/Execution/owner。
- A 领取安全可重复工作，确认第一步持久化后，强杀 A **且不重启**；B 在已运行状态下接管，已完成第一步不重做。
- 对已成功但 ACK 丢失的非幂等 Tool，平台必须 UNKNOWN → Reconciliation，不允许自动重执行外部副作用。
- WAITING_APPROVAL、取消/超时、真实 Cube Session 隔离、资源密度和 Token SSE 分开验收，不能以 Embedded DAG 正例取代整个 Gate。

## 四、集成注意

上轮本地 WebCodex 工作树 `agent-harness-platform-aa548030` 中有未提交的 DBOS 测试/报告，已证明真 PostgreSQL 的部分链路，但 Runner 现离线。本 GitHub 分支仅含 Hatchet 新 POC 及上述许可门禁，**不宣称已经合并本地未提交内容**。恢复 Runner 后，将两个专项按当前 main 冲突情况整合，更新唯一待办 `docs/ARCHITECTURE_BACKLOG.md` 并再做回归。生产依旧 NO-GO。
