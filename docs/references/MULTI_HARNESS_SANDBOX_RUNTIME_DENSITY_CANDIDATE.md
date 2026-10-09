# 多 Harness 共享 Sandbox 与 Runtime 密度：架构变更候选

> 状态：**POC CANDIDATE / 未接受、未替代原有 Contract**
> 日期：2026-10-09
> 对应：ARCH-TODO-024、ARCH-TODO-020；[专项 POC](../../poc/opencode_sandbox/README.md)

## 1. 触发背景及变更范围

未来 PDLC、AI 企业门户需要不同的逻辑专业 Agent（产品、研发、测试、知识、业务等），
各自可选 OpenCode 2、OpenAI Agents SDK、MAF 等 Harness；Intent Router 可选定逻辑
Agent 或 Process，Workflow 管理跨 Agent 的门禁/审批。现有 Sandbox 讨论主要面向
Coding Execution，现把 Sandbox 调度契约推广到**需要隔离执行能力的所有 Harness**，
并增加 Runtime 高密度的明确候选拓扑。

**本轮不是**采纳新的生产 ADR，也不决定 Temporal 与 MAF Durable 谁获选；
Router/Agent Catalog 只是上游逻辑路由与配置能力，不新建通用 IAM、MCP 治理或
Sandbox Infrastructure Control Plane。

## 2. 已接受、不允许被本候选推翻的约束

- `Run ≠ Workspace ≠ Runtime Session ≠ Sandbox ≠ OS Process`。
- 平台拥有 Run/Step/Attempt/Execution/RecoveryPoint、任务事实、审批、结果与恢复；
  Framework 原生状态和 Sandbox 状态不替代 Harness Task Facts。
- Coding/不可信本地命令必须隔离，不得在共享 Agent Worker 宿主机裸跑。
- SandboxProvider SPI 是平台消费外部隔离执行设施的边界。CubeSandbox
  （Local baseline、Remote burst）仍是生产**候选**；Docker 是开发和对照路径；
  E2B API/SDK 是兼容接口价值，不将 E2B Cloud 设为强制生产 Provider。
- Policy/授权、Workspace 与 Worktree 隔离、版本冻结、Side Effect Receipt、
  UNKNOWN→Reconciliation、任务级 Recovery 不因高密度部署而削弱。
- 不依赖 fork、monkey patch、Framework 私有内部实现达成关键路径。

## 3. 本轮新候选（Delta），尚待 Gate 通过

### 3.1 Sandbox 可选，需求由 Execution Capability 决定

非 Sandbox 场景（LLM / 已治理 MCP / 企业 API）不分配 Sandbox。
需要 Shell/文件执行的阶段经 Capability + Execution Policy 决策后获取
`Sandbox Lease`，而不是以每个 Agent、Session 固定分配。任务跨专业 Agent 顺序
执行时，**相同授权 Isolation Scope 且 Policy 允许**才可复用同一 Lease；
跨用户/项目/秘密凭据等不同安全边界不得为了资源效率复用运行状态。
`Agent Profile` 可以声明 NONE / ON_DEMAND / REQUIRED，最终准入由 Policy 决定；
只是轻量执行 Metadata，当前不为之新增独立核心领域对象。

### 3.2 多 Session 共享 Worker，Sandbox 仍按隔离 Scope 分配

候选目标是 `session_count` 与 `worker_process_count`、`sandbox_count` 解耦。
没有活动执行的 Session 仅保留持久任务/会话事实；Worker 是共享池；
Sandbox 随实际隔离执行需求申请、暂停、恢复与回收。Agent Runtime 进程允许
为内部并发使用异步任务/线程，但**线程/请求上下文隔离不构成 OS 级安全隔离**。
SDK/Framework 的全局 CWD、环境变量、File Tool 或 LSP 存在共享风险时必须拒绝
跨安全 Scope 的并行执行，不能用 Session ID 作为授权边界。

### 3.3 两种执行拓扑并行 POC，不预先锁死

```text
逻辑 Agent / Workflow
       ↓
Agent Runtime SPI  ─────────→ 共享 Runtime Pool (OpenCode 2 SDK Host / MAF / SDK)
       ↓                                             ↓ 工具执行请求
Execution Capability + Policy + Scheduler ───────────┘
       ↓
SandboxProvider SPI ───→ CubeSandbox（候选）/ Docker（对照）
```

- **Topology A：Harness-in-Sandbox**。把具有宿主机文件/命令能力的
  Coding Harness（如 OpenCode）放入实际 Sandbox；通过 Session/idle pause/
  template warmup 复用容量。较容易保证完整隔离，但有每活跃 Sandbox Harness 进程
  的开销；不是一个历史 Session 永久一个容器。
- **Topology B：Shared Harness Host + Remote Sandbox Tools**。多个 Session
  复用进程，在全部文件读写、Shell、Git、LSP、PTY、插件、Skill 脚本及隐式代码
  执行入口都能通过公开 API 安全重定向且并发隔离时才允许用于生产。
  单纯覆盖 Bash、或单纯实现两个不同 Session，**不等于通过 B 的安全 Gate**。
