# DEV-M5 · Native Cube SDK + PostgreSQL Sandbox Binding / Fencing 子切片（2026-10-11）

## 判定

**已验证：** Cube Provider 受信任控制层的持久 PostgreSQL Binding、Lease/Fencing、WorkspaceRef/Environment 绑定和本地 Cube SDK Port 合同。**没有验证：** 真 Cube MicroVM Create/Files/Connect/Release、真正 Guest 文件系统隔离、跨主机 Worker/Cube reconnect、实际 Workspace 数据/OCI 镜像一致性。M5 整阶段继续 ACTIVE / OPEN，Production NO-GO。

## 实施及可复验证据

- 新增 `CubeBinding`：Harness PG 以 Execution 为键持久 `run_id / isolation_scope / workspace_ref / environment_digest / owner / fencing_epoch / lease_expires_at / provider_sandbox_id / binding_generation / state`。创建任务先原子持久 `ALLOCATING`；Cube SDK 返回真实 Sandbox ID 后才 `ACTIVE`。若创建结果不确定，进入 `BLOCKED_UNKNOWN`，不得盲目再次分配。
- `CubeWorkspaceGateway` 在每次 files.read/files.write 前校验 PG Owner/Epoch/Lease、只允许固定 `/workspace/` 下的 canonical path；原 Cube Sandbox 不可 connect 时拒绝重建空 Workspace；没有 Host Shell/FS 兜底。
- A→B 的逻辑接管只能在 PG Server-clock Lease 已过期、原 Binding ACTIVE、Run 仍 RUNNING、Scope/Workspace/Digest 均一致时 CAS 升级 Epoch 和 Generation；两个并发抢占最多成功一个，旧 A 无权读写。此步骤不能替代真实 Cube Guest 内的命令级 Fencing。
- `RELEASING` 先落 PG 并阻断新动作，收到 SDK destroy 成功后才 `RELEASED`；销毁 ACK 不明确仍为 RELEASING，不能根据猜测重建一个 Sandbox。
- `NativeCubeTransport` 使用官方 Python `cubesandbox` SDK 真正的 `Sandbox.create()`、`Sandbox.connect(sandbox_id)`、`files.read/write`、`kill`；缺少 `CUBE_API_URL / CUBE_TEMPLATE_ID` 即拒绝连接，绝无 Docker 或伪 Cube 生产替代。
- `test_cube_binding_pg.py` 为真实 PostgreSQL + 明确的 **Fake Cube Transport（仅合同验证）**，测试 Owner/Scope/Workspace/环境不一致、并发 Owner CAS、模拟 Provider 连接失败、未知创建 ACK、不重建空沙箱、释放等。其 PASS **不是**真实 MicroVM PASS。
- `verify_cube_live.py` 和专用 `dev-m5-cube-live.yml` 需 GitHub Actions 实际配置 `vars.CUBE_API_URL`、`vars.CUBE_TEMPLATE_ID`，远端常需 `vars.CUBE_PROXY_NODE_IP`、授权时 `secrets.CUBE_API_KEY`。专用 Workflow 只允许人工 `workflow_dispatch`，没有配置会以非零退出并明确 `REAL_CUBE_GATE_NOT_RUN`，不允许 SKIPPED 或“模拟成功”。真实流程必须实际创建 Cube，读写字节，B 新 SDK 实例重连原 Sandbox ID，旧 A 被 PG Fencing 拒绝，最后 destroy。
- 开发环境预检 `Env:CUBE*`、Docker 运行中服务未发现可用 Cube 连接；当前仓库/CI 没有已证实的 Cube API、Template、Proxy 配置，**因此没有任何本轮真实 Cube MicroVM PASS 可引用**。

## TDD 与 CI

1. [Red CI 38146672828](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38146672828)：先提交 PostgreSQL Cube authority 回归，再执行，`ModuleNotFoundError: poc.sandbox.cube_binding`。真实 PG 服务已启动，负例不是构造的结果。
2. [Green CI 38146883331](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38146883331)：真实 PG 控制层 **5/5 PASS，无 SKIPPED**；官方 Native Cube SDK 方法 `create/connect` 确认可导入；Strict DEV-M5 OpenSpec PASS。
3. [Architecture CI 38146883332](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38146883332)：PASS。
4. 最终 Head 的 CI 必须重新通过后才可合并。不能用首轮 Green/SDK 导入替代真实 MicroVM 或整阶段 Gate。

## 仍需的真实门禁

1. 实际独立 CubeSandbox 集群配置与 SDK Create → Guest Shell/Files → Connect → Kill 全链路，并记录真实 Cube Sandbox ID 与 WorkspaceRef。
2. 与 PR #72 的真实物理 Hatchet Worker A SIGKILL→独立 Worker B、同 Sandbox ID 原 Guest 文件数据恢复相结合；旧进程迟到操作和 in-flight Tool 不能依赖单纯 Harness DB Read Fencing。
3. 不同 Principal/Project/Repo/Secret Scope、真实 OCI Digest/Workspace Revision、Sandbox Destroy ACK-loss/Reconcile、Release 原生资源回收及安全隔离；OpenCode Guest Shell/Files/Git 全路径接入。
4. 缺失 Cube Instance 时从可信 OSS/Git Checkpoint/Artifact 恢复，或明确 UNSUPPORTED；禁止创建空白替代。
5. 完整 M5/M9 Safety/Capacity Gate 仍 OPEN；平台只负责 Harness 边界，不接手 Cubelet/CubeMaster 自身调度。
