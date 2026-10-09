# CubeSandbox 提供 E2B 兼容能力：专项门禁与实测边界

> 日期：2026-10-09。状态：**主线 POC / NOT GO**。优先级高于共享 OpenCode
> SDK Host 密度测试。此文件记录候选能力，不替代 Accepted Architecture Contract。

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
