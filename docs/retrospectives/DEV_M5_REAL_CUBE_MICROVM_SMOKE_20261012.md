# DEV-M5 · 真实 CubeSandbox MicroVM 最小开发 Demo（2026-10-12）

## 验证结论

**真实 Cube MicroVM 本机 SDK 生命周期子切片 PASS**：在 Ubuntu 24.04 WSL2 / x86_64 上复用现有的 CubeSandbox CubeAPI、CubeMaster、Cubelet、CubeProxy 与已 READY 的模板，使用官方 `cubesandbox==0.7.0` SDK 两次分别创建真实 MicroVM，写入 Guest 文件，另建 SDK 连接重新连接**相同 Provider Sandbox ID**，读取并逐字节校验原数据，调用 `kill()` 收到成功响应。**不是 Mock/Fake Transport，也不是 Docker 容器冒充 Cube。**

本轮**未验证**：`Harness PG CubeBinding` 对真实 Cube 的完整流程、A/7→B/8 PG Fencing 携带的 Cube 操作、原生 Hatchet Worker A 实际 SIGKILL→独立 B 与 Cube 相同 Workspace 联合测试、Guest/in-flight Fencing、跨 Scope 权限及 Host 隔离、真实 OCI Digest、跨宿主或生产运维。DEV-M5 仍 ACTIVE/OPEN，M9 Production NO-GO。

## 环境误判与排障复盘

先前仅检查 Windows/Docker 的 Cube 容器列表，错误断言不存在可用 Cube 集群。实际 CubeSandbox 一键部署让 `CubeMaster/Cubelet/CubeAPI/CubeShim` **以 WSL 宿主机进程运行**，MySQL/Redis/Proxy 主要由 Docker 管理；因此“无 Cube Docker 容器”完全不等于“无 Cube 服务”。

真实本机自检证据：
- WSL Ubuntu 24.04、x86_64，约 12 GB RAM、磁盘可用约 935 GB；`/dev/kvm` 存在，嵌套 KVM 为 `Y`，root 可读写。
- `GET http://127.0.0.1:3000/health` 实测 HTTP 200（初始 `{"status":"ok","sandboxes":0}`），本机部署确有 `cubemaster`、`cubelet`、`cube-api` 进程；存在多个 `READY` 模板和原生模板副本。
- 原本准备官方 QEMU 开发 VM 的必要性消失：**优先复用现有真实 Cube 环境**，不额外构造第二套基础设施。官方已有本地 QEMU `dev-env` 供从零搭建时使用，但不是本环境的必要前置。
- 首次 Native SDK Create 遇到 `ConnectionRefused`，是 WSL/Cube 服务初始化尚未完成；第二次 `ApiError 130400 / template has no ready replica` 是模板尚未在健康节点就绪。这两次都未创建 Sandbox，不能作为 PASS。确认 CubeMaster、Cubelet、API 与模板节点副本全部 `READY` 后才重跑。
- 原 SDK 测试使用临时专用 Python 虚拟环境，选择**通用官方** READY 模板，所有文件为随机合成文本，不涉及任何内部消费者数据、密钥或业务源码。

## 实际原生 SDK 双次验证

1. 第一次原生 `Sandbox.create(template=...)` 返回 `sandbox_id=6f781bc2555f4fdeb61edfbcee8aab4e`。`Sandbox.files.write/read` 校验一致；`Sandbox.connect(same_id)` 由新 SDK 对象读取原 Guest 文件一致，`kill()` 返回，退出码 0。输出 `PASS_REAL_CUBE_MICROVM_MINIMAL`、`destroyed=true`。
2. 将纯原生 Demo 规范化为 `poc/sandbox/verify_cube_sdk_smoke.py`，要求实际 `CUBE_API_URL`、`CUBE_TEMPLATE_ID`（远端可附 `CUBE_PROXY_NODE_IP`），禁止 Mock/跳过；新连接读取并清理。
3. 使用仓库中的新脚本 **再次实测成功**，`sandbox_id=b4dda9024ea248eaa623e368651ba12a`，输出 `NATIVE_CUBE_CREATED`、`NATIVE_GUEST_FILE_OK`、`NATIVE_CONNECT_ORIGINAL_BYTES_OK` 和 `PASS_REAL_CUBE_MICROVM_MINIMAL`，`destroy_ack=PASS`、进程退出码 0。实际测试通过本地 WebCodex 受控执行环境运行，而不是 GitHub-hosted Runner。
4. 将显式 `dev-m5-cube-live.yml` 工作流调整为**先真实 SDK Smoke，再真实 Harness PG+Cube 集成**。未配置 Cube Endpoint 时的普通 GitHub CI **不会**冒充实机验收；需另行在有可用 Cube 的授权环境运行全项。
5. 普通 `dev-m5-cube-binding.yml` 继续以真实 PG / Fake Cube Transport 做控制层合同回归，并增加 SDK Demo 编译和缺少 Endpoint 时 **fail closed** 测试。这些常规 CI 的绿色仅证明代码与拒绝合同正确，真正 MicroVM PASS 的证据来自前述本地 Cube 实机双次验证。

## 后续验收（不可错误关闭）

- 现有 `poc.sandbox.verify_cube_live` 需接到独立真实 Harness PostgreSQL 并在现有 Cube 上执行完整 `CREATING→ACTIVE→B/8→RELEASING→RELEASED`、文件内容一致、跨 Scope/旧 Owner 拒绝。该集成**尚无成功的实测结果**；不能仅凭本次原生 SDK Smoke 勾选 M5 1.2/2.x。
- 与 PR #72 的真实 Hatchet Worker A 进程 SIGKILL→B 结合，保留原 Provider Sandbox/WorkspaceRef 和 Guest 文件，证明 PG Fencing、SDK Connect、原生 Hatchet Retry 三者联动。
- 验证真正的 Guest Execution/Shell 权限、Host Shell 不回退、取消/Timeout/过期 Owner 后异步请求效果与回收/UNKNOWN。M5 Gate 和 Production GO 仍 OPEN。

## 相关文件

- 真原生 Demo：`poc/sandbox/verify_cube_sdk_smoke.py`。
- 带 PG 的完整实机 Gate：`poc/sandbox/verify_cube_live.py`。
- 人工触发、须提供真实 Cube 连接信息的 CI：`.github/workflows/dev-m5-cube-live.yml`。
- SDK/PG 合同 CI：`.github/workflows/dev-m5-cube-binding.yml`。

仅记录上述非机密运行标识及本地实验结论；不上传企业内部业务消费者细节或代码。
