# DEV-M5 · Cube 创建 ACK 丢失、崩溃接管与原生唯一定位（2026-10-11）

## 独立子切片结果

**本切片通过：** 真实 PostgreSQL 的 Cube Native SDK 边界合同、冻结 Provider Metadata 与创建 ACK 丢失后仅对账唯一原生 Sandbox 的安全迁移；Worker A 已经调用 Cube 创建但在持久绑定之前死亡时，Lease 到期的 Worker B 通过 PG CAS 将 CREATING→BLOCKED_UNKNOWN，并核对原 Cube ID 后恢复同一 WorkspaceRef，不执行第二次创建。

**本切片未通过/未执行：** 真实 Cube MicroVM 创建/Guest Files/Native Connect/Destroy、实际 Cube Sandbox 的隔离与 OCI 镜像同一性、物理 Hatchet Worker A/B 加真 Cube 的联合场景、跨宿主安全。SDK 适配测试使用 Mock SDK，PG 合同测试使用明确 Fake Cube Transport：**不是**实机 Cube 通过证据。M5 仍 ACTIVE/OPEN，Production NO-GO。

## TDD 与真实 CI

1. 原 PR #73 的 PG Cube Binding 子切片 7/7 PASS；新加未知创建 ACK 原生对账、Provider Metadata 精确匹配/不一致/重复、SDK 接口参数、Owner B 恢复负例，真实 PG 10/10 PASS（[CI 38147967213](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38147967213)）。
2. 补 Worker B 接管 BLOCKED_UNKNOWN 时，旧代码错误要求已绑定的 Provider Sandbox ID；[Red CI 38148112088](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38148112088) 12 tests 中 `test_worker_b_recovers_unknown_cube_after_creator_lost_ack` FAIL，定位为 `CubeBinding.takeover()` 错误要求 `row[7]` 非空。
3. 修复 UNKNOWN 接管：仅在数据库时钟确认 Lease 到期、Scope/Workspace/Environment 一致、Run 未终止时，原子推进 Owner Epoch；未确认的 Provider ID 仍为空，由 B 原生查询和详情核验唯一 Cube 再绑定。冻结原创建元数据必须**跨 Owner 代际稳定**，不能随着 `binding_generation` 从 1→2 改写原始 Creator 的定位键。
4. 进一步新增 `CREATING` 状态：在 Cube SDK Create **之前**提交到 Harness PG，构成实际外部创建的 durable dispatch barrier。若外部 Create 成功但 PostgreSQL `confirm` 失败或 ACK 丢失，第二次 Allocate 必须失败并经原始元数据对账，防止第二个 MicroVM；若 A 死在 CREATING，B 获租约后只能进入 BLOCKED_UNKNOWN，而不能重新创建。
5. SDK 调用合同进一步核实：官方 `Sandbox.create(metadata=...)`、`Sandbox.list()`、`Sandbox.connect(sandbox_id)`、`Sandbox.get_info()` 与 `files.read/write`；Adapter 每条 native List Metadata 都需完整匹配 `Execution/Run/Scope/Workspace/Environment/Immutable-Allocation-Generation`，唯一匹配后仍调用 Connect 和 GetInfo 二次验证，错误/无记录/多记录/列表超过上限均 UNKNOWN。
6. 修复后 [CI 38148287980](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38148287980) 成功；包含更多真实 PG 创建/恢复路径的 [CI 38148372940](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38148372940) **14/14 PASS，无 SKIPPED**；最终提交须再次复验成功后才能合并。本次已按 Red→Green 复盘，不把设计讨论当完整验收。

## 环境事实与部署阻断

- Windows 开发机的 WSL 可检查到 `/dev/kvm`，说明具备一个硬件先决项；后续 WSL `df` 与资源/文件系统诊断连续超时，**没有验证可用 XFS、50GB 镜像/数据空间、16GB RAM 和可用 Cube Cluster/Template/Proxy**，不能擅自开始重型本机安装。
- Cube 官方当前实际支持 SDK `metadata`、`list`、`connect`；其 Quick Start/部署要求取自 https://docs.cubesandbox.com/guide/quickstart 及 https://docs.cubesandbox.com/guide/tutorials/sdk/python.html 。官方单机部署需 Linux/KVM、XFS、镜像空间，并不是运行 docker-compose 即可得到具备隔离的 Cube MicroVM。
- `.github/workflows/dev-m5-cube-live.yml` 仍保留人工触发的**真实 Cube**验收合同，需可访问的 `CUBE_API_URL`、`CUBE_TEMPLATE_ID` 和远端 Proxy/鉴权配置。缺失配置必须非零退出；不能为取得绿色结果而使用 Docker/Fake Sandbox 替代实机。
- 下一真实证据：验证真正 Native Cube Sandbox create/list/get_info/connect/read/write/kill，再与 PR #72 的物理 Hatchet A→B 接管串联，测试丢 ACK 后 Worker B 能保留真实 Guest 文件；并确认权限检查在 Guest 执行入口不可绕过。未完成之前不得通过 M5 1.2/1.3 或 M9 GO。

## 安全局限

本子切片的 PG Lease/Fencing 控制**受信任 Harness Gateway 的新动作**；已经交付 Cube Guest 的异步/in-flight Shell/Files 写入仍需要实际 Guest Side 执行栅栏或隔离策略才能阻断。当前还未覆盖跨项目 Principal/Secret/Repo Scope，不能把 Metadata 当身份凭证，也不把 Provider Sandbox ID 当授权 Token。Native `list()` 可能受 Provider 可见性与过滤限制，无完整证据时保持 UNKNOWN，不根据“未查到”推断从未创建。
