# CubeSandbox 提供 E2B 兼容能力：专项门禁与实测边界

> 日期：2026-10-09。状态：**主线 POC / NOT GO**。优先级高于共享 OpenCode
> SDK Host 密度测试。此文件记录候选能力，不替代 Accepted Architecture Contract。

> **最新准入裁定（2026-10-09）：** [分级准入报告](../../docs/references/MULTI_HARNESS_ADMISSION_20261009.md)。本文按时间逆序保存原始证据；下面“Cube 未验证 / 未部署”的早期表述是历史状态，不是本轮最终结论。官方 E2B Python 2.53.1 原生创建 405、Cube 原生 SDK 真机已通过，这两项独立记录不得互相覆盖。

## 2026-10-10：官方 E2B 2.40.0 + OpenAI Native Data Plane 真机通过

**之前的 v2.40 `ConnectError` 已按环境问题定位并在真实 Cube 上修复**：WSL 默认 DNS 跳过已有 `~cube.app` CoreDNS 路由，E2B 默认 `E2B_DOMAIN=e2b.app`。在独立挂载命名空间（非全机 DNS 变更）使用既有 systemd-resolved 路由、`E2B_DOMAIN=cube.app` 和可信本地 CA，真实官方 `e2b==2.40.0` `Sandbox.create/files.write/files.read/commands.run/kill` **PASS**；另实测 2 Sandbox 不共享文件内容、`openai-agents==0.23.1` 原生 `E2BSandboxClient.create/exec/aclose` **PASS**。所有客户端均为公开 SDK 无私有 patch，零托管模型调用。

完整准确证据、风险和 CLI：[E2B 2.40 真实验收](E2B_PRIVATE_DNS_VERIFICATION_20261010.md)。**官方 `e2b==2.53.1` `POST /v2/sandboxes` 405 仍不兼容；Pydantic Harness 内置 E2B、跨两个 SDK Native `connect(same_id)`、生产隔离及 TLS/DNS 运维尚未验收。** 以下 2026-10-09 关于 v2.40 Data Plane ConnectError 的描述仅为当时未配完整的历史负例。

## 2026-10-09 22:50：OpenCode 2 Cube Template 的 40% / 10 秒启动超时 RCA

**本轮已完成真正的根因验证**，见 [独立事件 RCA 与稳定环境复测](opencode2_cube_template/INCIDENT_20261009.md)。首次 Job `ec70a828...` 在系统关闭时 CubeTemplateCenter 输出 `native export layer 11 ...: context canceled`，向 CubeMaster 发送 `FAILED` 的请求同样被取消，导致状态被保留为 `RUNNING/BUILDING_EXT4/40%`；`CAP_MKNOD/xattrs` 是通用错误 Hint 而非实测权限根因。持续 WSL 保活时同一个 OCI 镜像的新 Job `4be59892...` 通过 EXT4 RootFS Artifact READY / 1/1 分发 / 85% 创建阶段，证明镜像 layer 能正常导出。然而其 Cubelet/containerd-shim 在 VM 启动事件等待 10 秒后 `Receive event timeout after 10000ms`，最终 **FAILED / CREATING_TEMPLATE**；VMM 有 `Booting VM` / kernel & vCPU 启动记录，Guest Ready 链路原因仍未知。**Template READY 与 V2 Session 尚无通过证据，ARCH-TODO-027 仍 OPEN**。

**OpenCode OCI Registry Push 最新证据：** 已改用国内镜像站取得官方 Registry v2 容器，独立 WSL Docker 运行本机 `127.0.0.1:5000` 私有 POC Registry，`docker push localhost:5000/ahp-opencode2-cube:2.0.24` 返回 Digest `sha256:825b61c967d09e94e9fb42fdc192796952a03842ec6fc3e9dff88f0d9e70679c`，**REGISTRY PUSH PASS**。但 CubeMaster 是否从 HTTP Registry 拉取成功、Template 是否 READY 仍需真机结果，不得提前升级 027 准入。

## 2026-10-09 最新增量：E2B 2.40.0 真实 Control Plane 创建已通过，Data Plane 仍 FAIL

