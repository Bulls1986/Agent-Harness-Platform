# OpenCode 2 × Cube 真实准入复验（2026-10-10）

> 前置 RCA：[2026-10-09 Template 故障](INCIDENT_20261009.md)。
> 本报告为**真实 WSL2 KVM Cube MicroVM 和 POC 功能证据**，非生产准入 ADR。

## 解决的两层故障

1. 先前停在 `BUILDING_EXT4 40%` 的 Job `ec70a828...`，确认是 WSL/systemd 关闭触发 `context canceled`，以及 TemplateCenter 向 CubeMaster 的 FAILED 回调被中断。**控制面过期 RUNNING 对账仍属 Cube 外部依赖缺口**，与本次 Coding Guest 模板无关。
2. 原 OpenCode 2 组合镜像（`sha256:825b61c967...`）在完整构建 EXT4 和分发之后，首次 Cubelet/Shim 收到 10 秒 VM Event Timeout；第二次同镜像 VM Agent 在约 3 秒内正常 Ready，但基础镜像自带的 **Jupyter Code Interpreter** 在 `GET /api/status 200`、`POST /api/sessions 201` 后未完成 FastAPI lifespan，Cubelet 端口验证 30 秒后 `PortBindingFailed / context deadline exceeded`。
3. 对照控制：同一 Cube 节点、相同创建参数的原生 `sandbox-code` 源镜像（本地 Registry 标签 `ahp-base-control:sandbox-code`）成功构建 READY（Job `d1ecbf4a-21a0-4b55-807a-7f2144592f5d`，Template `tpl-ae9b7349dfbf48ff92e79d6c`），证明 Cube 本身可冷启动；旧官方已 READY 的 Base Template `tpl-5e50f4d999c04bdc80b07609` 也通过真实 Shell/Files/Reconnect。
4. 独立 WSL Docker 冷启动对照：原版 Python Interpreter 的 `/health` 约 26.3 秒，OpenCode 组合镜像约 17.1 秒，均需要额外启动 Jupyter 和创建默认内核。**不能断言 OpenCode 二进制阻塞了 Jupyter；确定的是该重型服务增加了模板就绪时间与不确定性，且 Coding Sandbox 不依赖它。**

## 最小修复：保留 envd，换成轻量受信任 Probe

将 OpenCode 专用 OCI Guest `CMD` 更改为 `/opt/ahp/start-cube-opencode.sh`，只启动：

- 原生 Cube `/usr/bin/envd -port 49983`，提供 Commands/Files 接口；
- `health_probe.py` 监听 `0.0.0.0:49999/health`，**只在本机 TCP 49983 确实可连时返回 200**；
- OpenCode 2.0.24 可执行文件和私有 musl Loader/动态库保留不变；V2 Server **按需经真实授权 Cube Lease 的 Shell 启动 4096**，无需在 Guest 启动时额外创建 Jupyter 内核。
- 这是 Coding 专用 Guest Profile，不应冒称保留官方完整 Jupyter Code Interpreter API。未改全局 TLS 信任与宿主机其他容器。

独立 Docker 镜像 `ahp-opencode2-cube:lightprobe` 构建 **PASS**（image ID `845be110fe13`）；隔离容器 `/health 200` 约 **1 秒**，`opencode v2.0.24` PASS。镜像经本机 POC OCI Registry `localhost:5000/ahp-opencode2-cube:2.0.24-lightprobe` 推送成功，Manifest digest `sha256:845be110fe13b1a08fe302cf975ed086e3478b2d996118fad6389ff79ba3d386`。

## 真实 Cube Template → OpenCode V2 工具链 PASS

- CubeSandbox `v0.7.2`，正式 `cubesandbox==0.7.0` 原生 SDK；
- Cube Template **`tpl-aacac99e38bf46e68ecd2f1f`**，Job `75309ed6-bfa0-420b-b0cc-19adafc937ff`；
- **真实 `READY`**：OCI pull **19/19 layers / 196MiB**，EXT4 RootFS Artifact READY，分发 **1/1 READY**，`CREATING_TEMPLATE` 后最终 READY；
- `Sandbox.create(template=...)` 真实 MicroVM 创建 **PASS（约 4.31 秒）**；
- `commands.run('opencode --version')` 输出 `opencode v2.0.24` **PASS**；
- Cube Native `files.write/read`、Shell，`Sandbox.connect(sandbox_id)` 读取同一文件、`Sandbox.kill()` **PASS**；
- **真实 OpenCode 2 V2 Server** 经 Cube Shell 在同一 VM 内按需启动，`POST /api/session` 创建 **2 个独立 V2 Session PASS**，`GET /api/fs/read/from_provider.txt` 从同 Cube Workspace 读到预写文件 PASS（文件 API 返回纯文本，不能强行 JSON 解码）；
- `POST /api/shell` 执行 Shell 将 `v2-shell-ok` 写入 Workspace，Cube Native SDK 在同 Sandbox 读取相同内容 **PASS**；
- 随后 **Pydantic AI Agent `@tool_plain` + FunctionModel** 和 **OpenAI Agents SDK 公共 `@function_tool`** 都从上述同一 Cube Sandbox 读取 OpenCode V2 Shell 写入的文件：**LIVE LIMITED PASS**，1 个 MicroVM，没有托管模型调用；
- 可重复入口：`poc/opencode_sandbox/verify_cube_opencode2_v2_live.py --live --template tpl-aacac99e38bf46e68ecd2f1f`，必须显式设置可信 `CUBE_API_URL` / `CUBE_NATIVE_LIVE_CONFIRM=1`，本地开发可指向 127.0.0.1；`--live` 外不会创建 Cube 或产生外部成本。

