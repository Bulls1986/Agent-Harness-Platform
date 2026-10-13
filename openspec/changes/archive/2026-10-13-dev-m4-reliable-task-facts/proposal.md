# Proposal · DEV-M4 持久一致性、Receipt 与任务级恢复

## Why

正式开发阶段需要单独的实施与验收合同，历史技术可行性证据不能冒充生产级集成结果。总里程碑见 [正式研发计划](../../../../docs/DEVELOPMENT_MILESTONES.md)。

## What Changes

PG transactional Outbox/Inbox、Provider 查询/ACK-loss Reconciliation、Tool Intent/Receipt/UNKNOWN、故障注入后的任务级恢复；不能以跨库 2PC 或自行重建 Scheduler 解决。

## Deliverable

真实 PG/Hatchet 和非幂等工具在丢 ACK/SIGKILL/并发重试下可核对且不盲目重复副作用。

## Dependencies / traceability

DEV-M3 Domain/Segment；HC-02；任务编号：DEV-HC-02 / HC-02。严格遵守已冻结的 ADR/HC-01/02/03 和 G01–G20。范围不得扩大为第二套 Hatchet 技术执行引擎。

## Non-goals

本阶段只处理上述交付；不因独立技术演示通过认定整个平台 Production GO。企业 IAM、备份、MCP 治理等外部能力不在 Harness 内重建。

## Status

**CLOSED · 原始 DEV-M4/DEV-HC-02 限定范围；以本归档 PR 最新 Head CI PASS + 主干合并生效。** 已有真实 Hatchet Worker A OS SIGKILL→独立 B 原生接管、三独立 PG 非幂等 Tool UNKNOWN→唯一外部回执、稳定 Outbox/ACK-loss Lookup 与持久 Provider Observation Inbox 去重/乱序保护。这里不代表完整通用 ToolRuntime、跨宿主/真实 Cube/M9 Production GO；详见 docs/retrospectives/DEV_M4_FINAL_CLOSEOUT_20261013.md。