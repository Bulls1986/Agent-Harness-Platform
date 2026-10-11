# Proposal · DEV-M8 现有 PDLC 迁移

## Why

正式开发阶段需要单独的实施与验收合同，历史技术可行性证据不能冒充生产级集成结果。总里程碑见 [正式研发计划](../../../docs/DEVELOPMENT_MILESTONES.md)。

## What Changes

PDLC-M0 真源码/现网只读盘点→M1 兼容 Facade→M2 Single Writer 影子/灰度→M3 真实 PDLC Recipe→M4 分批切流/回退。保留 OpenCode Coding 和旧会话策略。

## Deliverable

旧 UI/SSO/项目/历史 Session/Agent/Skill/MCP/权限不退化，新增跨专业 Agent 可用、可回退。

## Dependencies / traceability

PDLC-M0 可先启动，后续依赖 M4/M6/M7；任务编号：DEV-PDLC-01～05；PDLC-M0～M4。严格遵守已冻结的 ADR/HC-01/02/03 和 G01–G20。范围不得扩大为第二套 Hatchet 技术执行引擎。

## Non-goals

本阶段只处理上述交付；不因独立技术演示通过认定整个平台 Production GO。企业 IAM、备份、MCP 治理等外部能力不在 Harness 内重建。

## Status

**PLANNED · 只有规划产物，全部实现/真实验收 Tasks 尚未启动。**