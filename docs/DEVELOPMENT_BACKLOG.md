# Development Backlog · Agent Harness Platform

**只维护通用平台交付任务。** 项目当前处于正式开发实施阶段；[里程碑 DEV-M0～M9](DEVELOPMENT_MILESTONES.md) 是统一计划入口。业务应用独立开发，业务私有资料与迁移计划不进入本仓库。

## 主要任务

| 任务编号 | 里程碑 | 交付 | 验收状态 |
|---|---|---|---|
| DEV-HC-01 | DEV-M3 | Run/Plan/Step/Attempt、Workflow Segment/Replan v2 与旧 Attempt 保护 | **CLOSED（2026-10-13，仅原始限定交付）**：真实 Hatchet v1→v2 独立 Workflow、PG 版本化领域事实和 Provider Binding、旧 Attempt 写入拒绝已验证。PR #80/#81/#83 Main Merge；CI [38343878631](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38343878631)、[38343879325](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38343879325) SUCCESS；[正式验收](retrospectives/DEV_M3_FINAL_CLOSEOUT_20261013.md)。通用 Retry/ToolRuntime 和 Cube Worker 接管继续归 M4/M5。|
| DEV-HC-02 | DEV-M4 | Outbox/Inbox、丢 ACK 对账、非幂等 Tool Receipt UNKNOWN | **CLOSED（原始限定交付）**：原 A.1～A.4 的 Native ACK-loss、独立外部账本实际 Commit→SIGKILL、Hatchet Worker A→B Native Retry + PG Owner Fencing 均有真实官方 CI；追加可信 Native Provider Observation Inbox/单调去重/终态拒绝并纳入原物理 Worker 联合门禁。阶段只要求未知副作用不得盲重放，不宣布通用 ToolRuntime 或 M9 Production GO；[正式收口](retrospectives/DEV_M4_FINAL_CLOSEOUT_20261013.md)。|
| DEV-HC-03 | DEV-M5 | ExecutionContext、Cube Scope/Lease/Fencing/WorkspaceRef、Worker A→B 安全接管 | PR #74 PG ACK-loss 合同 PASS；**2026-10-12 真 Cube Native MicroVM 创建/Guest Files/同 ID 重连/Destroy Smoke PASS**；真实 PG + Worker B + Cube 联合 Gate、OCI/Guest 隔离仍 OPEN |
| DEV-RECIPE-01 | DEV-M6 | Provider-neutral Recipe、Artifact/Evidence、Verifier 与 Approval | PLANNED |
| DEV-API-01 | DEV-M7 | 稳定公共 Run/Conversation/SSE/Cancel/ArtifactRef API/SDK 与服务身份合同 | **ACTIVE**：PR #65 授权只读与 #67 真 PG Run 归属已 PASS；2026-10-13 增加原范围版本化 /api/v1、真实 PG Conversation/Turn→Run、授权 SSE/游标/逐批撤权、ArtifactRef 元数据和可读只读 UI、持久取消请求的组合验收切片（最新 Head 官方 PG CI 待验证）。真实企业 Gateway/IdP、统一入口发起真实 Agent Run、OSS 下载/旧 UI Live Gate 仍 OPEN；Production NO-GO。|
| DEV-CONSUMER-01 | DEV-M8 | 只使用**合成数据**的独立客户端与平台公共 API 联调 | PLANNED |
| DEV-OPERATIONS-01 | DEV-M9 | 容量/中断/安全/运维/回退 GO/NO-GO | PLANNED |

HC-01：[Workflow Mapping](references/HATCHET_WORKFLOW_MAPPING_CONTRACT_20261010.md) · HC-02：[Consistency](references/HARNESS_HATCHET_CONSISTENCY_CONTRACT_20261010.md) · HC-03：[Trusted Sandbox](references/HATCHET_WORKER_SANDBOX_BINDING_CONTRACT_20261010.md)。

## 已完成开发切片

最小 Docker PG/Hatchet/双 SDK Run 和真实 LiteLLM Responses、SSE/持久游标/取消已有真实测试与 CI 证据；DEV-M7 的独立授权只读单测切片已由 PR #65 合并；PG 归属/不可变性子切片有独立真实 CI 证据（PR #67）。详见归档 OpenSpec、各开发复盘。这不等于生产准入：M3 限定 Replan 已关闭；通用 Task/Receipt 恢复（M4）、Approval（M6）、Cube Worker 可信重连（M5）与 M7 Gateway/PG/授权 SSE 仍 OPEN。

## 仓库保密边界

本公开仓库**禁止包含**任何业务消费者的私有源码、数据库 Schema、实际系统地址、内部 API/资产清单、迁移报告和身份数据。业务消费者通过版本化公共 API/SDK 单向依赖 Harness；与具体应用相关的工作只存在于其独立私有工程。