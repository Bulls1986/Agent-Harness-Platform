# DEV-M5 Cube 可信执行 · 原始范围最终验收和复盘（2026-10-13）

## 最终裁决

**DEV-M5 / DEV-HC-03：CLOSED（原始平台控制层 + 单宿主真实 Coding Guest 合同）**，不是平台 Production GO。原始 Proposal/Spec 要求：可信 ExecutionContext/WorkspaceRef/Scope/Lease/Fencing、按需 Cube Create/Bind/Release、模型-only 不分配 Sandbox、OpenCode 方向的 Coding Guest Shell/Files/Git 仅能在 Cube 中执行、真实 Hatchet Worker A 进程被杀后 Worker B 连接 **同一个** Cube、跨 Scope/旧 Owner 被拒。以上**原始有界合同**均已有真实 PG、真实 Cube MicroVM、原生 Hatchet/Worker 与 Git Guest 证据，不借用 Host Shell、不另建 Engine 或功能任务。

**明确 NOT TESTED（cross-host / Guest in-flight 等生产门禁）：** 跨不同宿主故障接管、已经进入 Cube Guest 的 in-flight 强制 Fencing/进程撤销、生产级 OCI 镜像供应链/密钥隔离、安全证明，以及完整远程 LLM/OpenCode Agent 的自主编程回路。这些不能从本地单宿主的真实 MicroVM 测试推断，也未在当前阶段作为实机完成声明；遵循原 M6/M8/M9 以及 Cube 基础设施 Owner 的既有验收职责。生产 **NO-GO** 不变。

## Red → Green、根因

