# OpenCode + E2B-compatible Sandbox / Shared Runtime POC

> **当前首要门禁：CubeSandbox 提供 E2B 兼容接口。**
> [Cube E2B 兼容性与实测记录](CUBE_E2B_COMPATIBILITY_FINDINGS.md)，
> [离线/真实 Cube 合约测试](verify_cube_e2b.py)。
> 当前环境缺 Cube MicroVM/Template/Endpoint，真实 Cube 未通过；
> Docker 与 OpenCode 2 的 PASS 仅作为对照证据。

> **Session → Cube E2B 执行适配（新增离线 POC）**：
> [`cube_e2b_session_adapter.py`](cube_e2b_session_adapter.py) 通过受信
> `session_id/run_id/isolation_scope/lease_generation` 解析已分配的
> `sandbox_id`，使用官方 E2B `Sandbox.connect(sandbox_id)`，
> 然后调用 `commands.run`、`files.read/write`。离线夹具
> [`verify_cube_e2b_session_routing.py`](verify_cube_e2b_session_routing.py)
> 已验证两个 Session 路由到不同 ID、拒绝失效/跨 Scope 请求，并从
> 重建的绑定表连接旧 ID。**此结果使用 Fake E2B Client，非真实 Cube，
> 且尚未注入 OpenCode 2 原生 Tool Executor。**

> **2026-10-09 当前关注点**：一个共享 OpenCode 2 Worker 服务多 Session；
> 每个需要隔离执行的 Session 绑定其 CubeSandbox Lease。平台的绑定准入
> 单元测试已通过，但 OpenCode 2 的原生 Shell/FS/PTY/Git/LSP/插件接口
> 尚未证明全部受此绑定控制。详见
> [架构候选 3.5](../../docs/references/MULTI_HARNESS_SANDBOX_RUNTIME_DENSITY_CANDIDATE.md)。

> **共享 Host Session→Sandbox 反向实验：**
> [`verify_opencode2_shared_host_negative.py`](verify_opencode2_shared_host_negative.py)
> 已证明（OpenCode 2.0.24、2 Session、2 模拟外部 Sandbox）：
> 原生 `/api/shell` 在共享 Host 执行，**不会**仅凭 Session 的
> Sandbox Binding 自动重定向。这是对共享 Host 拓扑的负面证据，
> **不是 CubeSandbox 测试**。平台显式 Session Lease 路由的
> `session_sandbox_router.py` 原型仍需完整复测；不能称为透明
> OpenCode Tool Adapter。

> **版本基线变更 2026-10-09：目标改为 OpenCode 2。**
> [ARCH-TODO-024 架构变更候选（先登记、再验证）](../../docs/references/MULTI_HARNESS_SANDBOX_RUNTIME_DENSITY_CANDIDATE.md)；
> 下文的 OpenCode 1.14.28 为不可删改的**历史实测**，不作为 OpenCode 2 通过证据。
> 下一批验收使用 OpenCode 2.0.24 容器镜像
> `sha256:9500f3474188a4b89e165c65fada370dbde5e038cc3b751ed5dcbd27d7620315`。
> 当前完成的 V2 预检：受限 Docker 内 Server 启动、默认 401 鉴权、
> 携带隔离环境内生成的临时凭据 `POST /api/session` 可创建 Session
> 并返回 `location.directory=/workspace`。
> 本地旧 `/api/health` 路径返回 404，不能直接沿用 V1 的健康探针。
> V2 SDK Host 的共享进程并发安全尚未验证；跨 Harness 的原生 API/Tool
> 文件接力仅在**同一 Sandbox、零模型、限定命令**场景获得证据。
>
> **架构记录后的后续实测更新：** OpenCode 2.0.24（immutable image digest）
> 与 OpenAI Agents SDK 0.23.1 在**同一 Docker Sandbox** 完成 SDK FunctionTool
> 写文件 → OpenCode 2 原生 `/api/fs/read/*` 读文件 →
> OpenCode 2 原生 `/api/shell` 写文件 → SDK FunctionTool 读取校验，
> **限定 PASS**；零模型调用。共享 Host 多项目隔离、Git/LSP/插件、真机 Cube
> 以及端到端 Agent Loop 未通过，仍不得作为生产 GO。

