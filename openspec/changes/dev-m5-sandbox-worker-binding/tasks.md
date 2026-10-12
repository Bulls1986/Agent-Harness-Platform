# DEV-M5 Cube 可信执行与 Coding Runtime · Tasks

> 状态：**ACTIVE · 可信工具准入首段已通过，真实 Cube/Worker 接管仍 OPEN**。工期、Owner 和 Sprint 需要在真实代码/团队容量基线上评估；所有勾选项以运行证据为准。来源 DEV-HC-03 / HC-03。

## 0. 前置与需求冻结
- [ ] 0.1 审阅原有 Accepted ADR/HC 与 G01–G20，识别事实 Owner、安全边界和阻断依赖；OpenSpec 四类规划材料 Strict PASS。
- [ ] 0.2 确认代表性真实业务/失败样本、环境及测试数据，记录本阶段交付与不做范围。

## 已完成的可独立验收切片（不替代后续任务）
- [x] A.1 在纯逻辑 TrustedExecutionGate 中验证不可信 Claim 与可信 ExecutionRecord/Workspace/Scope/Lease/Fencing/Capability 的负例，缺 Sandbox 时 Shell/Files/Git Fail Closed；**证据**：docs/retrospectives/DEV_M3_M5_FIRST_SLICE_20261011.md（TDD Red→Green、PR #61，CI 38132324088）。未执行 Cube Allocate/Bind/Release 或 Worker A→B 实机接管。

- [x] A.2 HC-03 受限 PostgreSQL Recovery Owner/Fencing：当前 Tool Execution 可信 Owner+Epoch+Lease 由 PG 持久化，PG 时钟校验到期后仅对 UNKNOWN 非幂等 Receipt 开放 B Owner CAS 接管；两个并发 B/C 只能一者获 Epoch+1，旧 A 的授权/Receipt 终态提交拒绝，新 B 只能外部读对账不重派 Tool；真实 Hatchet Native Retry 同 Run 验证 A/7→B/8。**证据**：docs/retrospectives/DEV_M4_HATCHET_NATIVE_RETRY_RECOVERY_FENCING_20261011.md。此项只代表**逻辑 Execution Owner** 交接，不等于物理双 Hatchet Worker 实机、真 Cube Sandbox、Workspace/OCI/Policy/Scope Gate。

- [x] A.3 真实 Hatchet 多进程 Fleet 下，Worker A 进程组 SIGKILL（退出码 -9）后，独立 OS Worker B 接管同一 Native Workflow Task；对应 Harness PG Fencing Epoch A/7→B/8，B 只对账已有非幂等 UNKNOWN、旧 Owner 拒绝、外部效果只提交一次。**证据**：docs/retrospectives/DEV_M4_M5_PHYSICAL_WORKER_TAKEOVER_20261011.md。本切片**未使用 Cube**，Scope/WorkspaceRef/真实 Guest/OCI/跨宿主仍 OPEN，不能据此关闭 1.2/1.3 或 DEV-M5 Gate。

- [x] A.4 Native Cube SDK 适配与 Harness PostgreSQL Sandbox Binding 的**控制层开发切片**：真实 PG 保存 Scope/WorkspaceRef/Environment/Owner/Lease/Fencing/Sandbox Locator/Generation/生命周期；跨 Owner 过期接管、旧 Owner 拒绝、同 Workspace 语义和 Fail Closed；测试使用 Fake Cube Transport **仅验证适配合同**。红→绿及 CI 证据：docs/retrospectives/DEV_M5_CUBE_PG_BINDING_20261011.md（真实 PG 5/5 PASS、官方 Cube SDK 方法检查）。**真实 Cube MicroVM 尚未验收，不得勾选 1.2/1.3/2.x**；`dev-m5-cube-live.yml` 配置真实 Cube 后才可执行明确实机 Gate。

- [x] A.5 CubeSandbox 创建 ACK 丢失及 Creator A 崩溃时的持久化 UNKNOWN 对账合同：真实 PostgreSQL `ALLOCATING→CREATING` dispatch barrier，外部创建已成功而 PG Binding ACK 丢失时不得盲目新建；官方 SDK Metadata 冻结，受信任 Native List/Connect/GetInfo 只有唯一完整匹配才允许 `BLOCKED_UNKNOWN→ACTIVE`；PG Fencing B 接管 A 的 `CREATING/UNKNOWN` 时仅能查询同一 Cube。**证据**：docs/retrospectives/DEV_M5_CUBE_CREATE_ACK_RECONCILE_20261011.md（Red 38148112088、Green 38148372940，14/14 PG/SDK 合同）。测试为 Fake Cube + PG，真实 Cube 实机继续 OPEN，不勾选正式 1.2/1.3。

- [x] A.6 **真实 Cube MicroVM 原生 SDK 最小生命周期 Demo**：在已有运行中的 CubeMaster/Cubelet/CubeAPI 和 READY 模板上，官方 `cubesandbox==0.7.0` 实际创建 2 次独立 Sandbox（均真实返回 ID），Guest 文件写入/读回、Native `Sandbox.connect(same_id)` 新 SDK 实例读取原字节、`kill()` 确认成功；运行退出码 0，未使用 Fake Transport。可复现脚本 `poc/sandbox/verify_cube_sdk_smoke.py`，证据 `docs/retrospectives/DEV_M5_REAL_CUBE_MICROVM_SMOKE_20261012.md`。**仅 SDK 实机 Smoke PASS**；Harness PG+真 Cube 以及真实 Hatchet A→B+Cube 联合测试尚未通过，1.2/1.3/2.x 保持 OPEN。

## 1. TDD 与集成开发
- [ ] B.1（2026-10-12 启动）真实 Native Cube Create 显式传入已冻结模板；先增加无 PG 的 SDK 参数负例，验证缺模板拒绝、调用方元数据不可变、未配置不触发 Provider 请求；红绿测试与 CI 证据追加到独立复盘。
- [ ] B.2 实机联合 B03：同 Run、同 Hatchet Workflow、真实 Worker A SIGKILL→B 原生 Retry；真实 Cube ID、同 Guest 字节、PG A/7→B/8、旧 Owner/Scope 拒绝、销毁回执；独立进程 PID/退出码/Provider IDs、Guest 证据及全套失败路径可查询。未实测只可记为 CODE_READY/NOT_TESTED，禁止 PASS。
- [ ] B.3 联合场景的权限边界和证据出口：Inspector 未来只能经可信后端受控发起，静态场景目录/只读 PG 不能判定真实联合 Gate。
- [ ] 1.1 先写无 ExecutionContext、越权、旧 Lease/Fencing 的拒绝测试；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.2 完成真实 Cube Provider Allocate/Bind/Release 与 WorkspaceRef；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.3 OpenCode Shell/Files/Git 和 Worker A→B 实机接管；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [ ] 1.4 模型-only 0 Sandbox、资源释放、跨 Scope 安全/CI/复盘；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。

## 2. 阶段 Gate 与复盘
- [ ] 2.1 复验 拒绝过期及越权 的拒绝/故障合同，正例、负例和真实集成全部 PASS；无 SKIPPED 冒充通过。
- [ ] 2.2 记录故障根因、设计修正、测试覆盖、可复用护栏及风险，完成复盘与 Backlog 状态更新。
- [ ] 2.3 代码 PR/CI、架构审查通过，确认无后续生产门禁被错误关闭后，勾选 Tasks 并归档该 OpenSpec。
