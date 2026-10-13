# Development Backlog · Agent Harness Platform

**只维护通用平台交付任务。** 项目当前处于正式开发实施阶段；[里程碑 DEV-M0～M9](DEVELOPMENT_MILESTONES.md) 是统一计划入口。业务应用独立开发，业务私有资料与迁移计划不进入本仓库。

## 主要任务

| 任务编号 | 里程碑 | 交付 | 验收状态 |
|---|---|---|---|
| DEV-HC-01 | DEV-M3 | Run/Plan/Step/Attempt、Workflow Segment/Replan v2 与旧 Attempt 保护 | Plan v1 + PURE 真实 Hatchet v1→v2 独立 Segment PASS；2026-10-13 追加真实 PG 取消后迟到 Step 拒绝/未绑定 Provider 拒绝切片 15/15 PASS（见 M3 复盘）；追加模型-only Plan v1 独立 PG Attempt ID、重复派发/旧 Attempt 提交拒绝 24/24 PASS（PR #81 最新 Head 真实 Hatchet/PG、M4/M5、架构四条 CI 均 PASS，已合并 main）；追加 A.5 候选：v2 Step/Attempt/业务终态、确认外部 Receipt 的显式非 PURE Replan、旧 PURE Attempt SUPERSEDED/取消绑定竞态，43 项真实 PG 合同 PASS（最新 Head 真实 Hatchet/独立账本 CI 待验）；任意多版本/多 Attempt 安全重试、跨 Worker Owner Epoch/真实 Cancel/TERMINATED 与完整领域 Gate OPEN |
| DEV-HC-02 | DEV-M4 | Outbox/Inbox、丢 ACK 对账、非幂等 Tool Receipt UNKNOWN | ACTIVE：实际 Hatchet Worker A 进程 SIGKILL→独立 B Native 接管、PG Receipt/Owner Fencing PASS（PR #72）；通用 ToolRuntime/Inbox/跨宿主 Gate OPEN |
| DEV-HC-03 | DEV-M5 | ExecutionContext、Cube Scope/Lease/Fencing/WorkspaceRef、Worker A→B 安全接管 | PR #74 PG ACK-loss 合同 PASS；**2026-10-12 真 Cube Native MicroVM 创建/Guest Files/同 ID 重连/Destroy Smoke PASS**；真实 PG + Worker B + Cube 联合 Gate、OCI/Guest 隔离仍 OPEN |
| DEV-RECIPE-01 | DEV-M6 | Provider-neutral Recipe、Artifact/Evidence、Verifier 与 Approval | PLANNED |
| DEV-API-01 | DEV-M7 | 稳定公共 Run/Conversation/SSE/Cancel/ArtifactRef API/SDK 与服务身份合同 | ACTIVE：PR #65 授权读取与 PR #67 PG 归属/不可变性集成子切片 PASS；真实 IAM/Policy+PG、SSE/Artifact/UI Gate OPEN |
| DEV-CONSUMER-01 | DEV-M8 | 只使用**合成数据**的独立客户端与平台公共 API 联调 | PLANNED |
| DEV-OPERATIONS-01 | DEV-M9 | 容量/中断/安全/运维/回退 GO/NO-GO | PLANNED |

HC-01：[Workflow Mapping](references/HATCHET_WORKFLOW_MAPPING_CONTRACT_20261010.md) · HC-02：[Consistency](references/HARNESS_HATCHET_CONSISTENCY_CONTRACT_20261010.md) · HC-03：[Trusted Sandbox](references/HATCHET_WORKER_SANDBOX_BINDING_CONTRACT_20261010.md)。

## 已完成开发切片

最小 Docker PG/Hatchet/双 SDK Run 和真实 LiteLLM Responses、SSE/持久游标/取消已有真实测试与 CI 证据；DEV-M7 的独立授权只读单测切片已由 PR #65 合并；PG 归属/不可变性子切片有独立真实 CI 证据（PR #67）。详见归档 OpenSpec、各开发复盘。这不等于生产准入，完整 Replan、Receipt/Approval、Cube Worker 可信重连以及 M7 正式 Gateway/PG/授权 SSE 仍 OPEN。

## 仓库保密边界

本公开仓库**禁止包含**任何业务消费者的私有源码、数据库 Schema、实际系统地址、内部 API/资产清单、迁移报告和身份数据。业务消费者通过版本化公共 API/SDK 单向依赖 Harness；与具体应用相关的工作只存在于其独立私有工程。