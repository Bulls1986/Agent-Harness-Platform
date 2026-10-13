# Proposal · DEV-M7 统一 API、Chat 与用户交互

## Why

正式开发阶段需要单独的实施与验收合同，历史技术可行性证据不能冒充生产级集成结果。总里程碑见 [正式研发计划](../../../docs/DEVELOPMENT_MILESTONES.md)。

## What Changes

统一 Conversation/Turn/Run、文件引用、Typed SSE、Run/Agent/Recipe 选择、项目与授权上下文输入和用户能看懂的执行结果；Inspector 仅调试，企业 IAM 仍外部。

## Deliverable

在已授权的 API/旧 UI 接入中稳定浏览历史、模型/工具结果和 Artifact/审核，跨用户和跨项目访问拒绝。

## Dependencies / traceability

DEV-M2 Typed SSE 和 DEV-M3 Run/Plan/Step 领域归属事实是平台内部依赖；可信身份/权限由外部 Gateway/IAM Adapter 输入。M7 接口实现可与 DEV-M4/M5/M6 适用切片并行；DEV-M8 的合成消费者验证依赖 **M7 的版本化公共 API**，不是反向前置。任务编号统一为 DEV-API-01；无需任何特定业务消费者先交付。严格遵守已冻结的 ADR/HC-01/02/03 和 G01–G20。范围不得扩大为第二套 Hatchet 技术执行引擎。

## Non-goals

本阶段只处理上述交付；不因独立技术演示通过认定整个平台 Production GO。企业 IAM、备份、MCP 治理等外部能力不在 Harness 内重建。

## Status

**CLOSED（2026-10-13 原始平台合同限定交付）**。Harness 侧真实 PG/Hatchet/SDK/授权 API/Typed SSE/ArtifactRef/只读结果页经正式 CI 验证，并以 `docs/retrospectives/DEV_M7_FINAL_CLOSEOUT_20261013.md` 记录边界与已知未验证的外部验收。企业 IAM、OSS 签名、真实 Tool/审批来源及生产旧 Portal **NOT VERIFIED**；其真实集成属于原 M6/M8/M9 及外部服务职责；Platform Production **NO-GO**。完整平台上线不因本阶段限定交付而批准。
