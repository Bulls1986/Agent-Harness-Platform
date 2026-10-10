# 多 Harness / CubeSandbox 阶段性准入报告

> 日期：2026-10-09 初稿，2026-10-10 追加真实 OpenCode/Git 验收；性质：**POC 分层准入记录，不是生产 ADR**。
> 当前架构以 [目标架构候选](MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md) 为权威；
> 未完成事项仅登记 [架构 Backlog ARCH-TODO-024～028](../ARCHITECTURE_BACKLOG.md)。
> [验证入口](../../poc/README.md) 提供可重复的最小测试。
> **版本不可漂移：** [2026-10-10 已验证组件 / SDK / Guest OCI Digest / Template 快照](VERIFIED_STACK_BASELINE_20261010.md)。这里的 GO 只对标记的真实验证组合有效，升级版本或换 Cube 部署需独立复验。

> **2026-10-10 ARCH-TODO-025/026 最新真机与 SDK 增量：** [E2B 2.40 + OpenAI Native 真机兼容修复](../../poc/opencode_sandbox/E2B_PRIVATE_DNS_VERIFICATION_20261010.md)：Cube v0.7.2 在受控私有 DNS + 有效本地 CA 下，官方 `e2b==2.40.0` 的真实 create/files/commands/kill、两 Sandbox 文件隔离、`openai-agents==0.23.1` 原生 `E2BSandboxClient.create/exec/aclose` **PASS**（SDK 未私有补丁）；而 e2b 2.53.1 **仍 405**。[平台 AgentRuntime SPI POC](../../poc/runtime_spi/README.md) 的 Pydantic `Agent.run` / OpenAI `Runner.run` 在真实安装 SDK + 本地确定性 Model 下映射 Run Typed Events，有限 PASS；OpenCode `session.prepare` 仍仅合同 Mock，Token SSE / Tool Receipt/Run 持久化/取消恢复尚无真实准入。**集成 POC 限定 GO，生产继续 NO-GO。** 2026-10-09 以及下文关于 E2B 2.40 文件 ConnectError 的旧数据仅代表当时未配置正确 DNS 的历史尝试。

> **2026-10-10 Git 功能补验最终确认：** [Git-enabled Cube 实测记录](../../poc/opencode_sandbox/opencode2_cube_template/VERIFICATION_20261010.md) 已新增 Git OCI Template `tpl-363306ce3b21432cb1ae6536`，Job `c835c0cd-9cf6-4628-9e8e-c4730a3873c0` **READY**，20/20 Layer、225.8 MiB、1/1 分发；同一次真实 Cube MicroVM 测试 `git init/add/commit/log`、OpenCode V2 2 Session/FS/Shell、Pydantic/OpenAI 公共 Tool 跨 SDK 接力、同 ID reconnect、Kill **全部 LIVE PASS**。至此 **ARCH-TODO-027 的最小真实功能链路准入 GO（仅集成 POC）**，仍缺平台自身的 Scope/Lease/Fencing/Recovery、全 Host 执行路径系统性隔离、安全治理、真实模型执行等生产门禁。当前原生 E2B SDK HTTP405 / Data Plane ConnectError **没有因此被解决**；生产 **NO-GO**。本条覆盖下文较早的“Git 待验”历史记录。

## 2026-10-10 Cube OpenCode 2 真机突破（以本节为最新结论）

- **ARCH-TODO-027 Harness-in-Cube 功能 POC 达到 LIMITED GO**：Cube v0.7.2 在 KVM WSL2 使用组合 OCI Template `tpl-aacac99e38bf46e68ecd2f1f`，正式 Job `75309ed6-bfa0-420b-b0cc-19adafc937ff` 全链路 **READY**，RootFS Artifact/节点分发全 PASS；Sandbox.create 真机创建约 4.31 秒。
- **真实 OpenCode 2.0.24 V2**：1 个 MicroVM 中 2 个互异 Session、FS 读取、Shell 创建文件、Cube Native SDK 重新连接读取及 Sandbox.kill 全部 **LIVE PASS**；同一 VM 的 **Pydantic AI Agent 公共 Tool + OpenAI Agents SDK FunctionTool** 从 OpenCode V2 Shell 写入的文件成功接力，**LIVE LIMITED PASS**，FunctionModel/公开 Tool、零托管模型调用。
- **VM 启动失效因素定位**：早期基于官方 `sandbox-code` 自带的 Jupyter Code Interpreter 完整启动链重型且波动大。失败镜像第二次已证实 Guest Agent Ready/容器创建通过，但 Jupyter 在 HTTP 201 创建默认内核后无法及时完成 Startup，Cubelet 30 秒端口探针报 `PortBindingFailed`。同样参数的官方 base control Template `tpl-ae9b7349dfbf48ff92e79d6c` 已 READY。Coding 专用 Guest 的最小修复是 **保留 envd 49983 + 按 envd 活跃状态返回 200 的轻量 49999 Probe**，OpenCode Server 4096 在 Cube Lease 激活后按需启动；不启动不需要的 Jupyter，Docker 测试 1 秒内探针 READY，Cube 实测 READY。
- 当前 READY 版本原生 Git 尚缺失，另一个含 Git 2.39.5 的新 OCI 镜像已在独立 WSL Docker Build **PASS**，完成 Template READY + `git init/add/commit/log` 真机验收前不标 Git PASS。CLI/API 多框架真实 Tool Bridge 完成不等于平台 AgentRuntime SPI/Typed Events/Cancel/Receipt/Worker Failover 已通过。
- **生产准入仍 NO-GO**，`e2b 2.53.1` 的 405 与 `e2b 2.40.0` Data Plane `ConnectError` 不受这个 Cube Native Adapter 成功证据覆盖。Host 上的 OpenCode 原生 Shell/FS 也不会随 SessionID 自动进入 Sandbox，Host 拓扑仍 NO-GO。

