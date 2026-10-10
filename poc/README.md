# POC 运行入口（2026-10-09 整理）

这里列出**最短可复验路径**。原有分散脚本及其证据保留原位；本索引不创建另一份架构待办，唯一主清单是 [ARCHITECTURE_BACKLOG](../docs/ARCHITECTURE_BACKLOG.md)。

**2026-10-10 Hatchet Durable Engine（ARCH-TODO-028）：** [Embedded 引擎 + 两真实 SDK DAG](durable_engine/hatchet_embedded_live.py) 已在 [GitHub CI #38020725053](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38020725053) PASS；[双 Engine 共用外部 PostgreSQL / A 强杀不重启 → B 接管原 Workflow](durable_engine/hatchet_fleet_failover_live.py) 已在 [GitHub CI #38021093089](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38021093089) PASS。两项是独立有限 POC，**非端到端同一 Run**；非幂等 Tool、WAITING_APPROVAL、真正 Token SSE / Cube / 资源压力未通过，生产 NO-GO。**DBOS 已因商业许可约束排除，不作为备选，也不再安排测试**；历史许可证说明见 [专项评估](../docs/references/DURABLE_ENGINE_LICENSE_GATE_20261010.md)。

## 一、无需外部服务：可以在 Windows/Linux 验证

```sh
python -B poc/verify_admission_offline.py
python -B poc/verify_repo_navigation.py    # 检查文档入口与链接
python -B poc/compatibility/verify_stack.py # 版本/验证证据/已知不兼容/OCI Digest 离线检查
python -B poc/compatibility/verify_stack.py --self-test # fail-closed 防漂移回归
```

脚本依次验证：Cube Native 预检（**无真实 Sandbox**）、Session→Sandbox Scope/Generation Fail Closed、E2B Session 路由 Mock。PASS 表示逻辑/SDK 边界测试已通过，不代表 Cube / OpenCode / Agent Loop 真机准入。

Pydantic 高密度（需依赖）：
```sh
python -B poc/pydantic_harness/verify_offline_density.py
# Linux/WSL / CI，POSIX-only：
python -B poc/pydantic_harness/verify_local_tool_routing_posix.py
```

**版本基线：** [真实通过的 SDK/Runtime 版本、失败组合、镜像与模板 ID](../docs/references/VERIFIED_STACK_BASELINE_20261010.md)；`poc/compatibility/verify_stack.py --profile cube_e2b_native` 在对应已安装 SDK 的隔离 venv 中验证实际 package pin；不启动 Cube，也不把 `e2b==2.53.1` 视作已通过版本。

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
# OpenCode 2 Harness-in-Cube READY Template：真实 2 V2 Sessions + FS/Shell +
# 同一 Cube MicroVM 的 Pydantic AI / OpenAI FunctionTool 接力（0 远程模型）
python -B poc/opencode_sandbox/verify_cube_opencode2_v2_live.py --live --template tpl-aacac99e38bf46e68ecd2f1f
# 仅内置真实 Git 的专用模板才能运行严格的 Git Gate：
python -B poc/opencode_sandbox/verify_cube_opencode2_v2_live.py --live --require-git --template tpl-363306ce3b21432cb1ae6536
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

### 2026-10-10 官方 E2B 2.40 + OpenAI Native 真机通过（独立 WSL DNS）

[真实版本矩阵、DNS/TLS 条件与可重复入口](opencode_sandbox/E2B_PRIVATE_DNS_VERIFICATION_20261010.md)。在隔离 WSL2 Python `e2b==2.40.0`、`openai-agents==0.23.1`、已 READY 的 Cube Template 和可信 CA 下：

```sh
python -B poc/opencode_sandbox/verify_cube_e2b_private_dns.py --live --openai-native
# 仅本地 auth-disabled 的隔离演示环境，才可以加 --anonymous-local
```

此版本组合实际真实 `create/files/commands/kill`、两 Sandbox 文件隔离、OpenAI Native E2BSandboxClient create/exec/aclose 均 PASS；**2.53.1 仍 405**，不能外推。

### 平台 AgentRuntime SPI POC

[公开 SDK Adapter 与合同](runtime_spi/README.md)；`python -B poc/runtime_spi/verify_runtime_spi.py` 离线预检，以及在安装 Pydantic AI + OpenAI SDK 的 venv 中运行 `--sdk`。两个真实 SDK 的本地确定性 Model Run 均 PASS（零远程模型调用）；OpenCode V2 Session SPI 此阶段仅模拟，完整 Token SSE/Receipt 仍待推进。

## 四、OpenCode 2 与其他专项

- [OpenCode 2 / OpenAI 对照](opencode_sandbox/README.md)：Docker V2 Server/Session/FS/Shell 双向接力 PASS；共享 Host 原生 Shell 不能按 Session ID 自动转到外部 Sandbox（负例）。
- [OpenCode 2 Harness-in-Cube OCI 模板](opencode_sandbox/opencode2_cube_template/README.md)：**真实 Cube Template READY、V2 2 Session/FS/Shell 与 Pydantic/OpenAI 同 Sandbox Tool 接力 LIVE LIMITED PASS**（2026-10-10）；Git 工具链与生产隔离继续验证。
- [Pydantic](pydantic_harness/README.md)：FunctionModel 与 POSIX 本地 Workspace；SDK Mock Ref Reconnect。
- [MAF](maf/) / [Temporal](temporal/)：已有 POC-A/C 验证不迁移、不删除。
- 真正的 OpenCode 2 **Cube** 验证需专用 OCI Template；默认 sandbox-code 镜像没有 OpenCode/Node/Bun。

**准入级别**：见 [唯一最新准入记录](../docs/references/MULTI_HARNESS_ADMISSION_20261009.md)，不要把单项历史 PASS 当作整个架构 GO。
