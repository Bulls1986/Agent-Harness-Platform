# 参考资料 / Discussion References

本目录用于记录 Agent Harness Platform 架构形成过程中的技术讨论、候选方案分析与背景资料。

> 这些文件是 **讨论记录 / 设计参考**，不是最终架构规范。正式决策以 `docs/ARCHITECTURE.md`、`docs/POC.md` 和后续 ADR 为准。

> **最新入口（候选状态）：** [文档导航](../README.md) → [目标架构](MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md) → [准入结论](MULTI_HARNESS_ADMISSION_20261009.md)。下列其余条目是历史背景、正式 Contract 或专项 POC 证据，读者必须看每份文件的 Status 与日期。

## 分类

1. [OpenAI Agent / Harness 能力梳理](OPENAI_AGENT_STACK.md)
2. [Harness Kernel 与可插拔组件抽象](HARNESS_COMPONENT_MODEL.md)
3. [Conversation / UI Protocol 讨论](CONVERSATION_PROTOCOL.md)
4. [框架与 Runtime 首轮技术比较](FRAMEWORK_LANDSCAPE.md)
5. [部署独立性与平台绑定风险](DEPLOYMENT_INDEPENDENCE.md)
6. [Control Plane / Data Plane 边界说明](CONTROL_DATA_PLANE.md)
7. [MAF Memory / Context 设计](MAF_MEMORY_MODEL.md)
8. [MAF 扩展性评估](MAF_EXTENSIBILITY.md)
9. [首轮方案架构匹配度估算](FIRST_ROUND_MATCH_ASSESSMENT.md)
10. [Coding Execution / Sandbox 架构](EXECUTION_SANDBOX_ARCHITECTURE.md)
11. [Coding Execution 容量模型与调度](EXECUTION_CAPACITY_AND_SCHEDULING.md)
12. [Local / Remote Sandbox 环境一致性](ENVIRONMENT_CONSISTENCY.md)
13. [CubeSandbox 作为本地 Agent Sandbox 的候选评估](CUBESANDBOX_ASSESSMENT.md)
14. [Domain Model & State Contract](DOMAIN_MODEL_AND_STATE_CONTRACT.md)
15. [失败、幂等与副作用契约](FAILURE_IDEMPOTENCY_AND_RECOVERY.md)
16. [工作空间、仓库与 Git 契约](WORKSPACE_AND_GIT_MODEL.md)
17. [运行时拓扑与参与者模型](RUNTIME_TOPOLOGY.md)
18. [Checkpoint 与恢复隔离契约](CHECKPOINT_AND_SNAPSHOT_CONSISTENCY.md)
19. [安全信任边界与隔离契约](SECURITY_THREAT_MODEL.md)
20. [Registry 与版本冻结契约](REGISTRY_AND_VERSIONING.md)
21. [MAF Python Durable 私有化部署约束](MAF_PYTHON_DURABLE_PRIVATE_DEPLOYMENT.md)
22. [Execution Lease / Fencing / Heartbeat 契约](EXECUTION_LEASE_FENCING_HEARTBEAT.md)
23. [Identity & Authorization Propagation 契约](IDENTITY_AND_AUTHORIZATION_PROPAGATION.md)
24. [Task Recovery Coverage & Recovery Semantics 契约](TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md)
25. [Artifact / Evidence / Log Retention 契约](ARTIFACT_EVIDENCE_LOG_RETENTION.md)
26. [Observability Contract](OBSERVABILITY_CONTRACT.md)
27. [Cost / Quota Ownership Boundary](COST_QUOTA_OWNERSHIP_BOUNDARY.md)
28. [Environment Supply Chain Ownership Boundary](ENVIRONMENT_SUPPLY_CHAIN_OWNERSHIP_BOUNDARY.md)
29. [MCP Trust Ownership Boundary](MCP_TRUST_OWNERSHIP_BOUNDARY.md)
30. [Cancellation / Timeout Propagation 契约](CANCELLATION_TIMEOUT_PROPAGATION.md)
31. [Harness Scope Alignment Review](HARNESS_SCOPE_ALIGNMENT_REVIEW.md)
32. [Microsoft Execution Containers（MXC）Sandbox Backend 候选评估](MXC_EXECUTION_CONTAINER_CANDIDATE.md)
33. [多 Harness 共享 Sandbox 与 Runtime 密度（2026-10-09 POC 候选，未 Accepted）](MULTI_HARNESS_SANDBOX_RUNTIME_DENSITY_CANDIDATE.md)
34. [多 Harness 技术选型增量评估（Pydantic AI Harness / OpenAI Agents SDK / Temporal / CubeSandbox）](MULTI_HARNESS_TECH_SELECTION_20261009.md)
35. [多 Harness 目标架构候选与 Cube 实测快照（2026-10-09，未 Accepted）](MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md)
36. [多 Harness 集成 POC 与生产分级准入（2026-10-09）](MULTI_HARNESS_ADMISSION_20261009.md)
37. [**已验证技术栈版本基线、E2B 兼容矩阵、Cube OCI Digest 与 Template（2026-10-10）**](VERIFIED_STACK_BASELINE_20261010.md)
38. [**现有 OpenCode PDLC 替换、已有能力无感迁移与跨 Agent 串联方案（2026-10-10）**](PDLC_REPLACEMENT_MIGRATION_20261010.md)

**架构视图：** 八类分层架构图现已[直接嵌入根目录 README（第 3.1 节）](../../README.md#31-八类分层架构视图)，旧 [ARCHITECTURE_VIEWS.md](../ARCHITECTURE_VIEWS.md) 仅提供兼容导航，不重复维护图表。

## 阶段评估处置索引

- [**架构原则与开发准入护栏（G01–G20）**](../ARCHITECTURE_GUARDRAILS.md)：Accepted Contract 对应的硬约束、PR 评审、异常恢复与 CI 静态门禁；不是新的选型 ADR。

- [POC-C C00–C16 技术评估收口与生产 NO-GO](../POC_C_EVALUATION_CLOSEOUT.md)：保留主干已合并的阶段证据，后续行动由 [ARCH-TODO-025](../ARCHITECTURE_BACKLOG.md) 管理。

## 使用原则

- 参考资料允许保留探索过程、候选方案和被否决思路。
- 正式架构文档只保留当前有效决策和接口边界。
- 任何引用到具体框架当前能力、许可证或托管方式的内容，在正式选型前必须重新核验。
- 当参考资料中的结论被 ADR 正式接受后，应在 ADR 中建立反向链接。