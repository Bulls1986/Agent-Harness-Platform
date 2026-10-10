# Agent Harness Platform 已验证版本基线（2026-10-10）

> **状态：POC 已验证版本快照 / 集成阶段推荐基线；不是生产 Lockfile，也不是 Accepted ADR。**
> 该文件是版本**唯一人工入口**；结构化事实见 [`poc/compatibility/verified_stack.json`](../../poc/compatibility/verified_stack.json)，复验命令见 [版本门禁](../../poc/compatibility/README.md)。历史实验文档保留原日期及失败证据，不再把“最新版本”当作“当前已验证版本”。
>
> 符合 [Accepted Registry & Versioning Contract](REGISTRY_AND_VERSIONING.md)：**Run 创建时冻结 resolved SDK/Adapter/Runtime/Environment 版本及不可变镜像 Digest**；后续发布仅影响新 Run，不能在恢复时自动切换“latest”。

## 核心判断与冻结表

**技术可行性已满足集成 POC（LIMITED GO）**：单一真实 Cube MicroVM 内 OpenCode 2 多 Session、FS/Shell/Git、Pydantic/OpenAI Tool 接力，官方 E2B 2.40 与 OpenAI Native E2B Client 的真实 Cube 接入；以及平台 AgentRuntime SPI 的有限真实 SDK Run 已验证。**生产仍 NO-GO**；未证明跨 Worker 任务恢复、生产隔离、真实模型 Token Streaming、Receipt 及完整模型 Agent Loop。

| 层 | **已验证版本** | 证据等级与条件 |
|---|---|---|
| CubeSandbox 服务端 | **v0.7.2** | WSL2 KVM 真实 MicroVM、Template READY |
| Cube 原生 Python SDK | **`cubesandbox==0.7.0`** | 真实 create/connect/files/shell/kill |
| E2B 官方 Python SDK | **`e2b==2.40.0`** | 在 `E2B_DOMAIN=cube.app`、独立解析器、可信 CA 下真实 create/files/commands/kill |
| OpenAI Agents SDK | **`openai-agents==0.23.1`** | 搭配 E2B **2.40.0** 真机 Native Client PASS；也通过公开 FunctionTool 和 `Runner.run`（本地模型） |
| OpenCode 2 | **v2.0.24** | Cube Guest 真实 V2 HTTP/双 Session/FS/Shell/Git |
| Cube Guest Git | **v2.39.5** | 真实 Guest `git init/add/commit/log` PASS |
| Pydantic AI SDK | **`pydantic-ai-slim==2.54.0`** | 真实 `Agent.run` 本地确定性模型、公开 Tool → Cube PASS |
| Pydantic AI Harness | **`pydantic-ai-harness==0.54.0`** | 已安装的**候选**，并非内置 E2BSandbox/Coder 真实 Cube 通过 |
| POC Python | **3.12** | 实测环境版本；不是生产部署最低版本 |

**必须保留的负例：** `e2b==2.53.1` 连接当前 Cube v0.7.2 的 `POST /v2/sandboxes` 返回 **HTTP 405**，不可自动将 `2.40.0` 升至 `2.53.1`。原版 `2.40.0` 在默认 `e2b.app` + WSL 全局 DNS 下的 `files.write ConnectError` 同样是实测失败；受控 DNS/TLS 修正后的 PASS 不可被复制成其他部署环境默认可用。

## 已验证、可追溯的 Cube OCI 镜像和 Template

| 字段 | **2026-10-10 已通过的值** |
|---|---|
| 本地 Registry 镜像标签 | `localhost:5000/ahp-opencode2-cube:2.0.24-lightprobe-git` |
| **不可变 Manifest Digest** | `sha256:9e4bde62fad22f2b22a2bd858ec865e403caccead740d113afc8c9a9e89e284f` |
| Cube Template | `tpl-363306ce3b21432cb1ae6536` |
| Build Job | `c835c0cd-9cf6-4628-9e8e-c4730a3873c0` |
| 验证状态 | OCI 20/20 Layers、225.8 MiB、EXT4 READY、分发 1/1 READY；MicroVM 功能 PASS |
| Guest 进程 | envd :49983；轻量 /health :49999；OpenCode V2 Server :4096 按 Lease 启动 |

