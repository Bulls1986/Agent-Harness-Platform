# Multica 调度设计参考与独立实现决策（2026-10-10）

> **状态：DECIDED / ADR-030（设计与源码使用边界）；非 Scheduler / Process-Durable 技术选型验收。**
> **适用范围：** Agent Harness Platform 的 ExecutionScheduler、任务生命周期、执行尝试与状态持久化。
> **参考项目：** [Multica](https://github.com/multica-ai/multica)；[许可证](https://github.com/multica-ai/multica/blob/main/LICENSE)。引用用于技术背景，不作为平台依赖或法律授权依据。

## 决策

**仅参考 Multica 的公开架构思路，由本项目独立设计、编写和验证实现；不直接使用、复制、改写、翻译、迁入或 Vendor Multica 的源代码。**

- 不 fork、不 git submodule、不添加 Multica 的包、镜像或运行时依赖；也不以抽取部分后端代码作为快捷实现方案。
- 可以研究其**思想层面**的队列领取、任务状态流转、并发控制、心跳与失联判定、Run/Attempt 记录、Daemon/Worker 职责分离等设计，形成属于本项目的状态转移规则、接口及故障模型。
- 独立实现须以本项目的 Accepted Contracts 和已验证需求为输入，不照搬 Multica 的代码结构、具体表达、文档文字、UI、协议或产品领域模型。设计、代码、测试、文档由本项目原创；需要时保留公开参考链接和取舍说明。
- **Multica 不是候选 AgentRuntime、Process/Durable Provider 或 SandboxProvider，也不是生产依赖。** 不直接采用它的 CLI 子进程执行层、Daemon、Workspace/Issue/Squad 管理模型。
- 本条已确定的是**第三方参考/源码使用边界**，不代表 PG + Worker/Scheduler 已获生产准入。Temporal、MAF Durable 与 PG + Worker 的任务级恢复和可靠性对比仍遵循 ARCH-TODO-028 等现行门禁。

## 参考范围与本平台职责映射

| 可研究的通用设计问题 | 本平台独立实现时的归属 | 必须坚持的边界 |
|---|---|---|
| 任务领取、排队、并发与背压 | ExecutionScheduler / Process-Durable SPI 候选 | Control Plane 只负责调度与状态裁决，不执行 Shell |
| Run / Attempt、失败和重试 | Harness Kernel + PostgreSQL Task Facts | Plan/Step/Attempt 分离；Retry 不等于 Replan |
| Worker 领取、续租、失联 | Execution Lease / Heartbeat / Fencing | stale Worker 拒绝提交；不接管外部框架内部 ownership |
| 持久化状态与任务级恢复 | RecoveryPoint / Task State / Process-Durable SPI | UNKNOWN 先 Reconciliation；不得盲目重试外部副作用 |
| Coding 工作目录和可执行环境 | WorkspaceRef + SandboxProvider SPI | Session ≠ Process ≠ Workspace ≠ Sandbox；Cube 按需分配 |
| Agent 启动与事件 | AgentRuntime SPI / Typed Events | 使用 Pydantic、OpenAI、OpenCode 等公开接口，不导入 Multica Runtime |

## 工程实施约束

1. **禁止复制实现：** 不从 Multica 拷贝函数、类、配置、数据库迁移、测试用例及 UI；不做逐行移植或“改名重写”。如未来确有源码复用需求，须先另行提交架构变更并进行许可证与法务审查；本 ADR 不提供授权。
2. **不复制不必要的能力：** 不建设 Multica 的 Issue/Squad/完整任务管理产品；平台只保留 Run/Plan/Step/Attempt/Execution、Policy、Recovery、Event 和相应 Adapter。
3. **先验证再选型：** PG Worker 与 Temporal/MAF Durable 的比较仍使用同一故障注入场景：claim/Lease、Worker 崩溃、Cancel/Timeout、WAITING_APPROVAL、RecoveryPoint、非幂等 Tool Receipt 与 UNKNOWN → Reconciliation。
4. **边界与资源模型：** Runtime Worker 可复用服务多个逻辑 Session；Coding/重执行阶段按需申请 CubeSandbox；不强制每个历史 Session 常驻独立进程或沙箱。
5. **审查证据：** 对调度与状态机的实现提交设计解释、Contract Tests、竞态/崩溃/旧 Worker 负例、来源声明（独立实现）、与 Multica 无代码依赖的检查。

## 原因与后果

**原因：** Multica 的任务调度实践可降低方案探索成本，但其 CLI 子进程/Daemon/产品层模型不契合本平台可插拔 AgentRuntime、可复用 Worker 和 Session 级按需 Sandbox 的设计约束。其自定义许可证对部分商业托管和嵌入场景另有要求；本项目没有必要为调度逻辑承受第三方源码依赖和许可证管理成本。

**取舍：** 独立实现可能增加初期开发量，但控制了授权风险、领域耦合与后续产品化边界；可靠性仍须自行证明，不能因借鉴成熟项目就将 POC 标记为 PASS。

**关联：** [正式架构](../ARCHITECTURE.md)、[架构待办 ARCH-TODO-028](../ARCHITECTURE_BACKLOG.md)、[执行调度参考](EXECUTION_CAPACITY_AND_SCHEDULING.md)、[租约与栅栏](EXECUTION_LEASE_FENCING_HEARTBEAT.md)、[失败与恢复](FAILURE_IDEMPOTENCY_AND_RECOVERY.md)、[目标架构候选](MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md)。

> 本文是工程架构与采购边界决定，不构成法律意见；因不复用源码，通常不触发该源码许可证的派生代码义务，但实际产品及任何后续第三方代码集成仍应独立核查。
