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

**ACTIVE · 2026-10-13 原始退出条件已逐项核对，仍有外部真实联调阻断，暂不可归档。** 公共 API 现在已具备真实 PG Conversation/Turn/Run、版本化 REST、可信注入授权与撤权、SSE Cursor、ArtifactRef 元数据、Native Hatchet 双 SDK 实际执行和本地 Inspector 演示。PR #65/#67/#86/#88/#90 官方真实 CI 已有合格证据；本轮加强 Tool/Approval/Artifact 只读事件可读性与超过 250 个事件的安全分页，真实 PG TDD Red→Green。

**尚无足以关闭原 M7 的证据**：外部企业 Gateway/Policy 身份真实联调、实际存储对象与 Tool/审批事件来源贯通已授权用户客户端的端到端呈现。外部 IAM、OSS 及 M6 Approval 引擎仍不是本平台要重建的能力；缺少外部服务/验收条件时，不把合成身份/事件、开发调试 Inspector 或 M8 合成消费者假冒成真实企业接入。

参见 [DEV-M7 固定范围 Gate 最终审计](../../../docs/retrospectives/DEV_M7_ORIGINAL_GATE_CLOSEOUT_AUDIT_20261013.md)。阶段继续 `ACTIVE`，Production `NO-GO`。