### 最后一个 Coding 工具链门禁

上述 READY 镜像**尚未内置 Git**，原 SDK Shell 的 `command -v git` 无结果；因此早期 Git 仍 `NOT TESTED`，不能声明 Coding 工作流验收完成。Debian 12 `apt-get install --no-install-recommends git` 已在独立 Docker 临时容器中真实安装，输出 `git version 2.39.5`；新的 OCI Dockerfile 将 Git 烘焙入镜像，`--require-git` 复验必须完成 `git init/add/commit/log`，**验证结果以新模板真实 Live 证据为准**。

## 2026-10-10 Git-enabled 最终模板与完整功能验收（最新）

Git 已固定写入专用 Cube Guest OCI（Dockerfile `apt-get install --no-install-recommends git`，真实版本 `git 2.39.5`），不依赖在运行中再装包。新的本地 OCI 镜像 `ahp-opencode2-cube:lightprobe-git` 构建 **PASS**（image ID `9e4bde62fad2`）；Registry Push Digest `sha256:9e4bde62fad22f2b22a2bd858ec865e403caccead740d113afc8c9a9e89e284f`。

- Cube Template **`tpl-363306ce3b21432cb1ae6536`**；Job `c835c0cd-9cf6-4628-9e8e-c4730a3873c0`：**READY**，Pull **20/20**（225.8 MiB）、RootFS EXT4 Artifact READY、节点分发 1/1 READY。
- 严格真实复验：`CUBE_TEMPLATE_ID=tpl-363306ce3b21432cb1ae6536 ... python -B poc/opencode_sandbox/verify_cube_opencode2_v2_live.py --live --require-git`；创建一个实际 Cube MicroVM，Git `init/add/commit/log` 完成且最后提交信息为 `cube-git-proof`。
- 同一次运行中，OpenCode 2 V2 2 个不同 Session、FS read、Shell write、Cube SDK reconnect、Pydantic AI Agent 公共 Tool、OpenAI Agents SDK 公共 FunctionTool、finally kill 全部真实 **PASS**，零托管 LLM 访问。实际 JSON：

```json
{"cube_native_reconnect":"PASS","e2b_native":"NOT_TESTED","git":"PASS","model_calls":0,"openai_public_function_tool":"PASS","outcome":"PASS","pydantic_agent_public_tool":"PASS","real_microvms":1,"scope":"live_cube_native_opencode2_v2","v2_fs_read":"PASS","v2_sessions":2,"v2_shell_file":"PASS"}
```

**裁定：ARCH-TODO-027 的 Harness-in-Cube 最小功能门禁（READY / 2 Session / FS / Shell / Git / 跨 Runtime 同 Sandbox 公共 Tool）为 LIVE PASS，允许进入集成开发。** 尚未通过生产级平台授权 Scope、Lease/Fencing、Git 等全部潜在 Host 绕过入口的系统性负例、真实模型 Agent Loop、平台统一 Typed Events/Cancel/Receipt 或 Worker 崩溃恢复，不可据此关闭整项生产准入或宣布高密度/安全隔离 PASS。

## 当前准入与依赖边界

- **新增可用性：** Cube 真实 Guest + OpenCode 2 V2 Session/FS/Shell + Pydantic/OpenAI 公共 ToolAdapter 共用一个 Sandbox 能力已通过功能 POC，ARCH-TODO-027 的 Guest Boot/Template READY 与无模型跨 SDK接力部分可收口。
- **仍非生产 GO：** 官方 E2B SDK 与 Cube API 路由和 Data Plane 未完整通过（026）；平台原生 AgentRuntime SPI、Run/Session/Scope/Lease 严格隔离、审计/撤销/非幂等 Tool Receipt/故障恢复未完成（025/028）；宿主机 OpenCode Host 模式的 FS/PTY/Git/LSP/插件透明远端路由仍 NO-GO；完整真实 LiteLLM 模型 Agent Loop 未跑。
- 验证环境临时 `localhost:5000` HTTP Registry **仅限隔离本机 POC**；不能用于生产镜像分发，生产需可信 HTTPS/认证 Registry。
- 协作范围清晰：Cube 自身 Kernel/VM/Containerd/TemplateCenter 对账、外部 DNS/TLS、底层备份等由 Infra 提供，不应被本平台 Harness 吸收。
