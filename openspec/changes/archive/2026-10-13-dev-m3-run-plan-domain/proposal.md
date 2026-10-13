# Proposal · DEV-M3 领域内核与 Workflow 映射

## Why

正式开发阶段需要单独的实施与验收合同，历史技术可行性证据不能冒充生产级集成结果。总里程碑见 [正式研发计划](../../../docs/DEVELOPMENT_MILESTONES.md)。

## What Changes

Run/Plan/Step/Attempt 领域事实与状态机、Plan 版本、Replan 新 Segment、Workflow ID Binding，不重写 Hatchet DAG/Queue。

## Deliverable

一条真实 Hatchet Run 经 Replan 生成 v2 Plan/独立 Segment，旧 Attempt 不得继续完成。

## Dependencies / traceability

DEV-M1/M2 现有 Run 闭环；HC-01；任务编号：DEV-HC-01 / HC-01。严格遵守已冻结的 ADR/HC-01/02/03 和 G01–G20。范围不得扩大为第二套 Hatchet 技术执行引擎。

## Non-goals

本阶段只处理上述交付；不因独立技术演示通过认定整个平台 Production GO。企业 IAM、备份、MCP 治理等外部能力不在 Harness 内重建。

## Status

**CLOSED · 2026-10-13，原始 DEV-M3 交付范围。** 实际 Hatchet v1→v2 新 Segment、旧 Attempt 拒绝和领域事实均已有主干代码、官方实机 CI 与归档证据。生产 GO 与 M4/M5 通用可靠性仍开放。