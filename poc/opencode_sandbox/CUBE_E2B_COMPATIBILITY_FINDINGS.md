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

## 目标不是让各 Harness 自建 Sandbox

`Agent Runtime SPI → SandboxProvider SPI → CubeSandbox E2B-compatible API`。
OpenCode 2、OpenAI Agents SDK、MAF 应共享 Sandbox 的模板、Lease、
执行隔离、Workspace Binding、暂停/恢复及资源池，而不是共享不安全的
文件系统或统一底层 SDK 内部结构。无执行需求的 Agent 不申请 Sandbox。

## 当前可核实的 Cube 官方能力及其限制

| 能力面 | 官方公开资料 / 兼容性判断 | 本项目状态 |
|---|---|---|
| E2B Control：创建/删除 Sandbox | CubeAPI E2B-compatible；设 `E2B_API_URL` 与 Cube Template | **待真实 Cube** |
| E2B Data：`commands.run`、`files.read/write` | CubeProxy/envd 提供 E2B-style Data Plane；需代理 DNS、TLS/证书、envd 端口 | **待真实 Cube** |
| `opencode 2` 在 Cube 模板中运行 | 必须自建含 OpenCode 2 的 OCI 模板；同时满足 Cube envd/Probe，不可把 E2B Cloud 模板 ID 原样复用 | **待真实 Cube** |
| OpenAI Agents SDK 原生 `E2BSandboxClient` | Cube 官方有集成示例，但其指南明确提到 root/streaming/SSL 等运行时兼容补丁；不能等同于零补丁 PASS | **未证明零补丁兼容** |
| MAF Tools + E2B | 可评估透过平台工具/Executor Adapter 交给 SandboxProvider，不能推断 MAF 自带原生 E2B | **待真实 Cube** |
| `Volume` 持久卷 | Cube REST `/volumes` E2B compatible；**官方 E2B Python Volume 客户端不可直接使用**，需 `cubesandbox` SDK 或 REST | **已识别 SDK 兼容缺口** |
| 暂停/恢复、Session 连接、HTTP 端口 | Cube 有对应示例；具体 E2B SDK 版本、域名、证书、代理行为需实测 | **待真实 Cube** |
| 跨 Harness 同 Sandbox/Workspace 接力 | Docker 下 OpenCode 2 ↔ OpenAI SDK 限定 PASS，**不是 Cube PASS** | **待真实 Cube** |

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

## 当前环境 Blocker（2026-10-09 重新核验）

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
- 由于本机没有可访问的 Cube MicroVM，此专项状态仍为
  **OFFLINE SDK PRECHECK PASS / CUBE LIVE BLOCKED**。

### 依据（需要随 Cube 发布变化复核）

- [Cube 官方 E2B Python quickstart](https://github.com/TencentCloud/CubeSandbox/blob/master/examples/code-sandbox-quickstart/README_zh.md)
- [Cube OpenAI Agents SDK integration](https://github.com/TencentCloud/CubeSandbox/blob/master/examples/openai-agents-example/openai-agents-sandbox-cube-integration.md)
- [Cube Volume E2B API vs SDK 限制](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/volume-plugin.md)
- [Cube Bare-metal KVM deployment](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/bare-metal-deploy.md)
- [Cube PVM deployment](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/pvm-deploy.md)