[真实模板、受控对照、V2 Session/FS/Shell 与跨 SDK 接力原始证据](../../poc/opencode_sandbox/opencode2_cube_template/VERIFICATION_20261010.md)；
[可重复脚本](../../poc/opencode_sandbox/verify_cube_opencode2_v2_live.py)。

## 分层裁定

| Gate | 裁定 | 原因 |
|---|---|---|
| **A. 进入集成 POC / 可开始实现适配器** | **GO（限定）** | Cube 原生 SDK MicroVM/Shell/文件/同 ID reconnect 真机通过；Pydantic AI 公开 Agent Tool Loop（2 Run/6 Tool）→同一 Cube Sandbox→OpenAI FunctionTool 真机接力通过；Session Scope/Lease Fail Closed 离线通过 |
| **B. 采用 Pydantic 作为通用 Agent Runtime 默认候选** | **CONDITIONAL GO（仅技术候选）** | 20 个并发 Run、Run-scoped Workspace、Linux 真实 Coder Tool，以及 Pydantic 基础 Agent 公共 Tool Adapter→Cube 真机通过；Harness 内置 E2BSandbox/Coder → Cube 原生路径、SDK 0.x 升级仍待验证 |
| **C. 官方 E2B SDK / OpenAI 原生 E2B Client 即插即用 Cube** | **NO-GO（当前版本组合）** | `e2b==2.53.1` / `openai-agents==0.23.1` 原生 E2B Client 对 Cube v0.7.2 的 Sandbox.create 均返回 **405**，不等于 Pydantic/OpenAI FunctionTool 不能通过 Cube Native Provider 接入 |
| **C2. 官方 E2B 2.40.0 + OpenAI E2BSandboxClient** | **GO（版本锁定的最小真机 POC）** | Cube v0.7.2 + `E2B_DOMAIN=cube.app` + 私有 resolver + 可信本地 CA：官方 SDK create/FS/Shell/kill、两沙箱隔离、OpenAI Native create/exec/aclose 全 PASS；不代表 2.53.1/生产 TLS/DNS/Security 已兼容 |
| **D. OpenCode 2 原生 SDK Host Session 自动挂 Cube** | **NO-GO（当前拓扑）** | Docker 负例证明原生 Shell 留在共享 Host；已有 Harness-in-Cube 真机 PASS 不能证明共享 Host 的 FS/Shell/Git/PTY/LSP/Plugin 自动重定向 |
| **D2. OpenCode 2 Harness-in-Cube 专用执行拓扑** | **GO（集成 POC 限定）** | 2026-10-10 Git-enabled 真实 Cube Template READY、OpenCode V2 2 Session/FS/Shell/Git、Pydantic/OpenAI 公共 Tool 同 Sandbox 接力 PASS；生产隔离/平台 SPI 尚待收口 |
| **E. 进入生产 Accepted ADR / 上线** | **NO-GO** | 多 Runtime Agent Loop + 严格租约绑定、跨 Worker/HITL/非幂等 Receipt、Cube 生命周期、隔离与资源门禁没有整体通过 |

**解释：** A 的 GO 允许针对平台自有 Runtime SPI / SandboxProvider SPI 开始**有边界的集成开发和 Demo**，并不是把 Pydantic、OpenAI Native E2B、OpenCode 原生 Host 三条路径都升级 PASS；E 明确没有准入。

## 关键原始证据