在新独立 WSL Python venv `/root/ahp-cube-demo/e2b-compat-v240` 安装官方 `e2b==2.40.0`，保留原环境 `e2b==2.53.1` 不变。调用新 `poc/opencode_sandbox/verify_cube_e2b_basic.py --live`：通过本地合成、满足 SDK 格式的测试 Key，**先等待 Cube API 3000 / TemplateCenter 8090 / CubeEgress 9091 全部返回 HTTP 200**，实测日志：

```text
CUBE_HEALTH_PENDING [3000, 8090, 9091] elapsed 0
CUBE_HEALTH_PENDING [9091] elapsed 20
ALL_CUBE_DEPENDENCIES_HEALTHY
{"failed_stage":"files","failed_type":"ConnectError","model_calls":0,
 "outcome":"FAIL","scope":"live_cube_official_e2b","sdk_version":"2.40.0"}
```

这说明 `Sandbox.create` **实际返回了非 Debug 的 Sandbox 句柄并通过测试检查**，因此可将 `e2b==2.40.0` 的 Cube Control Plane **创建阶段标记为 LIVE LIMITED PASS**。下一项 `sb.files.write(...)` 经 E2B 自己的 envd Data Plane **失败 `ConnectError`**，`commands.run` 未运行；还不能宣布 E2B SDK 整体兼容。这与之前 `e2b==2.53.1` 的 `POST /v2/sandboxes` HTTP405 是**不同的失败阶段**。

后续需查 E2B 2.40 `envd_api_url` 的 `E2B_DOMAIN` 默认 `e2b.app` 与 Cube 预期 `*.cube.app`、Wildcard DNS/CoreDNS、CubeProxy 域名 TLS 和本地 CA。直接在 WSL `getent ahostsv4 49983-example.cube.app` 无结果（域名示例不是实际 Sandbox 的真实路由，不可推断所有域名故障），说明至少需要专门的 Data Plane 解析和连通性检查。**不修改全机 DNS、不开 TLS 验证、也不修改 E2B SDK 私有实现来伪造 PASS**。

### OpenCode 2 OCI 镜像 Build Gate 真实结果

第二次 ABI 改造后独立 WSL Docker **SUCCESS**：`docker build ... -t ahp-opencode2-cube:poc`，日志 `opencode v2.0.24`、`Successfully built 825b61c967d0`；组合镜像包含 Cube Guest envd/probe 和 OpenCode 所需私有 musl Loader/库。**OCI Build/ABI Gate PASS**，但真实 Cube Template Registration、READY、MicroVM 内 OpenCode V2 Server/Session/FS/Git **未验收**。

尝试获取独立小型 OCI Registry 镜像 `registry:2` 以进行本地 Registry Push 时，WSL Docker 到 Docker Hub `registry-1.docker.io:443` 连接被对端重置；本机 Windows Docker Desktop 也没有缓存该镜像，所以尚未建立可靠可取回的 OCI Registry。当前 `create-from-image` 不能仅靠 WSL Docker 的本地 image ID 保证 CubeMaster 可获取。**不是 OpenCode Runtime 被证伪，仅是镜像供应链/Registry 准入未完成**。

## 2026-10-09 晚间：官方 E2B Python SDK 旧接口矩阵（本次新增证据）

本轮在**隔离的 WSL2 Python venv**，而非覆盖工作环境原有 `e2b==2.53.1` 的前提下，下载/安装并检查以下真实官方 PyPI 轮子。Cube v0.7.2 仍是本机 MicroVM Backend；后端启用 auth_enabled=false。

| SDK | 创建接口/配置观察 | 本次真实尝试结论 |
|---|---|---|
| `e2b==1.0.5` | SDK 生成客户端含 `POST /sandboxes`，但公开 `Sandbox.create` **不存在** | 安装 PASS；当前 `Sandbox.create` 平台调用形状 **INCOMPATIBLE**（AttributeError），不是 Cube API 失败 |
| `e2b==2.0.0` | SDK 含 `POST /sandboxes` 和 `Sandbox.create`，但 `ConnectionConfig` **不读取 `E2B_API_URL`**；未设置 `debug` 时默认访问云端 API | 第一次受 Cloud TLS 证书限制（未请求 Cube），`debug=True` 得到固定 **`debug_sandbox_id`**，Files 连接拒绝；**是假句柄，不是实际 MicroVM PASS** |
| `e2b==2.40.0` | `POST /sandboxes` + `Sandbox.create`，`ConnectionConfig` 确认读取 `E2B_API_URL` | 使用随意占位串时客户端在发包前拒绝：`AuthenticationException` 要求 `e2b_`+hex 格式；随后按格式传入本地**合成测试值**的一次重试，冷启动期间 3000/8090/9091 未同时健康，返回 `BLOCKED_CUBE_SERVICE`，未进入 SDK 创建。**LIVE 兼容结果仍 NOT VERIFIED** |
| `e2b==2.53.1` | 实测调用 `POST /v2/sandboxes` | Cube v0.7.2 实际响应 HTTP 405；同一组合下 OpenAI `E2BSandboxClient` 也创建失败，**LIVE FAIL** |

