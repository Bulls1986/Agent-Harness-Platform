# Proposal · DEV-M7 统一 API、Chat 与用户交互

## Why

正式开发阶段需要单独的实施与验收合同，历史技术可行性证据不能冒充生产级集成结果。总里程碑见 [正式研发计划](../../../docs/DEVELOPMENT_MILESTONES.md)。

## What Changes

统一 Conversation/Turn/Run、文件引用、Typed SSE、Run/Agent/Recipe 选择、项目与授权上下文输入和用户能看懂的执行结果；Inspector 仅调试，企业 IAM 仍外部。

## Deliverable

在已授权的 API/旧 UI 接入中稳定浏览历史、模型/工具结果和 Artifact/审核，跨用户和跨项目访问拒绝。

## Dependencies / traceability

DEV-M2 Typed SSE 和 M3 领域事实；可与 M5/M6 并行；任务编号：Conversation/Turn/Run 接口；DEV-CONSUMER-02 前置。严格遵守已冻结的 ADR/HC-01/02/03 和 G01–G20。范围不得扩大为第二套 Hatchet 技术执行引擎。

## Non-goals

本阶段只处理上述交付；不因独立技术演示通过认定整个平台 Production GO。企业 IAM、备份、MCP 治理等外部能力不在 Harness 内重建。

## Status

**PLANNED · 只有规划产物，全部实现/真实验收 Tasks 尚未启动。**