| 路径 | 冻结版本/环境 | 实测与限制 |
|---|---|---|
| Cube SDK | Cube v0.7.2，`cubesandbox==0.7.0`，WSL2 KVM，16GiB XFS | 原生 Sandbox.create/commands/files/kill；运行中同 ID connect。最小 POC 非生产容量 |
| OpenAI FunctionTool → Cube | `openai-agents==0.23.1`，Cube Native Client | **LIVE LIMITED PASS**，公开 FunctionTool 手工调用读已批准 Sandbox 文件，零托管模型，不代表 Agent Runner 或原生 E2B |
| 官方 E2B Python → Cube | `e2b==2.53.1`，Cube v0.7.2 | **LIVE FAIL：HTTP 405**，当前 SDK 发 `POST /v2/sandboxes`，Cube 原生路径为 `POST /sandboxes` |
| OpenAI `E2BSandboxClient` | SDK 0.23.1 / e2b 2.53.1 | **LIVE FAIL：HTTP 405**，堆栈经过 `AsyncSandbox.create` |
| OpenCode 2 V2 Server 与 OpenAI SDK | OpenCode 2.0.24 immutable Docker 镜像 | **DOCKER LIMITED PASS**：Session/FS/Shell/FunctionTool 双向文件；非 Cube，零模型 |
| Pydantic AI Harness | harness 0.54.0 / pydantic-ai-slim 2.54.0 | **OFFLINE/Linux CI PASS**：一 Agent 20 Run 与两个独立 POSIX Workspace 的真实 Coder Tool；E2B Ref attach 是 Mock |
| Pydantic AI Agent → Cube Native + OpenAI 同 Workspace | `pydantic-ai-slim==2.54.0`、Cube SDK 0.7.0、OpenAI SDK 0.23.1、真实 Cube v0.7.2；`verify_cube_native_agent.py --live` | **LIVE LIMITED PASS**：1 Agent / 2 Run / 6 Pydantic Tool Calls / 1 MicroVM；OpenAI FunctionTool 实际读取相同文件，零远程模型；**非 Pydantic AI Harness 内置 E2BSandbox/Coder、非原生 E2B Client** |
| Session→Sandbox Router | 平台 Session/Scope/Lease 测试 | **OFFLINE/MOCK PASS**，未知/跨 Scope/过期拒绝；尚未证明真实 OpenCode Native Tool 自动切换 |

### 本轮新增真实 Agent Tool Loop 证据

在健康的 Cube API 3000、TemplateCenter 8090、CubeEgress 9091 上执行 `poc/pydantic_harness/verify_cube_native_agent.py --live`，输出：

```json
{"outcome":"PASS","scope":"live_cube_native_public_tool_adapters","pydantic_agent_runs":2,"pydantic_tool_calls":6,"shared_agent_instances":1,"shared_cube_microvms":1,"same_workspace":"PASS","openai_function_tool_handoff":"PASS","hosted_model_calls":0,"pydantic_native_e2b_backend":"NOT_TESTED","openai_native_e2b_client":"NOT_TESTED","opencode2_cube":"NOT_TESTED"}
```

SDK 通过其公开 `@agent.tool` 与 OpenAI `@function_tool` 调用 Cube **原生** Provider。这个测试是真实 Pydantic **Agent Tool Loop** 而非仅手工调用 Tool；模型输出由 FunctionModel 确定性脚本提供，**未验证真实 LiteLLM/LLM Tool Calling、Harness 内置 Coder、并发多 Scope 生产权限/持久租约或 Worker 恢复**。成功后 Sandbox 在 finally 中销毁。

### 2026-10-09 22:50：OpenCode Cube 模板 40% 卡死 RCA（真实复测）

- **原 Job** `ec70a828-f898-4af8-95be-b8cbaa72c7b9`：CubeTemplateCenter 在 20:05:17 构建 `BUILDING_EXT4` 时收到 `context canceled`；其向 CubeMaster 的 `FAILED` 回调同因 `context canceled` 未能发出，导致 Master 反复显示 `RUNNING 40%`。同时间 systemd 停止整个 `multi-user.target / cube-sandbox-control.target`，证明服务生命周期中断。日志中的 `CAP_MKNOD/xattrs` 仅通用 Hint，非具体 errno；16GiB XFS 剩余约 15GiB。
- **同镜像复验 Job** `4be59892-961f-4453-8503-d4debd9ad1b9`，使用持续 WSL 运行进程保活：OCI pull 16/16、RootFS EXT4 Artifact **READY**、分发 **1/1**，进度 40→70→85，证明原镜像和 EXT4 构建可用。新任务最终 `FAILED/CREATING_TEMPLATE`：Cubelet 网络初始化成功，VMM 内核/vCPU 启动但未在 10 秒内收到预期 Shim Event，错误 `Receive event timeout after 10000ms`。这是独立 Guest 启动门禁，尚未定位更深层原因。**Template READY 与微虚机内 OpenCode 运行未验收**。
- 分级准入不变：**集成 POC GO（限定），生产 NO-GO；ARCH-TODO-027 仍 OPEN**。详见 [完整 RCA](../../poc/opencode_sandbox/opencode2_cube_template/INCIDENT_20261009.md)。此段覆盖下文较早的“Registry 尚未推送 / Cube 未拉取”等历史描述。