**Digest 代表当次已验证本地 Registry Manifest；Template ID 仅属于此 Cube 部署，不是跨环境标识。** 新部署应使用自己的经认证 HTTPS Registry，并对新 Digest 重新构建、记录 Template ID/Job 和真机 Gate，不能将开发机 `localhost:5000` 或 mkcert CA 作为生产发布物。

当前 Dockerfile 存在明确的**可复现性缺口**：Cube Guest 基础镜像使用 `sandbox-code:latest`，OpenCode 来源仅固定 tag `2.0.24` 而非可移植 Registry Digest，Git 通过 apt 安装、只记录已观测的 2.39.5。因此即便 Dockerfile 未改变，未来重建仍可能生成不同 Artifact；**一旦变化须先重新跑测试并升级版本基线**。不能以版本字符串代替 Digest/Build Provenance。

## 已冻结的兼容组合与复验

1. **Cube 原生调用**：Cube 0.7.2 + `cubesandbox 0.7.0` + Git-enabled Guest Template。真实命令/文件/复连/销毁、OpenCode V2 2 Session、Git、公共 SDK Tool 接力，见 [OpenCode-Cube 真机报告](../../poc/opencode_sandbox/opencode2_cube_template/VERIFICATION_20261010.md)。
2. **官方 E2B / OpenAI Native**：Cube 0.7.2 + `e2b 2.40.0` + `openai-agents 0.23.1` + Cube DNS/可信 CA，真实 create、双 Sandbox 文件隔离、Native exec/aclose，见 [E2B 私有 DNS 真机报告](../../poc/opencode_sandbox/E2B_PRIVATE_DNS_VERIFICATION_20261010.md)。
3. **平台 Run SPI**：`pydantic-ai-slim 2.54.0` + `openai-agents 0.23.1`，真实 SDK `Agent.run / Runner.run` + 本地确定性模型，无托管 LLM，见 [AgentRuntime SPI POC](../../poc/runtime_spi/README.md)。

推荐从仓库根运行：

```sh
python -B poc/compatibility/verify_stack.py            # 默认只读、离线核对文档/镜像基线
python -B poc/compatibility/verify_stack.py --self-test # 校验失败版本、篡改、冲突/缺包场景
# 在对应已安装 Python 虚拟环境下按 *组合* 校验，不需要把不兼容的SDK全装进一个 venv：
python -B poc/compatibility/verify_stack.py --profile cube_native
python -B poc/compatibility/verify_stack.py --profile cube_e2b_native
python -B poc/compatibility/verify_stack.py --profile runtime_spi_sdk
```

**每次升级必走：** 先修改候选版本、在全新隔离 venv 复验，记录 SDK API/版本、真实 Cube 模板与兼容矩阵，替换已验 Digest，并且确认平台 Run 冻结策略和失败恢复语义；**不可先改基线再将验证缺口默认标 PASS**。

目前 **LiteLLM 模型服务端版本、MAF/Temporal Runtime 版本、生产 Ubuntu/Cube 集群规格等没有足够这轮实测证据，不填猜测版本**。它们分别由模型通路、Durable 或运维集成专题记录。

## 仍属于集成与生产门禁

真正的 LiteLLM 模型→AgentRuntime→逐 Token/Tool Typed SSE、可用的 SandboxProvider/ExecutionOwner 绑定与 Scope/Fencing、可信 Tool Receipt/非幂等对账、任务级恢复及 Crash/HITL、Pydantic Harness 内置 E2B、OpenCode 模型执行、跨 Scope Host 绕过负例、安全/高密度/资源/运行成本，见 [ARCH-TODO-025～028](../ARCHITECTURE_BACKLOG.md)。

**结论：** 可以进入平台集成开发；若计划跨团队交付或生产部署，以上真实门禁仍必须通过后再更新 Accepted 状态。