**准入结论：** 现有真实证明仍为 `cubesandbox==0.7.0` **Cube Native SDK** 及公开 Pydantic/OpenAI Tool Adapter 在 Cube v0.7.2 上成功；并未证明任何上述官方 E2B Python SDK 完成真实 Create/Files/Commands/Kill。下一次要在**同一 WSL 持续进程中**等待三个控制/代理健康服务后用 `e2b==2.40.0` 运行新脚本 `verify_cube_e2b_basic.py --live`（本地合成但格式合法的测试 Key，禁止泄露真实凭据）。不得把接口签名/Debug 假句柄/健康预检 PASS 提升为 CUBE-1。

## 2026-10-09 晚间：OpenCode 2 专用 Cube OCI 模板进展

- 已通过宿主机 **Docker Desktop 现成** `ghcr.io/anomalyco/opencode:2.0.24`（image ID `sha256:9500f3474188a4b89e165c65fada370dbde5e038cc3b751ed5dcbd27d7620315`）`docker save`，成功导入**独立 WSL Ubuntu Docker daemon**。源宿主机 13 个运行容器未停用、未清理。归档暂存于 `E:/workspace/opensource/cube-poc-cache/`，不作为仓库源码。
- WSL Docker 独立拉取 `cube-sandbox-int.tencentcloudcr.com/cube-sandbox/sandbox-code:latest`，Digest `sha256:743d264fad8c9dc9a49f07e931166d24d025363360ae770ca4b70e3f19540944`。OpenCode 2.0.24 OCI 中实际二进制 `/usr/local/bin/opencode`（204023344 bytes），源镜像 Alpine 3.24.2。默认 Cube guest 是 Debian/glibc。
- 新增候选 `poc/opencode_sandbox/opencode2_cube_template/Dockerfile` / README：基于 Cube 官方 guest 保留 envd/probe 49983/49999，添加 OpenCode binary，准备 4096 V2 服务端口；镜像 build 时执行 `opencode --version` 的 ABI 安全门禁。
- 初次构建报 ARG 范围错误，已修正；随后实测 COPY 成功但 guest 中 `opencode --version` 返回 `/bin/sh: ... not found` (127)。`ldd` 明确源二进制依赖 Alpine musl 动态加载器 `/lib/ld-musl-x86_64.so.1`、`libstdc++.so.6`、`libgcc_s.so.1`。已使用**独立库路径与 OpenCode 专用 wrapper**修正 ABI，避免污染 Cube Debian envd 的运行库；随后 WSL Docker **真实 build PASS**：`RUN /usr/local/bin/opencode --version` 输出 `opencode v2.0.24`，成功构建本地 OCI image `ahp-opencode2-cube:poc`（image ID 前缀 `825b61c967d0`）。**这是 Build/ABI Smoke PASS，不是 Cube Template READY、OpenCode V2 Session PASS**。
- Cube 官方 `examples/opencode-plugin-sandbox` 已通过其 GitHub 仓库源文件独立审查：该方案仅经 `tool.execute.before` 重定向 `bash`，**每次 Bash 调用新建一个 MicroVM**，而 `read/write/edit` 仍访问 Host，文件在两边不一致；并存在不稳定 Session 键、锁超时无锁继续、TTY/host tool 绕过限制。因此可作为 `bash` 有限隔离参考，**不满足 Session 持续挂同一 Sandbox 和编辑/执行共享 Workspace 的核心门禁**。OpenCode 2 主方案仍为 **Harness-in-Cube**，直到其所有 Host 执行路径能安全远程路由。
- 下一门禁：组合 OCI 的 build/version PASS，可信 registry 可取回 OCI digest，Cube `tpl create-from-image` + Template READY，真实 MicroVM 内认证 V2 Server、多 Session FS/Shell/Git 与同 Sandbox 的 Pydantic/OpenAI 接力。缺任一真实证据都保持 `ARCH-TODO-027 OPEN`。