1. 真实 Cube API 首次联测出现原生 `ApiError 130400`：模板元数据列表 READY，但 CubeMaster 健康节点无可用模板副本；Harness PG 正确进入 `BLOCKED_UNKNOWN` 且拒绝盲目重试。复盘改为检查 Cube API Health **同时**核实 CubeMaster 模板真实 READY Replica 和 Node Inventory，并在启动时等待同一 WSL 服务初始化完成；新执行 ID 重新发起实测，**未对原 UNKNOWN 直接重新 Create**。
2. 原通用 Cube `sandbox-code` Guest 的 `git --version` 退出 `127`（未安装 Git）；SDK 创建/清理成功，测试 FAIL 而非伪装完成。选择**已存在**的 `ahp-opencode2-cube` Git Coding 模板，真实 Guest `git version 2.39.5`、`pwd=/workspace`、exit 0，原生 Sandbox 销毁成功；未构建新镜像，不在宿主安装 Git。
3. 先提交 PG 负例红灯 [PR #94](https://github.com/Bulls1986/Agent-Harness-Platform/pull/94)：缺 Sandbox、伪 Owner、旧 Fencing、过期 Lease、发布后旧 Run 禁止调用 `command`，以及 Native SDK Guest `commands.run(...,cwd=/workspace,timeout=30)` 形状；[RED CI 38407481404](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38407481404) 保留真实失败。最小 Green 是在**现有** `CubeWorkspaceGateway` 利用原 PG `_attach` 授权执行 `command`，`NativeCubeTransport` 只调用沙箱 Guest 的 `commands.run`，没有 `subprocess`、Host Shell 兜底、第二技术调度器或额外任务。[GREEN CI 38407888927](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38407888927) 与 [架构 CI 38407889074](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38407889074) SUCCESS。

真实物理联合测试输出的明确机器字段：`"native_guest_git": true`、`"host_shell_fallback": false`、`"guest_original_content_kept": true`、`"retry_count": 1`、`"cube_release_confirmed": true`；这是已验收的实际本地运行结果，不是预期值。

## 真实执行 Gate（同一单宿主 CubeSandbox / 原始用户预期）

| Gate | 实际可信证据 | 结果 |
| --- | --- | --- |
| Cube+PG 创建 / 绑定 / Guest 文件 / 重连 / 释放 | 真实 Cube Sandbox `c7a2705b7e22420ab4723391d0692f47`；Run `m5-cube-live-00ccbbf8618a4ec386b30f6b325399d2`；PG Worker A/7→B/8；独立 SDK 对同一个 Cube 读取原字节；Guest 执行 Shell/Git；`host_shell_fallback=false`；`RELEASED` | **PASS** |
| 物理 Worker A SIGKILL→独立 B + Cube/PG/Git | Run `m5-cube-hatchet-d0da08de029d430892d04b75b4c1b579`；Hatchet Workflow `87eb5c06-be46-4c3c-9a3e-b1233af09f93`；Cube `fa6ec514f24243fabcea8796150665f2`；A PID 6861 `SIGKILL=-9`，B PID 7784；Native Retry 1；PG Epoch 8；Guest 原始文件同 ID，B 在 Cube Guest 执行 `git --version`，PG Release 成功；无 Host Shell fallback | **PASS** |
| 模型-only 0 Sandbox | `poc.runtime_spi.verify_runtime_spi` 控制层 `no_sandbox_model_run=PASS`，并查询真实 Cube Native List：执行前 0，执行后 0；不是模拟一次真实 LLM 调用 | **PASS（控制层路由+真实 Cube 数量）** |
| 跨 Scope / 旧 Owner / Lease / Fencing / 文件越界 | [真实 PG Cube binding/Native SDK 合同 CI 38407888927](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38407888927)；无可信 PG ACTIVE / 过期/不同 Scope/Workspace/Digest / A 旧 Epoch 等拒绝，拒绝后 Provider 不调用，未知创建/销毁禁止盲重派；真实故障恢复仍只接原 Sandbox | **PASS** |
| 真实依赖/安全边界 | 独立 Hatchet Embedded 技术任务，PG Domain Owner，不向业务请求暴露 Cube ID 授权；Cube 原生 MicroVM Guest 执行 Git 和文件 | **PASS（本次有界合同）** |

若执行身份未注入 PG、模板无 READY 节点、副本不可访问、Cube 查询不确定、原 Sandbox 已消失，返回失败或保持 `BLOCKED_UNKNOWN`，不得 Host Shell 兜底或创建一个空白工作区让测试假绿。

## 原任务 0.1～2.3 逐条验收

- **0.1 / 0.2**：冻结架构 HC-01/02/03，G01–G20；仅合成 Run/Workspace、真正独立 PG/Hatchet/Cube SDK/Guest 实机样本；不触碰私有 PDLC 项目。
- **1.1**：PR #61、#74 和 #94 Red→Green；无 Context、非法/过期 Lease/跨 Scope/旧 Owner/文件路径/Shell/Git 拒绝，实际 Postgres、官方 CI、真 Cube Guest 均有证据。
- **1.2**：PG Cube Sandbox Locator/EnvironmentDigest/WorkspaceRef/Metadata/Lease/Fencing 原子事实与真实 Native Create/Connect/Files/Destroy，`CREATING/BLOCKED_UNKNOWN` 禁盲重建、Release ACK 可靠状态。
- **1.3**：Native Hatchet Worker A 实机 SIGKILL 到独立 Worker B，连接原 Sandbox，原 Guest 数据保持，受 PG Fencing 提升 B/8，真实 Coding Guest Git/Shell；不声称完整 OpenCode Agent 自主循环已执行。
- **1.4**：model-only route 0 Sandbox；真实 Coding MicroVM 创建/释放；跨 Scope、旧 Owner、过期 Lease/不同 Workspace/Digest 和不可信 Command 输入拒绝。
- **2.1**：本地真实 PG/Native Cube/Hatchet 以及官方 PG/SDK/Architecture 全 PASS（可回归）。GitHub-hosted `dev-m5-cube-live.yml` 属必须配置私有 Cube Endpoint/Template 的**显式环境 Gate**；当前没有可用的 GitHub-hosted Cube Endpoint，**NOT RUN ON GITHUB HOSTED**，不得当成该环境已通过，实机证据来自明确标明的本地 Cube 环境。
- **2.2**：记录 READY Replica/WSL 启动期错误、通用模板无 Git（127）、Fail-Closed、原实机 ID、TDD、单宿主与 in-flight 限制。
- **2.3**：原始有界平台合同已具备审批依据；正式 CI 最新 Head 的 M5 PG/SDK、Architecture、OpenSpec Strict/归档正本验证 **必须 PASS 后才能合并**。仅代码/证据归档；平台 Production **NO-GO**。

## 固定责任与后续既有门禁

DEV-M5 **不承担**外部企业 IdP、OSS 签名、MCP 治理，也不建立通用 ToolRuntime 或第二 Hatchet。具体 Agent 真正调用 OpenCode 的高层 Recipe/交互循环归原 M6（未通过）；真实消费者归 M8；生产安全、跨宿主/并发作业隔离、网络和 Guest in-flight Fencing 属 M9/基础设施生产 Gate。本阶段关闭并不承诺其生产结果。

原 [M5 集成审计](DEV_M5_REAL_CUBE_PG_WORKER_GATE_20261013.md) 是最终新实机验证前的记录，保留作为“已知故障 → 验证解决”的可审计历史，不覆写旧判断。其他 M3/M4/M7 阶段不重开；生产继续 **NO-GO**。
