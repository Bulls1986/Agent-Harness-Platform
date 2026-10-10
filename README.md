# Agent Harness Platform

企业级、厂商无关的 Agent Harness Platform 架构与 POC 项目。

核心目标是将 **Control Plane（控制平面）** 与 **Data Plane（执行平面）** 解耦，通过稳定协议和可插拔组件承载 Plan、Execute、Verify、Replan、Sandbox、Artifact、Approval、Durable Execution 与多模型/多 Runtime。

## 从这里开始（统一入口）

1. [文档导航：现行候选 / Accepted Contract / 历史 POC](docs/README.md)
2. [阶段性准入结论：集成 POC GO、生产 NO-GO](docs/references/MULTI_HARNESS_ADMISSION_20261009.md)
3. [多 Harness 当前目标架构](docs/references/MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md)
4. [POC 验证脚本导航](poc/README.md)
5. [架构待办：唯一主清单](docs/ARCHITECTURE_BACKLOG.md)
6. [**已验证技术版本基线：兼容矩阵 / OCI Digest / Cube Template / 升级门禁**](docs/references/VERIFIED_STACK_BASELINE_20261010.md)

## 历史研究与专题证据（保留原路径）

- [企业级 Agent Harness Platform 架构设计 V1.0](docs/ARCHITECTURE.md)
- [Agent Harness Platform 架构 POC 说明书 V1.0](docs/POC.md)
- [POC-A / MAF 完整实施任务计划](docs/POC_A_TASK_PLAN.md)
- [POC-A / MAF 决策型最终评估（Hard Gates 与 GAP）](poc/maf/POC_A_DECISION_CLOSEOUT.md)
- [POC-C / Temporal 技术验证任务计划](docs/POC_C_TASK_PLAN.md)
- [POC-C / 首批原生 Worker 与 Server 恢复证据](poc/temporal/C00_C04_NATIVE_FINDINGS.md)
- [POC-C / C05 非 Dev Server 的 OSS Temporal + PostgreSQL 故障证据](poc/temporal/C05_OSS_POSTGRES_FINDINGS.md)
- [POC-C / C06/C07 双 PostgreSQL 非幂等派发故障与任务状态证据](poc/temporal/C06_C07_GUARDED_FINDINGS.md)
- [POC-C / C10 受限 Responses/Typed SSE 跨 HTTP 进程恢复](poc/temporal/C10_PROTOCOL_FINDINGS.md)
- [POC-C / C12 Temporal Native History Replay 与版本不兼容检测](poc/temporal/C12_REPLAY_FINDINGS.md)
- [POC-C / C09 真实双 Agent Runtime SDK（MAF / OpenAI Agents）切换](poc/temporal/C09_REAL_RUNTIME_FINDINGS.md)
- [POC-C / C11 隔离 Sandbox + S3 Artifact/Evidence 引用与 Tombstone](poc/temporal/C11_SANDBOX_ARTIFACT_FINDINGS.md)
- [POC-C / C13 原生 OpenTelemetry 与 Harness Correlation/部署依赖](poc/temporal/C13_OTEL_FINDINGS.md)
- [POC-C / C14 MAF 与 Temporal 全 Gate/场景比较与条件选型](poc/temporal/C14_COMPARATIVE_DECISION.md)
- [OpenCode + E2B/CubeSandbox + 共享 Runtime 专项 POC（在研）](poc/opencode_sandbox/README.md)
- [2026-10-09 多 Harness 目标架构候选快照与 Cube 实测矩阵（未 Accepted）](docs/references/MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md)
- [POC-A 阶段性结论与证据台账](docs/POC_A_STAGE_FINDINGS.md)
- [POC-A / A30 任务恢复覆盖矩阵](docs/POC_A_RECOVERY_MATRIX.md)
- [架构待办 / Architecture Backlog](docs/ARCHITECTURE_BACKLOG.md)