> **Session 绑定门禁补充**：每个需隔离执行的 OpenCode 2 Session
> 必须由平台映射到经 Policy 授权的 Cube Sandbox Lease；
> 绑定映射与 E2B SDK 创建/连接分属两层。前者单元测试 PASS，
> 后者真实 Cube 未验证。OpenCode 2 Tool Transform、Shell Hook 等
> 不应被理解为自动覆盖 FS/PTY/Git/LSP/插件等全部 Host 入口。

> **新增执行路由夹具：**
> `cube_e2b_session_adapter.py` + `verify_cube_e2b_session_routing.py`。
> 使用公开 `E2B Sandbox.connect(sandbox_id)`/commands/files 调用形状；
> 注入 Fake E2B 实例完成 2 Session/2 ID、错租约拒绝、绑定重建后继续读。
> **OFFLINE MOCK PASS ≠ CUBE LIVE PASS ≠ OpenCode Native Tool 全接管。**

## 2026-10-09 晚间：Pydantic Agent Tool Loop → Cube Native → OpenAI Tool 真机接力

新增 `poc/pydantic_harness/verify_cube_native_agent.py --live`：在真实 Cube v0.7.2 上使用 Pydantic AI Agent + `FunctionModel`（无托管模型调用），**一个 Agent 实例、两个 Run、六次实际公共 Tool 调用、同一个 Cube MicroVM**，写/读/Shell 复用同一 Workspace；OpenAI Agents SDK `FunctionTool` 随后读取文件，**LIVE LIMITED PASS**。Cube Native Provider API 通过公开工具 Adapter 调用，未 monkey patch SDK。**Pydantic AI Harness 内置 E2BSandbox/Coder、OpenAI 原生 E2BSandboxClient、OpenCode 2 Cube 及跨 Scope 生产隔离仍未通过**，不能替代下方 E2B Native HTTP 405 负例。

## 2026-10-09 17:xx：OpenAI Native E2B / OpenCode 2 真机门禁（失败证据）

- Cube API 3000、TemplateCenter 8090、CubeEgress 9091、CubeMaster、Cubelet、CubeProxy 均检查为 healthy；同一 Cube Template 元数据与本机副本 READY。真实 Cube 原生 SDK 创建可正常运行。
- 官方 **e2b==2.53.1** 的 `Sandbox.create(template=...)` 在 Cube v0.7.2 实际调用得到 `SandboxException(status_code=405)`。检查该版本安装包的公开调用流程，`SandboxApi._create_sandbox` 调用 `post_v2_sandboxes.asyncio_detailed`，对应 `POST /v2/sandboxes`；而当前 Cube 原生 SDK 0.7.0 创建走 `POST /sandboxes`，Cube OpenAPI 的 `/v2/sandboxes` 只暴露 GET。属于**E2B SDK 版本与 Cube 控制面协议不兼容**，不是 KVM/MicroVM 故障。不能把 Cube Native 成功计入 CUBE-1 官方 E2B SDK PASS。待验证官方明确支持的 E2B SDK 版本或经平台 SandboxProvider 的薄适配，不采用 SDK 私有猴子补丁。
- **openai-agents==0.23.1** 原生 `E2BSandboxClient.create` 单独在真实 Cube API 调用，堆栈穿过 SDK `agents.extensions.sandbox.e2b` 和 `e2b.sandbox_async.sandbox_api`，同样在创建时得到 `e2b.exceptions.SandboxException: 405`，**CUBE-3 Native FAIL（组合版本）**。先前基于 Cube 原生 SDK 的公开 `FunctionTool` 桥接仍 PASS，不可与原生 E2BSandboxClient 混淆。
- **OpenCode 2 真机前置：** 在同一个已 READY 的 `sandbox-code` 模板中创建真实 Cube Sandbox `c82bb1411f404c24a7a86703f5ff182b`，读取发行版为 Debian 12 x86_64，`command -v` 检查表明 `opencode/node/npm/bun/curl/wget/git/tar` 均不存在；Sandbox 已删除。此模板**不能直接执行 OpenCode 2**，必须先构建包含 OpenCode 2 和 Cube envd/probe 的 OCI Template，随后再测 V2 HTTP Session、FS、Shell 与同 Cube 的 OpenAI Bridge 接力。不能把“Template 缺二进制”当作 OpenCode 2 Agent 兼容性失败。
- 结论：本轮 OpenAI FunctionTool→Cube Native 已有功能性 PASS；官方 OpenAI E2B Native 当前版本为**明确协议 FAIL**；OpenCode 2→Cube 为 **BLOCKED（待 OpenCode OCI Template）**；Pydantic Harness 的原生 E2B Backend 因也依赖 E2B SDK，需要针对版本组合专门复验，不能直接沿用此前 Mock PASS。

