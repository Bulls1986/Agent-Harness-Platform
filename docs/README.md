# 文档导航 / 单一现行入口

> **2026-10-10 更新：根目录 [README 总体架构设计](../README.md) 是当前唯一可直接阅读的完整方案。** 本页仅作专题索引，不另设一份与 README 竞争的总体方案；Accepted Contract 仍在规范优先级上高于候选设计，历史证据原样保留。

## 现在该读什么

| 目的 | 权威入口 | 状态 |
|---|---|---|
| **总体架构、建设必要性、方案优劣势、真实 POC 证据与路线图** | **[根目录 README：架构设计方案](../README.md)** | **现行总入口：集成 POC LIMITED GO / 生产 NO-GO** |
| **替换现有 OpenCode PDLC、保留存量能力及用户无感迁移** | [PDLC 替换与迁移方案](references/PDLC_REPLACEMENT_MIGRATION_20261010.md) | **业务目标已确认、迁移实码盘点未完成** |
| 当前多 Harness 目标架构与分层 | [多 Harness 目标架构候选](references/MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md) | **CANDIDATE，不是 Accepted ADR** |
| 本轮技术准入 / GO-NO GO 和证据 | [准入评估](references/MULTI_HARNESS_ADMISSION_20261009.md) | POC 分级准入 |
| **已验证技术版本 / 可兼容 SDK 组合 / OCI Digest / Cube Template** | [2026-10-10 实测版本基线](references/VERIFIED_STACK_BASELINE_20261010.md) | **POC 锁定版本，生产未 Accepted** |
| 唯一架构待办主清单 | [ARCHITECTURE_BACKLOG](ARCHITECTURE_BACKLOG.md)（024～028） | OPEN |
| 平台既有架构总设计 | [ARCHITECTURE](ARCHITECTURE.md) | V1.0 及其 Accepted Contract 不被 POC 候选覆盖 |
| POC 硬门禁、方案 A/C 历史范围 | [POC](POC.md) | 历史基线 + 新候选补充 |
| 最短运行验证脚本清单 | [poc/README](../poc/README.md) | 按 offline / Cube native / E2B native 区分 |

## 正式 Contracts（优先于候选）

沿用既有领域模型、失败/副作用、Workspace/Git、Sandbox、执行租约、安全/恢复、Typed Events 等 Accepted Contracts。完整目录与状态参见 [Reference 索引](references/README.md) 和 AGENTS.md 规定的优先级。**不能因为这个索引的技术排名而变更已冻结 Domain Model**。

## 各项 POC 与历史记录

- [Cube / OpenCode 2 / OpenAI Agents SDK](../poc/opencode_sandbox/README.md)：真实 Cube OpenCode V2 / Git / SDK 接力 PASS；官方 E2B 2.40.0 + OpenAI Native 在指定 DNS/CA 下 PASS，2.53.1 405 仍为已知不兼容组合。
- [Pydantic AI Harness](../poc/pydantic_harness/README.md)：共享 Agent Run、Linux 本地工具路由 PASS；真实 Cube 的默认 E2B Backend 尚未 PASS。
- [MAF](../poc/maf/)：POC-A 归档。保留 Workflow、Recovery、协议结论，并作为可选 Runtime 比较。
- [Temporal](../poc/temporal/)：POC-C 归档。保留任务级可靠性证据，并作为可选 Durable Backend 比较。
- [架构候选与技术评估](references/README.md)：技术选型演变过程的**历史探索证据**，不能用早期“环境不可运行 / 尚无 Cube 实例”覆盖后续真机结果。

## 维护规则

1. 最新结论只更新目标架构候选与准入记录；新增开放事项只进 `ARCHITECTURE_BACKLOG.md`，其他文档链接它。
2. 测试结果必须注明 LIVE / DOCKER / OFFLINE / MOCK，以及 PASS / FAIL / BLOCKED / NOT TESTED；**Adapter PASS 不等于 Native Client PASS**。
3. 保留旧脚本和历史结果，除非经过显式依赖审计，不做大范围目录重命名、分支删除、清理真实数据。
4. 要把候选变成 Accepted，必须完成对应 ARCH-TODO 门禁，并更新正式架构及 ADR；单凭文档整理不能准入生产。
