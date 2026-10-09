# POC 运行入口（2026-10-09 整理）

这里列出**最短可复验路径**。原有分散脚本及其证据保留原位；本索引不创建另一份架构待办，唯一主清单是 [ARCHITECTURE_BACKLOG](../docs/ARCHITECTURE_BACKLOG.md)。

## 一、无需外部服务：可以在 Windows/Linux 验证

```sh
python -B poc/verify_admission_offline.py
python -B poc/verify_repo_navigation.py    # 检查文档入口与链接
```

脚本依次验证：Cube Native 预检（**无真实 Sandbox**）、Session→Sandbox Scope/Generation Fail Closed、E2B Session 路由 Mock。PASS 表示逻辑/SDK 边界测试已通过，不代表 Cube / OpenCode / Agent Loop 真机准入。

Pydantic 高密度（需依赖）：
```sh
python -B poc/pydantic_harness/verify_offline_density.py
# Linux/WSL / CI，POSIX-only：
python -B poc/pydantic_harness/verify_local_tool_routing_posix.py
```

## 二、自建 Cube 真机（必须显式 opt-in）

环境：隔离 WSL2 Ubuntu，Cube v0.7.2，实际 KVM 和 Cube Template；**本地 Windows Python 不能直接运行 POSIX host readiness 脚本**。

```sh
export CUBE_API_URL="http://127.0.0.1:3000"
export CUBE_PROXY_NODE_IP="127.0.0.1"
export CUBE_TEMPLATE_ID="<existing-template-id>"
export SSL_CERT_FILE="<trusted-local-CA-path>"
export CUBE_NATIVE_LIVE_CONFIRM=1
python -B poc/opencode_sandbox/verify_cube_native_live.py --live --openai-function-tool
# Pydantic AI 真实 Agent Tool Loop（2 Run + 6 Tools）与 OpenAI FunctionTool
# 复用同一个 Cube 原生 Sandbox；不验证内置 E2BSandbox/Coder
python -B poc/pydantic_harness/verify_cube_native_agent.py --live
```

该路径使用 **cubesandbox 官方原生 SDK**：真实 MicroVM / Shell / Files / 重连 / OpenAI FunctionTool；不使用 E2B Python SDK，也不运行完整模型 Agent Loop。

## 三、官方 E2B/OpenAI Native（当前版本已知不兼容）

```sh
# 配置 E2B_API_URL 指向可信 Cube，E2B_API_KEY 使用本地可信配置；
# 同时配置 CUBE_TEMPLATE_ID 和 CUBE_E2B_LIVE_CONFIRM=1
python -B poc/opencode_sandbox/verify_cube_e2b.py --live --native-sdk
# 最小单 Sandbox 官方 E2B Python SDK conformance（不依赖 OpenAI SDK）
python -B poc/opencode_sandbox/verify_cube_e2b_basic.py --live
python -B poc/pydantic_harness/verify_cube_live.py --live
```

当前 Cube v0.7.2 + e2b 2.53.1 的创建接口为 **HTTP 405**，OpenAI E2BSandboxClient 同受影响；Pydantic 的原生 E2BSandbox 同样**不能推断已兼容**，应先修复版本组合或经平台 Cube Native Adapter 用公开执行接口。完整记录见 [兼容专项](opencode_sandbox/CUBE_E2B_COMPATIBILITY_FINDINGS.md)。

> **2026-10-09 晚间实测：** E2B 2.40.0 可在真实 Cube 健康控制面完成 Sandbox.create 并返回非 Debug 句柄，接着 `files.write` 经 Data Plane 发生 `ConnectError`；尚未验收 Commands/Kill/Native OpenAI，因此正式 E2B conformance 仍 FAIL。e2b 2.53.1 创建直接 HTTP 405。建议下一步检查 `E2B_DOMAIN` / `*.cube.app` Wildcard DNS、Proxy/证书；不得停用 TLS 证书校验。

## 四、OpenCode 2 与其他专项

- [OpenCode 2 / OpenAI 对照](opencode_sandbox/README.md)：Docker V2 Server/Session/FS/Shell 双向接力 PASS；共享 Host 原生 Shell 不能按 Session ID 自动转到外部 Sandbox（负例）。
- [OpenCode 2 Harness-in-Cube OCI 模板](opencode_sandbox/opencode2_cube_template/README.md)：组合 Guest 镜像 build 和 `opencode v2.0.24` 实测 PASS；尚未 Registry Push / Cube Template READY / MicroVM V2 Session。
- [Pydantic](pydantic_harness/README.md)：FunctionModel 与 POSIX 本地 Workspace；SDK Mock Ref Reconnect。
- [MAF](maf/) / [Temporal](temporal/)：已有 POC-A/C 验证不迁移、不删除。
- 真正的 OpenCode 2 **Cube** 验证需专用 OCI Template；默认 sandbox-code 镜像没有 OpenCode/Node/Bun。

**准入级别**：见 [唯一最新准入记录](../docs/references/MULTI_HARNESS_ADMISSION_20261009.md)，不要把单项历史 PASS 当作整个架构 GO。