## 2026-10-09 下午：真实 Cube MicroVM 验证增量（取代下面早间环境结论）

**当前状态：Cube 原生 SDK 的真实 MicroVM/命令/文件/复连与 OpenAI SDK FunctionTool 桥 PASS；官方 E2B SDK Native 和生产选型仍 NOT GO。**

- 复用了单独的 WSL2 Ubuntu / CubeSandbox v0.7.2 环境。`/data/cubelet` 是 16 GiB XFS (`/dev/loop2`)，背后文件 `/root/ahp-cube-demo/cubelet-demo-16g.xfs`；嵌套 KVM 正常。未停止或清理原有 Docker Desktop 13 个运行容器。这个容量仅足够最小 Demo，**不代表满足官方建议的 50+ GiB 生产磁盘需求**。
- Cube Control Plane 的 `cube-api`、`cubemaster`、`cubelet`、`cube-proxy`、`cube-templatecenter` 可运行；`GET http://127.0.0.1:3000/health` 返回 HTTP 200（首次无 Sandbox 时返回 `{"status":"ok","sandboxes":0}`），Ubuntu 内 MySQL/Redis/MinIO 运行健康。WSL 临时进程结束会使发行版退出并停止服务；务必使用同一个存活的 WSL 环境验证，不以服务曾经启动推断当前仍存活。
- 官方 `sandbox-code:latest` OCI 镜像成功构建为模板 `tpl-5e50f4d999c04bdc80b07609`；首次构建 Job `7f2a790a-f1b3-4cf2-9e03-909e2729e812` 为 READY，镜像 Digest `sha256:467494c38f3c335e42d590e23d5cbb00dc15c2627c9da4f7e7f3bd9f4ec18c5e`。曾遭遇重启时 TemplateCenter `127.0.0.1:8090` 尚未就绪，Artifact 代理返回 502，CubeMaster 拒绝创建（`130400: template has no ready replica`）；一次重同步在 CubeEgress `9091` 尚未就绪时因 `PortBindingFailed / context deadline exceeded` 失败。**在 3000/8090/9091 健康后**，再次通过官方 `tpl redo` 恢复该模板，Job `c8e125ae-4a87-42d9-84f9-e1f5edca3fa2` 为 READY。故要改进服务启动顺序与模板副本健康检查。
- 官方 `cubesandbox==0.7.0` 原生 SDK **真实调用** `Sandbox.create`，得到 Sandbox ID `a258e4a2feb34e5c821e385740bdcce2`；`commands.run` 返回 `cube-native-ok`，`files.write/read` 返回 `cube-files-ok`，最后 `kill` 完成。独立第二次 Sandbox 验证同 ID 的 `Sandbox.connect(sandbox_id)` 可由新的客户端句柄继续读取、写入现有文件，并已删除 Sandbox。此复连是**运行中重连**，不是 pause/resume 或灾难恢复。
- `openai-agents==0.23.1` 通过官方公开 `@function_tool` 与 `FunctionTool.on_invoke_tool` 回调，实际读取同一 Cube Sandbox 文件，再由 Sandbox Shell 修改并由 FunctionTool 读取更新后的内容，PASS；无模型/无 Agent Loop，**不等于 SDK 原生 E2BSandboxClient**。
- Ubuntu 独立 Python venv 已安装 `e2b==2.53.1`、`openai-agents==0.23.1` 和 `cubesandbox==0.7.0`。官方 **e2b** Python SDK 的 `Sandbox.create`/命令/文件/销毁以及 OpenAI 原生 E2BSandboxClient 的 Cube 兼容性**尚未实测**，不能将 Cube 原生 SDK 成功等同于 E2B SDK 完全兼容。
- 可复验的最小功能性夹具：`poc/opencode_sandbox/verify_cube_native_live.py`，不带参数只执行配置预检；需要真实 Cube 时显式 `--live`、`CUBE_NATIVE_LIVE_CONFIRM=1`，可选 `--openai-function-tool`，测试中只建一个 Sandbox 并在退出时清理。测试环境还需可信 CA 和 CubeProxy 访问配置。
- **脚本复跑状态：** 独立分段执行的上述 Native 与 FunctionTool 真实调用 PASS；新增脚本的首轮串行复跑遇到 WSL API 已退出（ConnectionError），随后同进程启动+固定等待 45 秒的复跑在 CubeEgress 9091 未就绪时被预检挡下。因此新增脚本的整套 Live 回归本轮**未获得 PASS**，已在脚本内增加 3000/8090/9091 就绪门禁；这是需要继续解决的启动编排问题，而不是已执行的原生 SDK 功能调用失败。

