# Microsoft Execution Containers（MXC）执行沙箱后端候选评估

> 状态：**Candidate / DEFERRED（未采纳、未验证）**  
> 记录日期：2026-10-09  
> 对应架构待办：ARCH-TODO-024  
> 归属：SandboxProvider SPI / Execution Plane  
> 优先级：P2；**不属于当前 POC-A 验收范围，也不构成阻塞项**

## 1. 候选判断

将 Microsoft Execution Containers（MXC）列入**可选执行沙箱后端**的技术评估清单，优先评估 Linux 上短生命周期、受限 Shell/Code/Tool 执行。此处的“列入候选”不是选择 MXC、承诺引入 MXC SDK，或改变现有生产 Sandbox 的默认候选。

当前正式架构仍以已有 SandboxProvider SPI 解耦；CubeSandbox 是通用 Coding Sandbox 的首轮生产候选，Docker 为开发/兼容/fallback，其他 Provider 按已有 Contract 评估。MXC 能否作为独立 Provider，或作为已有 Provider 内部某一执行模式，必须由后续实测决定；**此时不新增 SandboxExecutionProvider 等平行 SPI**。

### 候选价值

- 以较轻的 OS 原生隔离承载一次性代码与工具执行，可能降低相对于完整容器/VM 的启动成本（尚无本项目实测）。
- 使用统一策略描述文件、网络和进程权限，能够尝试映射平台已有 ExecutionRequest / Policy 到具体宿主 OS。
- 为 Windows/macOS 本地工具执行及未来扩展保留选择，但企业服务端 Linux 场景应独立验证，不因跨平台宣传而默认认为安全和行为等价。

## 2. 与当前平台的关系（保持原有架构）

~~~text
Control Plane（Run / Policy / Recovery / Reconciliation）
    → ExecutionScheduler
    → 已有 SandboxProvider SPI
        ├─ CubeSandboxProvider（当前通用 Coding 生产候选）
        ├─ DockerProvider（兼容 / 开发）
        └─ MXC 后端候选（尚未实施；独立 Provider 或内部模式待验证）
    → Sandbox / OS 隔离执行
    → ExecutionResult + Artifact/Evidence Reference
~~~

- **共享 Agent Worker / MAF / Agent SDK 不变**。TaskContext 与 WorkspaceResolver 负责受控 API 的逻辑路由，不代表安全隔离；ThreadLocal、Task ID、路径重写都不能约束任意 Shell、子进程及不可信代码。
- **工作空间（Workspace）与沙箱（Sandbox）生命周期分离**：任务和工作区可以长于一次 Sandbox 执行，具体目录映射、挂载、清理由 Provider 完成。不得因为 MXC 增设新的 Workspace 领域模型。
- **执行隔离不等于任务恢复**：RecoveryPoint、持久化 Task Facts、UNKNOWN → Reconciliation、Tool Side Effect Receipt、OSS Artifact/Evidence 均由原有平台契约处理。沙箱实例存活不是任务级恢复必要条件。
- **不转移治理责任**：企业 IAM、MCP Trust、Secret、Network Infrastructure、Supply Chain Security 仍归既有外部平台；Harness 只按现有 Policy/Capability/Execution 边界消费与记录。
- **执行后端能力不齐时显式 unsupported / reject**。不得在要求隔离时静默降级为裸宿主机 Shell，亦不得以仅设置逻辑工作区来伪装成 Sandbox。

## 3. 截至 2026-10-09 的官方事实与尚存疑点

| 项目 | 公开信息 | 选型含义 |
|---|---|---|
| 发布状态 | Microsoft 在 2026-10-07 宣布 MXC GA | 仅代表官方发布声明；**不等价于本项目已验收** |
| 实现成熟度 | 官方 microsoft/mxc 仓库 README 仍提示代码处于 early preview，部分策略可能过宽，并声明现有 profile 不应直接作为安全边界 | 必须按具体版本/后端独立进行安全与正确性验证；记录公告与仓库描述的差异 |
| Linux | 默认 Bubblewrap；另有 LXC 等后端，宿主须安装对应依赖 | 生产部署可用性依赖 Linux namespace、安全策略、镜像/工具链及运行环境 |
| macOS | 使用 Seatbelt | 服务端 Linux 验收不能复用 macOS 结论 |
| Windows | Process Container；Session/WSL 等能力偏向 Windows 特定版本 | 不用 Windows 的 Session 能力推导 Linux 有等价持久会话能力 |
| MicroVM | 官方标注实验性 | 不纳入当前生产级选择的默认前提 |
| 生命周期 | 官方 SDK 支持 one-shot，也展示部分后端 state-aware lifecycle | **不预设 Linux 默认 Bubblewrap 可以支持持久 Session/pause/resume/snapshot**；依实际 Capability 验证 |
| 文件与网络策略 | 不同后端/OS enforcement 并不完全相同；仓库注明 Linux/macOS 网络代理策略存在 cooperative 约束 | 限权必须真实测试；不把 policy schema 存在视为内核强制执行的证明 |