> 2026-10-09。**专项进行中，不是 G5 或共享 Coding Runtime 的生产 GO。**
> 本专项遵循既有 Workspace/Sandbox、Control/Data Plane 和容量契约，
> 不更改 Runtime Domain Model，也不让 E2B Cloud 成为生产强制依赖。

## 核心问题

长期存在的大量逻辑 Agent Session **不能**等于相同数量的 OpenCode
进程或 Sandbox。需要分别证明以下三件事，不能互相替代：

1. 一个 OpenCode Server 通过公开 HTTP API 承载多个 Session。
2. OpenCode-in-Sandbox 通过完整 FS/Shell/Git/Session 行为，且每次执行
   有明确、可重建的 Workspace / Sandbox Binding。
3. 共享的 OpenCode Server 可以在不同项目/用户并发时，将 **全部**
   文件、编辑、Shell、Git、LSP、插件和其他可访问宿主机资源的路径
   安全隔离至目标 Sandbox；任意工具不支持则必须 fail closed。

第 1 项是容量前提，**不自动证明第 3 项的执行隔离**。

## 当前实测与状态

| 证据 | 状态 | 严格范围 |
|---|---|---|
| Windows OpenCode 1.14.28, headless HTTP health | PASS | 本机隔离临时目录与 loopback；未调用 LLM |
| 同一 Server 的两个已提交 Git 项目、6 与 20 个并发 Session | PASS | 两次独立启动各 1 个 Server 实例，项目列表无跨项目 Session；未测完整子进程树 |
| 只有 git init 但没有初始 commit | 发现风险 | 两个项目的 Project ID 均为 global，不能用作安全身份 |
| E2B Cloud OpenCode Sandbox | NOT RUN | 缺 E2B_API_KEY；明确 opt-in 后可执行 |
| CubeSandbox + OpenCode 自定义模板 | NOT RUN | 缺 Cube API Endpoint 和已构建的 OpenCode 模板 |
| 共享 OpenCode Runtime + Sandbox Tool Adapter | NOT PROVEN | 宿主机文件/Shell/LSP/插件路径未被完整隔离 |
| 多 Session RSS/CPU、10/100/1000 负载 | NOT RUN | 尚无相同负载资源对照与容量边界 |
| 统一 SandboxProvider / Docker 两个隔离 Scope | PASS（有限） | 真实非 root/只读根目录/无网络容器；同一绑定的两个逻辑角色顺序复用、异绑定拒绝 |
| OpenAI Agents SDK 0.23.1 原生 DockerSandboxClient | PASS（有限） | 官方公开 API 创建 SandboxSession 并在 Docker 容器内执行命令；不调用模型 |
| OpenAI Agents SDK 0.23.1 统一 Tool Adapter | PASS（有限） | SDK 原生 FunctionTool 解析与回调 → 平台提供的同一个 Docker SandboxProvider，真实 Shell/Read/Write |
| OpenCode 2.0.24 与 OpenAI SDK 同物理 Sandbox 双向接力 | PASS（有限） | 同一 Lease 内 V2 Server 创建 2 个逻辑 Session；SDK FunctionTools 与 V2 原生 FS/Shell 共享文件；无模型 |
| 平台 Session→Sandbox 绑定准入 | PASS（仅逻辑） | 2 Session / 2 Sandbox ID，未知、跨 Scope、陈旧 generation 拒绝；非 OpenCode 原生工具接入 |
| 共享 V2 Host 所有工具根据 Session 切到指定 Cube Sandbox | **NOT PROVEN** | Tool Transform 候选可行，但原生 Shell/FS/PTY/Git/LSP/插件路径未封闭 |

可复验绑定层纯逻辑夹具：

```bash
python poc/opencode_sandbox/verify_session_sandbox_binding.py
```

测试 **没有**证明 OpenCode 的任意 Tool 能在跨项目场景安全路由，
更没有证明同一进程能够安全执行来自不同用户的任意不可信代码。
不同 Git 仓库可能共享相同 root commit，OpenCode 的 Project ID
也不适合用于授权、Sandbox Binding 或跨用户访问控制。

## ④ 跨 Harness 统一 SandboxProvider / OpenAI Agents SDK

