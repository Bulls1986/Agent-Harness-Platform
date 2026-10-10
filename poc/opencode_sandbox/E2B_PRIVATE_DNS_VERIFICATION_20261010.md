# Cube v0.7.2 × 官方 E2B 2.40.0 数据面修复（2026-10-10）

> **真实 WSL2/KVM Cube MicroVM 测试；CUBE-1 最小子集 + CUBE-3 原生 OpenAI 已 PASS。生产仍 NO-GO。**

## 失败根因与复验条件

原 `e2b==2.40.0` 调用 CubeSandbox.create 已成功，`files.write` 遇 `ConnectError`，原因是运行环境中的**域名/解析器配置**：

1. E2B 2.40.0 公开 `E2B_DOMAIN` 默认 `e2b.app`；CubeProxy 代理实例的目标 Host 应为 `49983-<sandbox-id>.cube.app`，请求需通过 Cube 专用代理。
2. WSL2 `/etc/resolv.conf` 指向 Windows DNS（`/mnt/wsl/resolv.conf`），但 Cube 启动器已经在 WSL 的 `systemd-resolved` 为 `~cube.app` 配置了 `cube-dns0` 路由和 `169.254.254.53` CoreDNS：`resolvectl query 49983-...cube.app` 能解析至当前 CubeProxy 节点地址，而 `getent ahostsv4` 因默认 resolv.conf 不走该路由而失败。
3. **最小 POC 处理**：使用 Linux **单独 mount namespace**（`unshare -m --propagation private`），仅将现有 `/run/systemd/resolve/stub-resolv.conf` bind 到该进程的 `/etc/resolv.conf`；设置 `E2B_DOMAIN=cube.app`，并保留本地 CA 的 `SSL_CERT_FILE`。严格禁止修改全机 `/etc/resolv.conf`、关 TLS 验证、劫持 SDK 私有字段。直接使用隐藏的子进程标志调用时先检查当前 mount namespace 与 PID1 不同，拒绝危险全局 bind。
4. 本地自托管 Cube API 3000、TemplateCenter 8090、CubeEgress 9091 健康，模板使用 [Git-enabled Cube READY Template](opencode2_cube_template/VERIFICATION_20261010.md) `tpl-363306ce3b21432cb1ae6536`；测试期间没有调用模型。

## 真实 SDK 兼容矩阵（同一 Cube v0.7.2）

| 组合 | Control Plane | Data Plane | 结论 |
|---|---|---|---|
| Cube Native SDK 0.7.0 | PASS | Files/Shell PASS | 已有真机 PASS |
| 官方 `e2b==2.53.1` | `POST /v2/sandboxes` HTTP 405 | NOT TESTED | **此组合 NO-GO** |
| 官方 `e2b==2.40.0`，使用 WSL 默认 DNS | `POST /sandboxes` 创建 PASS | `ConnectError` | **环境不完整，FAIL** |
| 官方 `e2b==2.40.0`，隔离的 `cube.app` DNS + 可信 CA | 真实 ID 创建 PASS | `files.write/read`、`commands.run` PASS | **CUBE-1 最小真机 PASS** |
| `e2b==2.40.0` + `openai-agents==0.23.1`，同上 | 两个独立 E2B Sandbox create PASS | 彼此文件隔离，原生 `E2BSandboxClient.create/exec/aclose` PASS | **CUBE-3 最小真机 PASS** |

可核查实际工具输出（`--live --anonymous-local`，本地 Cube `auth_enabled=false` 模式下临时生成格式合法的测试值，不输出敏感信息）：

```json
{"commands_run":"PASS","cross_instance_content_isolation":"PASS","files_write_read":"PASS","model_calls":0,"official_e2b_sdk":"PASS","openai_agents_e2b_client":"PASS","outcome":"PASS","sandbox_instances":2,"scope":"live_cube","sdk_private_patches":false,"sdk_versions":{"e2b":"2.40.0","openai_agents":"0.23.1"}}
```

## 可复验（必须真实 Cube 本地、可信证书和显式 opt-in）

```sh
export CUBE_API_URL=http://127.0.0.1:3000
export CUBE_TEMPLATE_ID=tpl-363306ce3b21432cb1ae6536
export CUBE_E2B_LIVE_CONFIRM=1
export SSL_CERT_FILE=/path/to/trusted/local/CA.pem
# 生产凭据用 E2B_API_KEY 从 Secret Provider 提供，切勿写入仓库。
python -B poc/opencode_sandbox/verify_cube_e2b_private_dns.py --live
# 仅隔离本机 Cube auth-disabled 的 demo 可显式生成随机临时 Key：
python -B poc/opencode_sandbox/verify_cube_e2b_private_dns.py --live --anonymous-local
# 含原生 OpenAI Agent SDK E2B Client 最小合约：
python -B poc/opencode_sandbox/verify_cube_e2b_private_dns.py --live --anonymous-local --openai-native
```

隔离 WSL Python 环境需安装官方 `e2b==2.40.0`，最后一步另需 `openai-agents==0.23.1`。该 `--anonymous-local` **禁止**用于鉴权开启的生产 Cube/远端租户，仅使用本机无需鉴权的测试环境。脚本默认离线，提供 `--live`、真实模板、可信 CA 和本机 Cube API 才会创建 Sandbox；各 SDK 合约在 `finally` 释放实例。

## 不可提升为生产通过的门禁

- **官方 SDK 2.53.1 仍 HTTP 405**，版本路由未修复，不得将 v2.40 的通过外推到最新客户端；
- 官方 `e2b Sandbox.connect` 同原 Sandbox ID 的外部 SDK 重连、Pydantic AI Harness 内置 E2BSandbox/Coder → E2B 2.40.0，仍未单独完成；
- Pydantic/OpenAI SDK 同一个真实 Sandbox ID 的原生混合 Tool 接力尚未从这次原生 E2B 测试单独证明（之前的 Cube Native Tool 同 VM 接力另有 LIVE PASS）；
- 广域 DNS/可信 CA/私有 HTTPS 配置与无鉴权 POC 环境**不能原样照搬生产**；生产严禁直接暴露本地 HTTP Registry 或未经 IAM 授权 Sandbox；
- 跨 Worker 恢复、并行 Scope 隔离 / lease fencing / Receipt、安全/容量仍属架构待办。
