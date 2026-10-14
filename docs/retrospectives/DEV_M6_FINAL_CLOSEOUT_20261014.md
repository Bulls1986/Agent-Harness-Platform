# DEV-M6 最终限定收口 · 2026-10-14

## 结论

**DEV-M6 CLOSED（原始有界合成 Recipe），Agent Harness Platform 生产仍 NO-GO。**

本次仅验收原定 1 条通用合成 Recipe：规划（Pydantic AI SDK）→ WAITING_INPUT → WAITING_APPROVAL → 编码（OpenAI Agents SDK）→ 验证（Pydantic AI SDK）；不增加 Recipe、Runtime、Agent 进程模型、调度器、业务消费者或 Inspector 页面。不把企业 OSS、IAM、跨主机生产运维归入本次完成范围。

## 正式 Pull Request / CI

- [PR #95](https://github.com/Bulls1986/Agent-Harness-Platform/pull/95) 原始代码版，GitHub 提交 SHA `308d0a2fea67ee6432b4cfe9c5ab7cffa5329f0b`。
- [真实 PostgreSQL + Hatchet + 3 SDK + M6 原生恢复 + Inspector CI #38499209969](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38499209969)：**SUCCESS**；其中原生 M6 正常、拒绝、Worker A→B 物理恢复均在同一实际 CI Job 通过，已有 M7/重规划/Inspector 回归也成功。
- [官方 Architecture Guardrails CI #38499209960](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38499209960)：**SUCCESS**。
- 本报告和 OpenSpec 归档属于后续同一 PR 的**最终文档提交**；归档后的最终 Head 仍必须重新经过上述等价门禁才能合并。文档先行不算仓库已合并或生产准入。

## 已验证的业务与故障事实

1. 冻结 Recipe JSON 版本、Project Scope、Run/Step/Attempt、不可更改已验证输入与 ArtifactRef；后续 Step 只能接受经过实际字节和 SHA-256 校验的已验证产物。真实 Harness PostgreSQL 合成合同 12/12；独立字节夹具 2/2；原有架构/里程碑单测 23/23。
2. 真实 Hatchet Engine/Worker 运行 Pydantic AI → OpenAI Agents SDK → Pydantic AI 三个 SDK；`WAITING_INPUT` / `WAITING_APPROVAL` 使用 Hatchet 原生 durable event，Harness PostgreSQL 记录唯一领域状态，等待恢复不创建第二个业务 Run。
3. 审批拒绝真实运行：Run `m6native-f5d4c3f719fd4552acf12437efa7383f`，Provider `57dbc40a-5266-4691-8e42-780bbc3c9ebb`，状态 BLOCKED；编码未启动，外部副作用数量 0。
4. 真实 LiteLLM Responses API，模型 `glm-5.3-flash`，三个独立 SDK 实际完成：Run `m6native-14e9f8921f3f4cb8b1bb6a0fac9f139b`、Provider `1e39460e-cccf-4da1-a64e-24aaf586e863`，3/3 Step VERIFIED，Run COMPLETED，外部效果恰好 1。该真实模型 Run 的 commit 早于最后一个只读模型 Prompt 溯源调整，最终源码的原生确定性完整 CI 已通过，不把该 Run 虚构成最终 Head 的第二次远端模型调用。
5. 实际物理 Worker 终止恢复：Run `m6recover-4c491fc1cb4546d680935d8d5345d759`、同 Provider `83d0e0af-0e27-4e6c-bfa7-c2a1ec93dbe9`；Worker A PID21 接收 SIGKILL (-9)，独立 Worker B PID68 执行原 Hatchet Task 恢复；同 Run/Provider，三 Step 各 1 Attempt，外部效果一次。恢复负例初期暴露重复 Input 请求阻断，限制性修复仅允许同 Principal/RequestDigest 的幂等读取，跨 Scope 或已更改请求仍拒绝。
6. 非幂等写入通过原 M4 ToolReceiptJournal 执行真实**独立测试 PostgreSQL** COMMIT、UNKNOWN→唯一可信账本 Receipt 对账；未确认或错误 Attempt 的写入不得被作为验证完成。不存在自行构建第二套任务调度、领域 Run/Step 状态权威或另一套 Receipt 账本。

## 限定边界与 P0/P1 非本阶段事项

- 本次 Artifact 的真实字节/hash 验证是在单独 PostgreSQL 合成测试夹具，`oss://synthetic-m6/…` 只是 **合成 ArtifactRef**；不代表企业 OSS 真链路已经测试或上线。
- Tool Receipt 真实 COMMIT 到独立合成 PG 账本，不是企业 Git/OSS 的非幂等写；M5 已单独验过真实 Cube Guest 操作和 Fencing，M6 不重复建设 Cube Provider 或新的 Tool Runtime。
- 企业 IdP/IAM、OSS/签名、跨宿主恢复、生产容量/安全/回退属于既有外部 Owner 和 M9 生产准入；生产 **NO-GO**。
- 不引入 PDLC 业务实现；M8 真实消费者接入仍独立保持 PLANNED。

## 复盘

根因：此前 M6 只有 OpenSpec 规划，原 Inspector 双 Agent 不满足三 Agent 工作流；第一次 PG 代码错误建立了平行 Run/Step 权威，已改成 Canonical PgFacts 上的 Recipe 元数据。Hatchet native durable event 第一次缺少 Scope 参数，按 SDK 合同修复。故障恢复时 Worker B 能收到原 Task，但 Domain 拒绝同一输入的重放，已修改为严格幂等且保留拒绝/版本冻结语义。CI 将真实三 SDK/审批正反/实际 Worker Kill/B 接管列为同一阶段门禁，不能用 SKIPPED 或仅模拟数据库替代。