- 两拓扑均不得让某个 Framework 或 Sandbox Provider 拥有平台 Workflow、
  任务终态、权限审批或跨组件恢复语义。

### 3.4 OpenCode 2 / OpenAI Agents SDK 的接入边界

OpenCode 2 作为本专项**目标版本线**；OpenCode 1.14.28 旧 POC 保留为历史证据，
不能直接推出 V2 接口、插件或隔离行为。已下载并在隔离容器观察
`ghcr.io/anomalyco/opencode:2.0.24`：

- 受限 Docker 内 `opencode serve` 成功启动；未经认证的请求返回 401；
- 提供启动时临时凭据后 `POST /api/session` + `location.directory` 返回 Session；
- 旧 `/api/health` 探针曾返回 404，不允许以 V1 health path 推断 V2 状态；
- V2 的嵌入 SDK Host、跨项目安全 Context/文件工具路由仍是待 POC 的
  **Capability Candidate**，未验证不宣称成功。

OpenAI Agents SDK 0.23.1 的官方 `DockerSandboxClient` + `SandboxSession`
已在 Docker 内实测；公开 `FunctionTool` 可以桥接平台发放的
`Sandbox Lease` 进行命令/文件操作。Native Client 与平台桥接路径必须分别测试，
不强迫 SDK 内核采用平台的 Tool API。二者都不能替代尚未完成的真实 Agent
模型/Runner/多 Framework 接力测试。

## 4. 必须证明而非推断的验收矩阵

> **2026-10-09 优先级调整**：先验证 CubeSandbox 作为生产 E2B Provider 的
> SDK 兼容性、Data Plane、Template、跨 Harness 接力和任务级恢复，
> 再决定 OpenCode 2 SDK Host 的密度优化是否值得投入。
> 对应新增 [Cube E2B 兼容专项门禁](../../poc/opencode_sandbox/CUBE_E2B_COMPATIBILITY_FINDINGS.md)。
> Cube 官方资料已揭示 Volume 官方 E2B Python SDK 不完全兼容，
> OpenAI Agents SDK 的官方 Cube 集成示例涉及运行时补丁；仍须遵守
> Public Extension Point 原则，未验不得称为 drop-in 全兼容。

| Gate | 最小证据 | 当前状态 |
|---|---|---|
| S1 | OpenCode 2 真实容器 Server/Session、文件/命令/Git/PTY/插件完整边界 | PARTIAL：Server + Session |
| S2 | OpenCode 2 SDK Host 单进程多 Session；跨项目并发文件/命令不串扰 | NOT PROVEN |
| S3 | OpenAI Agents SDK 真实 Native SandboxSession 和平台 Tool Bridge | PASS（局部无模型） |
| S4 | 同一**物理 Sandbox** 中 OpenCode 2 ↔ OpenAI SDK → 同一 Workspace 的可核验接力 | PASS（有限：公开 FS/Shell API + SDK FunctionTool、无模型；未验 Agent Loop/Git/LSP） |
| S5 | 两个不同 Isolation Scope 跨容器拒绝读写/宿主机逃逸检查 | PARTIAL：Docker 基线 |
| S6 | OpenCode + SDK + 后续 MAF 的 CubeSandbox/E2B 兼容 conformance | **BLOCKED：当前无 Cube 实例、Template、Proxy，Docker 缺 /dev/kvm；Cube 官方存在 SDK 兼容限制** |
| S7 | 一致负载下 Topology A/B 的 RSS/CPU/P95/进程数/Sandbox 数和回收情况 | NOT RUN |
| S8 | Worker/Sandbox 崩溃后任务级 RecoveryPoint/Workspace/Receipt 安全边界 | NOT RUN |

所有实测都应冻结 Harness SDK 版本、镜像 digest、场景、隔离策略、样本数量；
零模型探针不得宣称完整 Agent 工作流。未过门禁的设计只能保持候选。

## 5. 与已有架构的关系及下一步

- `EXECUTION_SANDBOX_ARCHITECTURE`、`EXECUTION_CAPACITY_AND_SCHEDULING`、
  `WORKSPACE_AND_GIT_MODEL`、`RUNTIME_TOPOLOGY` 的既有 Accepted/Reference
  仍有效；本文件只记录将 Sandbox 可选能力推广到多 Harness 以及 OpenCode 2
  候选执行拓扑的**增量**。
- 下一步先跑 **OpenCode 2 真实 Sandbox + OpenAI SDK 同 Sandbox 接力**，然后
  复核是否能从 OpenCode 的公开扩展点安全实现 Topology B，再测资源成本。
- 没有足够证据时倾向 A（完整隔离）作为 Coding fallback；不为节省进程数
  绕过强隔离，不提升 POC 结论为 Accepted ADR。