官方 OpenAI Agents SDK 已支持 `SandboxAgent`、`SandboxRunConfig`，
原生 `DockerSandboxClient`、`E2BSandboxClient` 及其他远程
Sandbox 后端；可以选择让 SDK 用其内建完整 Sandbox 能力，
也可以使用公开的 `FunctionTool` 调用平台批准的 Sandbox Lease。

这里所谓 **一套 Sandbox** 指共享一个 Platform SandboxProvider
契约、容量池和 Lifecycle/Binding/Policy，不是让所有不同信任域的
Agent 共用同一个物理 Sandbox。Agent Runtime 可长期共享进程；
不同隔离 Scope 的执行必须由 Sandbox Provider 保证隔离。

```bash
# 仅验证平台 SandboxProvider，使用已有本机 postgres:16-alpine
python poc/opencode_sandbox/verify_unified_sandbox.py

# 本机独立 Python 环境中安装官方 SDK（不会调用模型）
python -m pip install "openai-agents[docker]==0.23.1"
python poc/opencode_sandbox/verify_agents_native_docker.py
python poc/opencode_sandbox/verify_agents_sdk_tool_bridge.py
```

在真实 Docker Engine 上执行三条测试：

1. **Provider 契约**：Run A 的两个角色使用同一个 Sandbox Lease，
   读取/写入共享临时文件；Run B 不能读取或写入 A，B 有独立
   Sandbox；验证用户 10001、无网络、只读根 FS 和资源上限配置。
2. **SDK Native**：使用官方 `DockerSandboxClient.create` 创建
   `SandboxSession`，通过 `session.exec` 在实际容器中执行命令。
3. **SDK Tool Bridge**：用 SDK 官方 `@function_tool` 创建
   `sandbox_shell/read/write`，通过其公开回调与 ToolContext
   走平台单个 Sandbox Lease，完成真实写入、读取和命令执行。

这三个验证都无需 LLM；SDK Native 与 SDK Tool Bridge 是两条
**独立运行路线**，不是同一个 SDK Session 已经跨两路迁移的证明。
完整 Agent Runner、模型驱动 Tool Calling、Skill、Git、LSP、
E2B/Cube 真机和跨 Harness 同 Sandbox Instance 的接力均待验。
也不宣称该 POC 的最小 Docker Provider 是生产级 Sandbox 服务：
内存中的 Lease 表、无任务级持久绑定、无进程重启恢复、无外部
Workspace 恢复或平台实际 Policy/Approval 接口。

SDK Native 优先复用官方客户端，不要在 Harness 中复制官方
SandboxSession 的文件操作、Snapshot、Resume 等机制；工具层
转发仅作为需要共享平台 Sandbox Lease 时的薄适配备选。

### OpenCode 2 + OpenAI SDK 同物理 Sandbox 接力

```bash
docker pull ghcr.io/anomalyco/opencode@sha256:9500f3474188a4b89e165c65fada370dbde5e038cc3b751ed5dcbd27d7620315
python poc/opencode_sandbox/verify_opencode2_sdk_handoff.py
```

这个 POC 使用带限制的 Docker Sandbox：网络关闭、只读根目录、独立
`/workspace` tmpfs、非 root 用户和资源上限。OpenCode 2 的 HTTP
只绑定 Sandbox 内的 127.0.0.1，Basic Auth 密码按次生成，仅在测试中
内存持有，不记录密码、请求鉴权头或容器日志原文。
验证的是 OpenAI SDK 公共 Tool Callback 与 OpenCode 2 原生
Session/FS/Shell API 的可复用性，不是模型 Agent 已经自主完成交接。

## 执行入口

### ① 本机共享 OpenCode HTTP（无需模型密钥）

```bash
python poc/opencode_sandbox/smoke_local_pool.py --sessions-per-project 3
```

创建两个**有独立首个提交**的临时 Git 项目，启动一个 OpenCode
Server，并发创建/查询 Session，打印单行可机器读取的 JSON。
仅验证 HTTP Session 路由；不会请求模型或运行项目代码；结束时
强制清理 Server 和临时目录。本机环境使用已安装的 OpenCode CLI。

### ② 官方 E2B 模板，真实 Sandbox 内 OpenCode

E2B 提供预构建 `opencode` 模板，可以在 Sandbox 内运行
`opencode serve`，平台通过 HTTP API 使用 Session。此验证
只使用健康检查和 Session CRUD，不调用模型，不进行 Git Push。