### 2026-10-09 E2B SDK 兼容与 OpenCode OCI 模板新证据

- 官方 E2B Python SDK wheel/API 对照：**1.0.5** 使用旧 POST /sandboxes 但公开 Sandbox.create 不存在；**2.0.0** 有公开 Sandbox.create，使用旧 POST /sandboxes，但不读 E2B_API_URL，debug 模式返回 synthetic `debug_sandbox_id`，文件连接拒绝，非真机成功；**2.40.0** 具备公开 Sandbox.create、旧 POST /sandboxes 并读取 E2B_API_URL，独立 WSL venv 已安装，在 Cube 3000/8090/9091 全健康后 `Sandbox.create` 返回真实非 Debug 句柄 **LIVE CREATE PASS**，但 `files.write` 经 E2B Data Plane 仍 **ConnectError / LIVE FAIL**，Commands 未验；**2.53.1** 保持真实 HTTP 405 FAIL。离线 API Shape ≠ SDK 与 Cube Native GO。新增 `poc/opencode_sandbox/verify_cube_e2b_basic.py`，明确离线与 opt-in Live Gate。
- **OpenCode 2.0.24** OCI 已从原 Docker Desktop 镜像（保留 13 个容器）导入独立 WSL Docker；Cube 官方 sandbox-code 基础 OCI 成功拉取。初次 Multi-stage Docker build 的 ARG 位置错误及 Alpine/musl 二进制在 Cube Debian guest 内缺 loader (127) 已修复；**组合 OCI Build + `opencode --version` 真机 PASS**：`opencode v2.0.24`、`Successfully built 825b61c967d0`。获取本地 `registry:2` 镜像遭遇 Docker Hub 连接重置；**尚无 Cube Template READY、MicroVM 内 OpenCode V2 Session PASS**。
- Cube 官方 OpenCode Bash 插件只拦截 Bash、每次命令重新创建 VM、Host 读写与 MicroVM 文件不共享，不能满足 Session→连续 Sandbox 和编辑→执行共享 Workspace。以 **Harness-in-Cube** 为 Coding 主线，仍保持 ARCH-TODO-027 未验收。

具体原始命令、下载的 1.0.5 / 2.0.0 / 2.40.0 SDK、Cube 冷启动 BLOCKED 与 Docker ABI 原因见 [Cube专项 Findings](../../poc/opencode_sandbox/CUBE_E2B_COMPATIBILITY_FINDINGS.md)。本轮分级 Gate A / E **不升级**：集成 POC GO（限定），生产 NO-GO。

## 当前允许推进的工作

通过平台 **SandboxProvider SPI** 封装 Cube Native SDK，经公开 `Tool / Workspace Backend` 接入 Pydantic 与 OpenAI；同一授权 Scope 的 Agent Run 通过受信任的 Lease ID 路由，共享物理 Sandbox。保留 OpenCode 2 在隔离 Cube 实例内运行的候选路线，不向共享 Host 暴露未经验证的原生 FS/Shell/PTY/Git 等接口。

这些是 POC 范围内允许的实现路径，生产准入仍要求经过 [ARCH-TODO-025～028](../ARCHITECTURE_BACKLOG.md) 的测试和 Accepted ADR 收口。**对 Cube Native Adapter 有限接入的正向证明，不会改变官方 E2B SDK 不兼容的负面证据。**

## 未满足的关键条件

- 核实和固定官方 E2B SDK 与 Cube API 版本兼容矩阵；必要时用公开 Cube SDK/REST Adapter，禁止依赖私有 SDK monkey patch。
- OpenCode 2 Cube OCI Template、真实 Session/FS/Shell/Git；共享 Host 全入口重定向不达标则保留隔离拓扑。
- 真实 AgentRuntime SPI 的 Pydantic/OpenAI/OpenCode 同一平台 Typed Event/Cancel/Receipt 接力，而不是只把工具回调拼接起来。
- 任务级持久租约、Worker A→B 崩溃接管、HITL 恢复、非幂等 Tool Receipt UNKNOWN 对账；Volume/暂停恢复/容量及不同 Scope 隔离。
- 可接受的安装/升级与运行资源、SDK 0.x 版本冻结和端到端重复验收。

## 代码与目录整理原则

1. 根 README 只提供统一入口，`docs/README.md` 负责权威文档导航，`poc/README.md` 负责脚本。
2. 旧 MAF、Temporal、OpenCode 及 Cube 试验文件保留在原目录，不重命名已被 GitHub CI 或文档引用的路径；不删除未合并分支/工作树/容器。
3. 在线证据和负例继续落到原专项 Findings，归纳状态只在本文件；开放任务只能落 `ARCHITECTURE_BACKLOG.md`。
