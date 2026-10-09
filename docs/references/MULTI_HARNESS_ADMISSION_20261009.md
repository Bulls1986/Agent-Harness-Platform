# 多 Harness / CubeSandbox 阶段性准入报告

> 日期：2026-10-09；性质：**POC 分层准入记录，不是生产 ADR**。
> 当前架构以 [目标架构候选](MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md) 为权威；
> 未完成事项仅登记 [架构 Backlog ARCH-TODO-024～028](../ARCHITECTURE_BACKLOG.md)。
> [验证入口](../../poc/README.md) 提供可重复的最小测试。

## 分层裁定

| Gate | 裁定 | 原因 |
|---|---|---|
| **A. 进入集成 POC / 可开始实现适配器** | **GO（限定）** | Cube 原生 SDK MicroVM/Shell/文件/同 ID reconnect 真机通过；Pydantic AI 公开 Agent Tool Loop（2 Run/6 Tool）→同一 Cube Sandbox→OpenAI FunctionTool 真机接力通过；Session Scope/Lease Fail Closed 离线通过 |
| **B. 采用 Pydantic 作为通用 Agent Runtime 默认候选** | **CONDITIONAL GO（仅技术候选）** | 20 个并发 Run、Run-scoped Workspace、Linux 真实 Coder Tool，以及 Pydantic 基础 Agent 公共 Tool Adapter→Cube 真机通过；Harness 内置 E2BSandbox/Coder → Cube 原生路径、SDK 0.x 升级仍待验证 |
| **C. 官方 E2B SDK / OpenAI 原生 E2B Client 即插即用 Cube** | **NO-GO（当前版本组合）** | `e2b==2.53.1` / `openai-agents==0.23.1` 原生 E2B Client 对 Cube v0.7.2 的 Sandbox.create 均返回 **405**，不等于 Pydantic/OpenAI FunctionTool 不能通过 Cube Native Provider 接入 |
| **D. OpenCode 2 原生 SDK Host Session 自动挂 Cube** | **NO-GO（当前拓扑）** | Docker 负例证明原生 Shell 留在共享 Host；Cube `sandbox-code` 模板缺 opencode/node/bun；优先做 Harness-in-Sandbox OCI Template |
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
