# Proposal · DEV-M4 持久一致性、Receipt 与任务级恢复

## Why

正式开发阶段需要单独的实施与验收合同，历史技术可行性证据不能冒充生产级集成结果。总里程碑见 [正式研发计划](../../../docs/DEVELOPMENT_MILESTONES.md)。

## What Changes

PG transactional Outbox/Inbox、Provider 查询/ACK-loss Reconciliation、Tool Intent/Receipt/UNKNOWN、故障注入后的任务级恢复；不能以跨库 2PC 或自行重建 Scheduler 解决。

## Deliverable

真实 PG/Hatchet 和非幂等工具在丢 ACK/SIGKILL/并发重试下可核对且不盲目重复副作用。

## Dependencies / traceability

DEV-M3 Domain/Segment；HC-02；任务编号：DEV-HC-02 / HC-02。严格遵守已冻结的 ADR/HC-01/02/03 和 G01–G20。范围不得扩大为第二套 Hatchet 技术执行引擎。

## Non-goals

本阶段只处理上述交付；不因独立技术演示通过认定整个平台 Production GO。企业 IAM、备份、MCP 治理等外部能力不在 Harness 内重建。

## Status

**ACTIVE · PURE v2 Segment ACK-loss 原生对账 + 双独立 PostgreSQL 的非幂等 Tool Intent/Receipt/SIGKILL 独立测试切片已有真实 CI 证据；完整 HC-02/DEV-M4 Gate 仍 OPEN。** 尚未实现真实 Hatchet Worker SIGKILL 后 A→B 接管、自动故障观察、泛化 Tool Runner 与 Receipt Policy、通用 Outbox/Inbox、正式 Lease/Fencing；以上未通过门禁不得宣称生产可用。