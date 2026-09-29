# Artifact / Evidence / Log Retention 契约

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-011

## 1. 核心定位

本契约定义任务完成前后 Artifact、Evidence、Raw Log、Trace 与恢复依赖的保留边界。

核心原则：

> 任务事实（Fact / Metadata）与载荷（Payload）分离。平台数据库保存可审计事实、Lineage 与对象引用；文件、报告、截图、大日志等 Payload 默认进入对象存储（OSS / Object Storage）。

本契约不建设对象存储产品、日志平台或合规 Legal Hold 系统。

## 2. 存储分层

推荐 V1 分层：

~~~text
PostgreSQL / Platform State Store
→ Artifact / Evidence metadata
→ lineage
→ verification result
→ retention metadata
→ storage reference

OSS / Object Storage
→ generated files
→ reports
→ screenshots
→ test artifacts
→ large evidence payload
→ raw logs / trace payload when retained
~~~

Object Storage 可以是企业现有 OSS、S3-compatible、MinIO 或其他 Provider；Harness 只依赖 ObjectStorage / ArtifactStore Adapter，不绑定具体厂商。

## 3. Artifact 与 Evidence

Artifact 表示任务产物；Evidence 表示支撑某个判断、Verification 或审计结论的证据。

两者是逻辑身份，不等同于物理文件。

建议最小 metadata：

~~~text
Artifact / Evidence
├─ id
├─ run_id
├─ step_id?
├─ attempt_id?
├─ execution_id?
├─ type
├─ media_type?
├─ content_digest
├─ size?
├─ storage_ref?
├─ retention_policy_ref?
├─ payload_status
├─ created_at
└─ purged_at?
~~~

payload_status 至少支持 AVAILABLE / PURGED。

## 4. Payload Store

所有需要持久保存的二进制或大文本 Payload 默认进入 Object Storage。

典型包括：

- 生成文档；
- build/test report；
- screenshot / browser evidence；
- code diff / patch bundle；
- exported trace / diagnostic bundle；
- large tool output；
- promoted evidence payload。

平台数据库不应直接承担大对象存储职责。

允许小型结构化 Evidence 直接作为数据库字段保存，但不得因此改变 Artifact / Evidence 的逻辑模型。

## 5. Raw Log / Trace

Raw Log / Trace 默认属于短期诊断数据，不自动升级为长期 Evidence。

~~~text
Raw Log / Trace
→ diagnostic payload
→ short retention

selected / promoted portion
→ Evidence
→ evidence retention
~~~

若某段日志被 Verification、Reconciliation 或 Audit 明确引用，应形成独立 Evidence 或 Evidence reference，而不是依赖整份 raw log 永久存在。

## 6. Metadata 与 Payload 生命周期分离

Payload 可以按 Retention Policy 删除，但其最小 Metadata / Tombstone 必须保留，使历史 Lineage 仍可解释。

删除后：

~~~text
payload_status = PURGED
storage_ref = null / tombstoned
content_digest retained
lineage retained
purged_at retained
~~~

因此即使二进制文件已经清理，平台仍然能够回答：

- 该 Artifact / Evidence 曾经存在；
- 由哪个 Run / Execution 产生；
- 被哪个 Verification / Reconciliation 使用；
- 当时的 digest / type / size；
- 何时被清理。

## 7. Recovery Pin

只要某个 Run 仍处于可恢复状态，其恢复所依赖的对象不得被 GC。

例如：

- runtime checkpoint reference；
- workspace state reference；
- required Artifact / Evidence；
- SideEffectReceipt；
- Reconciliation Evidence；
- 必要的 snapshot reference。

~~~text
Recoverable Run
→ referenced recovery dependency
→ PIN
→ not eligible for GC
~~~

Run 进入不可恢复终态、RecoveryPoint 失效或依赖被明确释放后，相关 Provider 才可以根据 Retention Policy 清理 Payload。

## 8. Workspace / Snapshot 边界

Workspace 生命周期仍由 Workspace Contract 管理；Sandbox Snapshot 生命周期仍由 Sandbox Provider 管理。

011 只规定：

> 如果某个有效 RecoveryPoint 仍依赖对应 Workspace State / Snapshot，则不得被 GC。

不在本契约中重新实现 Workspace Retention Engine 或 Snapshot Manager。

## 9. Deduplication

可以通过 content_digest 对 Object Storage 中的物理对象去重。

但必须保持：

~~~text
Logical Artifact / Evidence Identity
≠
Physical Storage Object
~~~

多个 Artifact / Evidence 可以引用同一物理对象，但各自的 run_id、execution_id、purpose、lineage 与 retention decision 仍独立存在。

## 10. Retention Policy

Harness 不硬编码固定保留天数。

平台只需要支持可配置 Retention Policy / Retention Class，例如：

- SHORT；
- STANDARD；
- LONG；
- PRESERVE；
- external retention_policy_ref。

具体 7/30/90/180 天或永久保留，由部署环境、项目 Policy 或企业合规策略决定。

V1 不建设完整 Legal Hold / eDiscovery 系统；最多允许外部 Policy 将对象标记为不可清理。

## 11. Task Facts

以下内容属于任务执行事实，不应因为 Payload GC 一并删除：

- Run / Plan / Step / Attempt / Execution 状态；
- Verification Result；
- Approval Decision；
- SideEffectReceipt；
- Reconciliation Result；
- Artifact / Evidence metadata 与 lineage；
- final Runtime Topology snapshot / key lifecycle events（按其独立 retention policy）。

这些事实的最终保留周期由平台 Policy 决定，但逻辑上与大对象 Payload 生命周期分离。

## 11.1 Observability Retention Boundary

Observability 产生的 Trace / Log 默认属于诊断数据，其 schema、correlation 与 sampling 由 OBSERVABILITY_CONTRACT.md 定义；本契约只负责其 Payload 保留与 GC 边界。

如果某段 Trace / Log 内容被 Verification、Reconciliation 或 Audit 明确作为长期依据，应提升为 Evidence 或形成稳定 Evidence Reference，再按 Evidence Retention 处理。

## 12. 不在本契约范围

- Object Storage 产品选型与底层副本机制；
- PostgreSQL / Object Storage Backup / DR；
- Workspace 生命周期策略本身；
- Sandbox Snapshot 实现与 GC 算法；
- 通用日志平台 / SIEM；
- 完整 Legal Hold / eDiscovery；
- DLP / PII；
- Observability schema（由 OBSERVABILITY_CONTRACT.md 定义）。

## 13. Accepted Rules

1. Task Facts 与 Payload 分离；删除 Payload 不得删除任务历史和 Lineage。
2. Artifact / Evidence 的文件、报告、截图及其他大 Payload 默认保存到 OSS / Object Storage；数据库只保存 metadata、lineage 与 storage reference。
3. Raw Log / Trace 默认短期保存；只有被明确提升或引用的内容进入 Evidence 生命周期。
4. Artifact / Evidence 是逻辑身份，物理对象可以按 content_digest 去重，但不能合并逻辑 Lineage。
5. Recoverable Run 所依赖的 checkpoint、workspace state、evidence、snapshot reference 等必须 PIN，不能被 GC。
6. Workspace / Sandbox Snapshot 生命周期由其对应 Provider/Contract 管理，011 只定义引用与 GC 约束。
7. Retention 时长由 Policy / 部署配置决定，Harness Kernel 不硬编码具体天数。
8. Payload 清理后保留最小 Metadata/Tombstone，使历史 Verification、Recovery 与 Audit 仍可解释。
9. Object Storage 是 Artifact/Evidence Payload Store，不替代平台数据库中的任务事实与 Lineage。