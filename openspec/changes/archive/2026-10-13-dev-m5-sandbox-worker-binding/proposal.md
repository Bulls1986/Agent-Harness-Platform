# Proposal · DEV-M5 Cube 可信执行与 Coding Runtime

## Why

正式开发阶段需要单独的实施与验收合同，历史技术可行性证据不能冒充生产级集成结果。总里程碑见 [正式研发计划](../../../docs/DEVELOPMENT_MILESTONES.md)。

## What Changes

SandboxProvider→Cube Scope/Lease/Fencing/WorkspaceRef 绑定、按需分配释放和 OpenCode Coding Guest；模型-only 0 Sandbox，禁止 Host Shell 兜底。

## Deliverable

真实 Worker A→B 可信重连同 Workspace；跨 Scope 和旧 Owner 被拒，Shell/Git 仅在 Cube。

## Dependencies / traceability

HC-03 已冻结；DEV-M3/4 联合接管用例；任务编号：DEV-HC-03 / HC-03。严格遵守已冻结的 ADR/HC-01/02/03 和 G01–G20。范围不得扩大为第二套 Hatchet 技术执行引擎。

## Non-goals

本阶段只处理上述交付；不因独立技术演示通过认定整个平台 Production GO。企业 IAM、备份、MCP 治理等外部能力不在 Harness 内重建。

## Status

**CLOSED（2026-10-13 原始有界平台合同）**。真实 PG + Native Cube MicroVM + Hatchet A SIGKILL→B + 同 Workspace + Coding Guest Shell/Git 通过本地实机；PG/Native SDK/架构官方 CI PASS。最终报告：`docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md`。跨宿主和 Guest in-flight Fencing、完整 OpenCode Agent loop **NOT TESTED**，生产 **NO-GO**。