相关事实可能随官方仓库版本变化；正式选型时必须冻结 MXC 版本/commit、host kernel/OS、后端及依赖版本，再更新验证结论。

## 4. 后续评估门槛（非 POC-A 任务）

只在完成当前核心 POC 收口且有明确受限执行需求时，安排与 CubeSandbox / Docker 等现有路线的**同 workload、同 host、同资源配额**对比。

1. **能力映射**：确认已有 SandboxProvider 的 execute/cancel/cleanup、ExecutionResult/Evidence、Policy、Environment Fingerprint 可以映射，不得修改上层 Workflow/Domain Model。
2. **隔离正确性**：并发 Task A/B 跨工作区读写、符号链接/目录穿越、proc/env/凭据可见性、宿主敏感路径访问及恶意子进程逃逸验证；拒绝/不可证明时判 FAIL。
3. **网络与 Secret**：验证禁止出站、loopback、本机服务、DNS、内网与凭据泄露的真实 enforcement；cooperative policy 不当作强隔离保证。
4. **进程生命周期**：timeout、graceful cancel、强制终止、子进程树清理、孤儿进程及残留文件；ACK 不等于 TERMINATED。
5. **失败与恢复**：kill sandbox/worker、宿主重启、分离 Workspace 的重新绑定；非 PURE 操作未知结果进入 UNKNOWN → Reconciliation，不盲目重试。
6. **性能与容量**：记录 cold/warm startup、p50/p95 latency、CPU/内存、并发吞吐、cleanup 时间，所有指标采用同环境可复现实测，不提前承诺性能优势。
7. **环境与可移植性**：执行环境依赖、宿主支持矩阵、OCI / 工具链兼容性、不可变版本绑定；不把 Linux 进程沙箱直接等同完整 Coding Workspace。
8. **运维与证据**：执行 ID 与 Run/Step/Attempt correlation、日志/退出状态、失败原因、Artifact/Evidence 引用、版本升级/回滚及审计能力。

验收结果按具体 backend 标记 PASS / PARTIAL / FAIL / UNSUPPORTED；不允许仅凭 SDK 调用成功宣称通过安全门禁。达到等价的安全、恢复、兼容性及可运维性后，才比较性能收益。

## 5. 决策状态、触发条件和明确排除

**目前结论：保留候选，延后验证，不写入 Accepted ADR。**

重新打开 ARCH-TODO-024 的条件：

- 当前 POC-A / POC-C 的已承诺 Gate 与收口工作完成；
- 有明确需要轻量 OS 级受限执行的生产 workload；
- 已经具备现有 SandboxProvider 基线对照和可复现实验环境；
- Microsoft 发布的具体后端提供可以验证的隔离与维护承诺。

届时根据证据选择 **Adopt / Keep Candidate / Reject**，如采纳则单独更新 ARCHITECTURE.md、受影响 Contract、POC/Contract Suite 和正式 ADR。**现阶段不创建实现任务、不改变 G3/G2/G6 优先级，也不将此项作为 G5 新硬门禁。**

## 6. 官方资料（核验于 2026-10-09）

- Microsoft Windows Developer Blog（2026-10-07）：https://blogs.windows.com/windowsdeveloper/2026/10/07/microsoft-execution-containers-policy-driven-containment-for-ai-agents/
- Microsoft 官方代码库及 README（应特别关注 preview/security warning）：https://github.com/microsoft/mxc
- 官方配置/后端文档：https://github.com/microsoft/mxc/blob/main/docs/schema.md
- 现有平台讨论契约：[Coding Execution / Sandbox](EXECUTION_SANDBOX_ARCHITECTURE.md)、[安全信任边界](SECURITY_THREAT_MODEL.md)、[Task Recovery](TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md)、[取消与超时](CANCELLATION_TIMEOUT_PROPAGATION.md)