**门禁：Cube MicroVM Native Control/Data Plane（单实例）PASS；同 Sandbox ID 新连接 PASS；OpenAI FunctionTool 实验 PASS。CUBE-1 官方 E2B SDK、CUBE-2/3 原生多 Harness、CUBE-4/5 生命周期与恢复、CUBE-6 安全隔离、CUBE-7 密度仍未满足，生产 NOT GO。**

---
## 目标不是让各 Harness 自建 Sandbox

`Agent Runtime SPI → SandboxProvider SPI → CubeSandbox E2B-compatible API`。
OpenCode 2、OpenAI Agents SDK、MAF 应共享 Sandbox 的模板、Lease、
执行隔离、Workspace Binding、暂停/恢复及资源池，而不是共享不安全的
文件系统或统一底层 SDK 内部结构。无执行需求的 Agent 不申请 Sandbox。

## 当前可核实的 Cube 官方能力及其限制

| 能力面 | 官方公开资料 / 兼容性判断 | 本项目状态 |
|---|---|---|
| E2B Control：创建/删除 Sandbox | CubeAPI E2B-compatible；设 `E2B_API_URL` 与 Cube Template | **Cube 原生 SDK 创建/销毁 PASS；官方 E2B SDK 未测** |
| E2B Data：`commands.run`、`files.read/write` | CubeProxy/envd 提供 E2B-style Data Plane；需代理 DNS、TLS/证书、envd 端口 | **Cube 原生 SDK 真机 PASS；官方 E2B SDK 未测** |
| `opencode 2` 在 Cube 模板中运行 | 必须自建含 OpenCode 2 的 OCI 模板；同时满足 Cube envd/Probe，不可把 E2B Cloud 模板 ID 原样复用 | **待真实 Cube** |
| OpenAI Agents SDK 原生 `E2BSandboxClient` | Cube 官方有集成示例，但其指南明确提到 root/streaming/SSL 等运行时兼容补丁；不能等同于零补丁 PASS | **未证明零补丁兼容** |
| MAF Tools + E2B | 可评估透过平台工具/Executor Adapter 交给 SandboxProvider，不能推断 MAF 自带原生 E2B | **待真实 Cube** |
| `Volume` 持久卷 | Cube REST `/volumes` E2B compatible；**官方 E2B Python Volume 客户端不可直接使用**，需 `cubesandbox` SDK 或 REST | **已识别 SDK 兼容缺口** |
| 暂停/恢复、Session 连接、HTTP 端口 | Cube 有对应示例；具体 E2B SDK 版本、域名、证书、代理行为需实测 | **原生 SDK 运行中 reconnect PASS；pause/resume 未测** |
| 跨 Harness 同 Sandbox/Workspace 接力 | Docker 下 OpenCode 2 ↔ OpenAI SDK 限定 PASS；Cube 真机 FunctionTool ↔ Native Shell 有限定证据 | **Cube + OpenAI FunctionTool Bridge PASS（无模型）；OpenCode 2/Cube 和原生 E2B 未测** |

