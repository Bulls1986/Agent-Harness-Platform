# Proposal · DEV-M6 多 Agent Recipe 与审批验证

## Why

正式开发阶段需要单独的实施与验收合同，历史技术可行性证据不能冒充生产级集成结果。总里程碑见 [正式研发计划](../../../docs/DEVELOPMENT_MILESTONES.md)。

## What Changes

Recipe/Plan JSON/YAML 版本、跨 SDK A→B→C、Artifact/Evidence 引用、验证失败阻断、WAITING_APPROVAL/INPUT 及任务级恢复；不开发完整 BPMN。

## Deliverable

基于合成任务的通用规划→Coding→验证三 Agent 跨 SDK 串联，后继只接收已验证结果，审批前工具不可执行，失败可在任务级恢复；不依赖任何特定外部应用。

## Dependencies / traceability

DEV-M3/M4/M5 适用的真实 Domain/Receipt/Cube Gate；任务编号：DEV-RECIPE-01（遵循 HC-01/02/03）；独立于外部业务消费者开发或迁移。严格遵守已冻结的 ADR/HC-01/02/03 和 G01–G20。范围不得扩大为第二套 Hatchet 技术执行引擎。

## Non-goals

本阶段只处理上述交付；不因独立技术演示通过认定整个平台 Production GO。企业 IAM、备份、MCP 治理等外部能力不在 Harness 内重建。

## Status

**CLOSED（2026-10-14，原始有界合成 Recipe）**：真实 Hatchet/三 Agent SDK、独立 PG 字节及 Receipt、WAITING_INPUT/审批、真实 Worker SIGKILL A→B、官方 CI/架构 PASS；不代表企业 OSS/IAM 或 M9 Production GO。验收：[正式收口](../../../docs/retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md)。最终归档 Head CI 仍为合并前置。