# 文档导航 / 单一现行入口

> 2026-10-09 整理。**本页是导航，不是新增架构 Contract。** 不修改已接受的 ADR/Contract；历史 POC 结果按原路径保留，避免破坏 Git 历史和引用。

## 现在该读什么

| 目的 | 权威入口 | 状态 |
|---|---|---|
| 当前多 Harness 目标架构与分层 | [多 Harness 目标架构候选](references/MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md) | **CANDIDATE，不是 Accepted ADR** |
| 本轮技术准入 / GO-NO GO 和证据 | [准入评估](references/MULTI_HARNESS_ADMISSION_20261009.md) | POC 分级准入 |
| 唯一架构待办主清单 | [ARCHITECTURE_BACKLOG](ARCHITECTURE_BACKLOG.md)（024～028） | OPEN |
| 平台既有架构总设计 | [ARCHITECTURE](ARCHITECTURE.md) | V1.0 及其 Accepted Contract 不被 POC 候选覆盖 |
| POC 硬门禁、方案 A/C 历史范围 | [POC](POC.md) | 历史基线 + 新候选补充 |
| 最短运行验证脚本清单 | [poc/README](../poc/README.md) | 按 offline / Cube native / E2B native 区分 |

## 正式 Contracts（优先于候选）

沿用既有领域模型、失败/副作用、Workspace/Git、Sandbox、执行租约、安全/恢复、Typed Events 等 Accepted Contracts。完整目录与状态参见 [Reference 索引](references/README.md) 和 AGENTS.md 规定的优先级。**不能因为这个索引的技术排名而变更已冻结 Domain Model**。

## 各项 POC 与历史记录

- [Cube / OpenCode 2 / OpenAI Agents SDK](../poc/opencode_sandbox/README.md)：真实 Cube SDK PASS、E2B 原生 405、OpenCode 2 Cube 自定义模板阻塞。
- [Pydantic AI Harness](../poc/pydantic_harness/README.md)：共享 Agent Run、Linux 本地工具路由 PASS；真实 Cube 的默认 E2B Backend 尚未 PASS。
- [MAF](../poc/maf/)：POC-A 归档。保留 Workflow、Recovery、协议结论，并作为可选 Runtime 比较。
- [Temporal](../poc/temporal/)：POC-C 归档。保留任务级可靠性证据，并作为可选 Durable Backend 比较。
- [架构候选与技术评估](references/README.md)：技术选型演变过程的**历史探索证据**，不能用早期“环境不可运行 / 尚无 Cube 实例”覆盖后续真机结果。

## 维护规则

1. 最新结论只更新目标架构候选与准入记录；新增开放事项只进 `ARCHITECTURE_BACKLOG.md`，其他文档链接它。
2. 测试结果必须注明 LIVE / DOCKER / OFFLINE / MOCK，以及 PASS / FAIL / BLOCKED / NOT TESTED；**Adapter PASS 不等于 Native Client PASS**。
3. 保留旧脚本和历史结果，除非经过显式依赖审计，不做大范围目录重命名、分支删除、清理真实数据。
4. 要把候选变成 Accepted，必须完成对应 ARCH-TODO 门禁，并更新正式架构及 ADR；单凭文档整理不能准入生产。