### 适配策略

1. 先以官方 `e2b` Python SDK 完整测试 **最小公共子集**：
   创建、命令、文件、删除。不要写 Cube 私有 API 规避失败。
2. 再用 OpenAI Agents SDK `E2BSandboxClient` 的**公开 API**对同一模板
   运行等价合约。官方 Cube 示例如果仅依赖 monkey patch 或访问 SDK
   `_inner/_sandbox` 私有字段，记录为未达到平台公开扩展点门禁。
3. Volume 明确采用平台 `WorkspaceProvider` 适配 `cubesandbox` SDK/REST，
   不声明 E2B 官方 SDK Volume 全兼容。Persist Workspace 与短时 Sandbox
   生命周期保持分离。
4. OpenCode 2 可先采用 Harness-in-Cube 模式，通过 Cube 标准 Template
   + `get_host`/Port 暴露能力访问 Server；后续另测 Shared SDK Host
   多安全 Scope 的全工具隔离，不以少进程为由取消 MicroVM。
5. 只有同一 Cube Template、同一 Workspace 内容、同一风险级别、
   相同执行操作的 A/B 数据才比较 E2B Cloud 与 Cube 的延迟/资源。

## 历史环境 Blocker（2026-10-09 上午：以下断言由上方下午结果更新）

- **修正早先 KVM 误判：** 未指定 `--device` 时普通 Docker 容器内没有
  `/dev/kvm`，不能据此推断宿主不支持 KVM。Docker Desktop 后端的
  WSL2 中该设备**存在且可以传入容器**；独立 Ubuntu 24.04 WSL2
  `/dev/kvm` 可打开，`KVM_GET_API_VERSION = 12`，
  `KVM_CREATE_VM` 成功，且 `kvm_intel nested=Y`。
  **这证明 KVM 基础 API 可用，不等于 Cube MicroVM 已启动。**
- 独立 Ubuntu WSL2 具备 root、systemd、8 CPU、11 GiB 可见 RAM、
  cgroup v2 CPU 控制器；内核支持 XFS，但目前没有安装 `xfsprogs`，
  `/data/cubelet` 所在路径仍是 ext4，**不能通过官方安装器的 XFS
  前置检查**。
- WSL 根分区显示 951 GiB 虚拟可用，但不能将此视为物理可用磁盘容量：
  已通过 WSL 注册信息确认 Ubuntu 的虚拟磁盘存储于 **E:**；
  `verify_cube_host_readiness.py --backing-path /mnt/e` 真正读到
  约 **43.1 GiB** 物理空闲、存储路径 `ext4`，返回
  `BLOCKED`；`KVM_CREATE_VM`、11 GiB RAM 和 cgroup CPU 均 PASS。
  E: 低于最低 50 GiB 门槛。**不以超配稀疏回环镜像伪造容量**，
  避免影响已有 POC/用户数据。
- 当前有 13 个运行中的 MAF/Temporal/PG 等 Docker 容器。官方
  `dev-env` QEMU 开发虚机默认占 8 GiB RAM；此时 WSL 总内存 11 GiB，
  不宜并行启动，以免现有环境被 OOM 中断。
- 没有 Cube Control Plane、Template、E2B URL 或凭据配置。
- `127.0.0.1:3000`、`13000`、`11443`、`49983` 未监听。
- 官方允许 WSL2 + Nested KVM 用 `dev-env` QEMU VM 创建实际 Cube
  MicroVM；PVM 是供缺 KVM 的独立 Linux 云主机使用，**本机已有
  KVM，无需修改或重启 Windows/WSL 的内核**。
- 已只读下载官方 `online-install.sh` 并检查其 XFS/cgroup
  前置条件；尚未执行安装、未创建卷/虚机、未改 Docker 配置。
- **不能以普通 Docker Server 冒充 Cube / E2B，或把 KVM ioctl
  成功描述成 MicroVM、Sandbox/E2B 实测成功。**

复核入口（WSL Ubuntu 内执行）：

