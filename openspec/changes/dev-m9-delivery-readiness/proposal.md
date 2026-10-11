# Proposal · DEV-M9 生产交付与运营验收

## Why

正式开发阶段需要单独的实施与验收合同，历史技术可行性证据不能冒充生产级集成结果。总里程碑见 [正式研发计划](../../../docs/DEVELOPMENT_MILESTONES.md)。

## What Changes

自托管部署 Runbook、配置/Secret 与 OTel 接入、权限安全/故障恢复/灰度回滚、100 Active Runs 真实资源与性能测量；不自建 IAM/备份平台。

## Deliverable

PDLC 等价、新 Recipe 业务和生产安全/容量三类 Gate 分别全部 PASS，才允许生产 GO。

## Dependencies / traceability

DEV-M3～M8 核心 Gate；外部 IAM/运维/安全协作；任务编号：DEV-M9 / Production GO Gate。严格遵守已冻结的 ADR/HC-01/02/03 和 G01–G20。范围不得扩大为第二套 Hatchet 技术执行引擎。

## Non-goals

本阶段只处理上述交付；不因独立技术演示通过认定整个平台 Production GO。企业 IAM、备份、MCP 治理等外部能力不在 Harness 内重建。

## Status

**PLANNED · 只有规划产物，全部实现/真实验收 Tasks 尚未启动。**