> **2026-10-10 集成准入更新：** [唯一版本基线](docs/references/VERIFIED_STACK_BASELINE_20261010.md) 已明确锁定实测组合：Cube v0.7.2、原生 SDK 0.7.0、E2B 官方 2.40.0（专用 DNS/CA）、OpenAI Agents 0.23.1、OpenCode 2.0.24、Pydantic AI Slim 2.54.0，以及通过的 Git-enabled Guest Template 和 OCI Digest。**真实 Cube / 双 Session / FS / Shell / Git / 原生 E2B/跨 SDK Tool 的基础技术路径已通过；项目进入集成 POC，仍非生产 GO**。以下 2026-10-09 状态是历史快照，不能用它否定 2026-10-10 的 E2B v2.40 Native PASS。

> **当前增量选型（2026-10-09，候选而非 Accepted）：** Pydantic AI Harness 为通用 Agent 默认 Runtime Adapter 首选；OpenCode 2 保留 Coding、OpenAI Agents SDK/MAF 保留可选 Adapter；平台自有 AgentRuntime SPI 才负责 SDK 切换，Process/Durable SPI 的 Temporal 或 PG Worker 仍待等价验证。Cube 原生 SDK 的真实 MicroVM/文件/命令/重连已通过，但 E2B 2.53.1/OpenAI 原生 E2B Client 对当前 Cube v0.7.2 的创建均返回 HTTP 405。详见上述目标架构快照与 [ARCH-TODO-025～028](docs/ARCHITECTURE_BACKLOG.md)。下文首轮 POC 优先级仅保留历史基线。

## 首轮 POC

2026-09-29 首轮验证过三条路线；以下仅为**当时的历史优先级，不是 2026-10-09 最新选型或准入结果**：

1. Microsoft Agent Framework（MAF）
2. Temporal + 可替换 Agent Runtime
3. Google ADK

本轮不把 Java 原生支持作为评分项。

首轮 POC 的判定对象是 **Harness 任务生命周期与集成边界**，不是企业治理/基础设施产品的完整复刻。核心验收聚焦 Plan → Execute → Verify → Replan、任务级持久化与恢复、HITL、协议桥接、自托管，以及 Runtime / Model / Sandbox 的解耦；IAM、MCP Governance、Cost/Quota/Billing、Secret、APM Backend、Storage Backup/DR 等只验证 Adapter / Ownership Boundary，不要求在 Harness 内实现。

LangGraph / Deep Agents 因企业生产部署平台绑定与 Managed Feature Cliff 风险，不进入本轮 POC。

## 架构原则

- 厂商无关，Framework / Model / Sandbox / Tool 通过 Adapter / SPI 接入。
- Control Plane 决定“做什么、谁来做、失败后怎么办”；Data Plane 只负责真实执行。
- 状态迁移由确定性代码控制，LLM 负责需要智能判断的部分。
- Event 是系统事实，可用于 UI Streaming、审计、Replay 与恢复。
- 部署独立性、数据独立性、协议独立性是一级架构门禁。
- Coding Execution 视为独立重资源区，生产默认进入隔离 Sandbox，不在 Agent Runtime 宿主机裸跑。
- 执行容量采用 Local CubeSandbox baseline + Remote CubeSandbox burst；E2B 仅保留为兼容 API/SDK 语义，不作为独立 Provider。
- Local/Remote 环境通过 Environment version directory / external registry reference + immutable OCI digest 维持可验证的一致性；不要求 Harness 建设中心化 Environment Registry 服务。


## 设计讨论参考

架构形成过程中的讨论记录、候选方案分析和背景资料统一归档在：

- [docs/references/README.md](docs/references/README.md)

本轮新增的执行平面专题：

- [Coding Execution / Sandbox 架构](docs/references/EXECUTION_SANDBOX_ARCHITECTURE.md)
- [Coding Execution 容量模型与调度](docs/references/EXECUTION_CAPACITY_AND_SCHEDULING.md)
- [Local / Remote Sandbox 环境一致性](docs/references/ENVIRONMENT_CONSISTENCY.md)
- [CubeSandbox 候选评估](docs/references/CUBESANDBOX_ASSESSMENT.md)

这些内容用于保留设计上下文和被否决方案，正式架构决策仍以 `docs/ARCHITECTURE.md`、`docs/POC.md` 和后续 ADR 为准。
