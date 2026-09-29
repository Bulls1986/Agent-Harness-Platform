# Agent Harness Platform

企业级、厂商无关的 Agent Harness Platform 架构与 POC 项目。

核心目标是将 **Control Plane（控制平面）** 与 **Data Plane（执行平面）** 解耦，通过稳定协议和可插拔组件承载 Plan、Execute、Verify、Replan、Sandbox、Artifact、Approval、Durable Execution 与多模型/多 Runtime。

## 文档

- [企业级 Agent Harness Platform 架构设计 V1.0](docs/ARCHITECTURE.md)
- [Agent Harness Platform 架构 POC 说明书 V1.0](docs/POC.md)

## 首轮 POC

首轮验证三条路线，当前 POC 优先级为：

1. Microsoft Agent Framework（MAF）
2. Temporal + 可替换 Agent Runtime
3. Google ADK

本轮不把 Java 原生支持作为评分项。

LangGraph / Deep Agents 因企业生产部署平台绑定与 Managed Feature Cliff 风险，不进入本轮 POC。

## 架构原则

- 厂商无关，Framework / Model / Sandbox / Tool 通过 Adapter / SPI 接入。
- Control Plane 决定“做什么、谁来做、失败后怎么办”；Data Plane 只负责真实执行。
- 状态迁移由确定性代码控制，LLM 负责需要智能判断的部分。
- Event 是系统事实，可用于 UI Streaming、审计、Replay 与恢复。
- 部署独立性、数据独立性、协议独立性是一级架构门禁。
- Coding Execution 视为独立重资源区，生产默认进入隔离 Sandbox，不在 Agent Runtime 宿主机裸跑。
- 执行容量采用 Local Sandbox baseline + Remote burst；当前本地第一候选为 CubeSandbox，E2B Cloud 作为弹性候选。
- Local/Remote 环境通过 Environment Registry + immutable OCI digest 维持可验证的一致性。


## 设计讨论参考

架构形成过程中的讨论记录、候选方案分析和背景资料统一归档在：

- [docs/references/README.md](docs/references/README.md)

本轮新增的执行平面专题：

- [Coding Execution / Sandbox 架构](docs/references/EXECUTION_SANDBOX_ARCHITECTURE.md)
- [Coding Execution 容量模型与调度](docs/references/EXECUTION_CAPACITY_AND_SCHEDULING.md)
- [Local / Remote Sandbox 环境一致性](docs/references/ENVIRONMENT_CONSISTENCY.md)
- [CubeSandbox 候选评估](docs/references/CUBESANDBOX_ASSESSMENT.md)

这些内容用于保留设计上下文和被否决方案，正式架构决策仍以 `docs/ARCHITECTURE.md`、`docs/POC.md` 和后续 ADR 为准。