```bash
python3 poc/opencode_sandbox/verify_cube_host_readiness.py --backing-path /mnt/e
```

具备真正空闲的 8 GiB / 50+ GiB Linux 环境及 XFS 后，按官方
[WSL2 Dev Environment](https://docs.cubesandbox.com/guide/dev-environment)
或[裸机安装](https://docs.cubesandbox.com/guide/bare-metal-deploy)部署；
然后先执行 `verify_cube_e2b.py --live --native-sdk`，
再跑 Pydantic `verify_cube_live.py --live`。所有结果仍须单独记录。

## 可复现的正式门禁

```text
CUBE-0  Endpoint/Template/SDK/DNS/CA preflight
CUBE-1  e2b Sandbox.create → commands.run → files.write/read → destroy
CUBE-2  Workspace 内容及同一 Cube Sandbox 的 OpenCode 2 和 OpenAI SDK 接力
CUBE-3  OpenAI Agents SDK E2BSandboxClient 原生 API（无 SDK 私有补丁）
CUBE-4  Cube Volume REST/SDK 持久化 + Sandbox 重建 Workspace 恢复
CUBE-5  pause/resume、取消、超时、Worker A 退出/Worker B 恢复与 Receipt 对账
CUBE-6  两个隔离 Scope 并发访问拒绝；本机宿主机读取与秘密泄漏否定测试
CUBE-7  10/100/1000 Session 与活跃 Sandbox 容量、P95、RSS/CPU、启动回收
```

未满足 `CUBE-1/2/3/5/6` 之前，不得以 Cube 的 E2B 兼容性作为
“所有 Harness 可统一生产接入”的依据。

## 验证入口

使用 `python poc/opencode_sandbox/verify_cube_e2b.py` 执行
**不产生远程资源的 preflight**；显式添加 `--live` 且具备真实 Cube
API、Template、SDK、数据面 Proxy/DNS/可信 CA 后，才真正创建 Sandbox。
测试不调用模型，不访问 GitHub、不会创建永久 Volume。

```bash
# SDK 固定版本，与本地已验证 API Surface 一致
python -m pip install "e2b==2.53.1" "cubesandbox==0.7.0" "openai-agents==0.23.1"

# 安全离线检查：只检查公开 SDK 签名和配置，不访问 Cube 服务
python poc/opencode_sandbox/verify_cube_e2b.py

# 在真正的 Cube MicroVM 部署上运行。由环境或本地机密管理注入：
# E2B_API_URL、E2B_API_KEY、CUBE_TEMPLATE_ID
# 必须确保对 envd 49983 数据面代理、DNS 与 CA 的实际可达性
export CUBE_E2B_LIVE_CONFIRM=1
python poc/opencode_sandbox/verify_cube_e2b.py --live --native-sdk
```

## 模板与网络实际要求

- Cube 模板不是 Docker 的通用 OpenCode Image：必须含 Cube 可启动的
  envd/Agent 基础设施，模板声明 49983 服务和 readiness probe；
  OpenCode 2 / 4096 端口按 Coding Template 需要额外预装、暴露。
- `E2B_API_URL` 是 Cube Control Plane；Sandbox Data Plane 走
  CubeProxy/envd，不能只验证 3000/TCP 可连就认为命令/文件可用。
- 官方示例本地外部访问常需 `*.cube.app` DNS/受信任的 CA 或
  dev sidecar，不能通过关闭证书校验掩盖问题。
- **旧状态，下午已更新：** 本机已经运行真实 Cube MicroVM，并通过原生 SDK 的命令、文件、复连；官方 e2b SDK 和原生 E2BSandboxClient 合约仍未通过。

### 依据（需要随 Cube 发布变化复核）

- [Cube 官方 E2B Python quickstart](https://github.com/TencentCloud/CubeSandbox/blob/master/examples/code-sandbox-quickstart/README_zh.md)
- [Cube OpenAI Agents SDK integration](https://github.com/TencentCloud/CubeSandbox/blob/master/examples/openai-agents-example/openai-agents-sandbox-cube-integration.md)
- [Cube Volume E2B API vs SDK 限制](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/volume-plugin.md)
- [Cube Bare-metal KVM deployment](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/bare-metal-deploy.md)
- [Cube PVM deployment](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/pvm-deploy.md)
