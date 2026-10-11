# Proposal · DEV-M6 多 Agent Recipe 与审批验证

## Why

正式开发阶段需要单独的实施与验收合同，历史技术可行性证据不能冒充生产级集成结果。总里程碑见 [正式研发计划](../../../docs/DEVELOPMENT_MILESTONES.md)。

## What Changes

Recipe/Plan JSON/YAML 版本、跨 SDK A→B→C、Artifact/Evidence 引用、验证失败阻断、WAITING_APPROVAL/INPUT 及任务级恢复；不开发完整 BPMN。

## Deliverable

真实 PDLC 需求→Coding→测试串联，后继只接收已验证结果，审批前工具不可执行，失败可恢复。

## Dependencies / traceability

DEV-M3/M4/M5 相关真实 Gate；任务编号：HC-01/02/03 + DEV-PDLC-04。严格遵守已冻结的 ADR/HC-01/02/03 和 G01–G20。范围不得扩大为第二套 Hatchet 技术执行引擎。

## Non-goals

本阶段只处理上述交付；不因独立技术演示通过认定整个平台 Production GO。企业 IAM、备份、MCP 治理等外部能力不在 Harness 内重建。

## Status

**PLANNED · 只有规划产物，全部实现/真实验收 Tasks 尚未启动。**