```bash
python -m pip install e2b
# 在可信执行环境中配置 E2B_API_KEY，不写入仓库或日志
export OPENCODE_TEST_ALLOW_REMOTE=1
python poc/opencode_sandbox/smoke_e2b_opencode.py --provider e2b
```

仅当明确允许产生 E2B Cloud 资源费用时开启 opt-in。工具结束时
销毁创建的 Sandbox；不要直接将 Sandbox 内的 OpenCode HTTP
服务无鉴权地公开到互联网，示例使用临时 Basic Auth 密码。

### ③ CubeSandbox：必须使用企业内网自建模板

CubeSandbox E2B-compatible 接口允许特定 SDK 操作复用，但
**E2B Cloud 的 `opencode` 模板不是 CubeSandbox 的预置模板 ID**。
先使用不可变 OCI 镜像在 CubeSandbox 注册并验证包含 OpenCode 的
自定义模板（其 HTTP 4096 端口可访问），再配置：

```bash
export E2B_API_URL="https://<private-cube-api>"
export E2B_API_KEY="<trusted-cube-api-key>"
export CUBE_OPENCODE_TEMPLATE_ID="<registered-cube-template-id>"
python poc/opencode_sandbox/smoke_e2b_opencode.py --provider cube
```

此脚本是 E2B Python SDK 兼容性探针；如果 Cube 当前 SDK/协议
不接受该调用，应报告 **UNSUPPORTED/GAP** 并评估 Cube 原生 SDK，
不可称为已通过，也不应绕过 TLS 或安全认证。E2B 保留为协议兼容
测试目标，不改变 CubeSandboxProvider 的生产候选地位。

## 下一阶段的不可豁免门禁

| Gate | 验收标准 |
|---|---|
| H1 | 真实 E2B/Cube 下 OpenCode 文件读/改、Git、Shell、取消、Session 恢复与完整 Evidence 链 PASS |
| H2 | 共享 Runtime 进行 **跨 Workspace 并发文件写入** 的正反对照，零串写；不支持的 Tool 必须明确拒绝 |
| H3 | 证明 bash、read、write、edit、glob、grep、git、LSP、插件及 Skills 脚本等宿主机执行面没有遗漏出口 |
| H4 | Server A 退出后 Server B 能基于持久 Session/Workspace 状态在已声明能力边界继续；不把缓存当权威状态 |
| H5 | 相同负载实测两种拓扑：OpenCode-in-Sandbox 与共享 OpenCode + remote Sandbox；记录 RSS、CPU、P95、活跃进程和 Sandbox 数量 |
| H6 | 100/1000 空闲 Session 不应线性创建进程或 Sandbox；Coding 执行仍遵守独立的 Sandbox 安全边界 |
| H7 | OpenCode、OpenAI Agents SDK、MAF 均声明 Sandbox Capability；同一业务任务的兼容阶段可复用同一 Lease，不同授权 Scope 无法串读写 |
| H8 | OpenAI SDK 原生 E2B/Cube 与平台 SandboxProvider 的创建、挂载、取消、Evidence、恢复语义必须通过同口径 Conformance；不要求各 Harness 采用相同 SDK |

若无法通过官方公开扩展点把 **全部** OpenCode 文件/执行入口
安全路由到外部 Sandbox，则应继续采用 **OpenCode-in-Sandbox
+ 生命周期池化/暂停**，而不是为降低 RSS 放弃隔离，或修改
OpenCode 内核。

## 参考

- [E2B 官方 OpenCode 集成](https://docs.e2b.dev/agents/opencode)
- [OpenCode Server](https://opencode.ai/docs/server/)
- [OpenCode SDK](https://docs.opencode.ai/docs/sdk/)
- [OpenCode Custom Tools](https://docs.opencode.ai/docs/custom-tools/)
- [CubeSandbox Quickstart](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/quickstart.md)
- [CubeSandbox Volume 兼容边界](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/volume-plugin.md)
- [OpenCode 无提交 Git Project ID 问题](https://github.com/anomalyco/opencode/issues/15192)
- [OpenAI Agents SDK Sandbox Agents](https://openai.github.io/openai-agents-python/sandbox_agents/)
- [OpenAI Agents SDK Sandbox clients](https://openai.github.io/openai-agents-python/sandbox/clients/)
