# DEV-M5 Cube 可信执行与 Coding Runtime · Tasks

> 状态：**CLOSED（2026-10-13，原始有界 Harness Cube/PG/Native Hatchet Coding Guest 交付）。** 以 `docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md` 为最终可信门禁；仅真实单宿主技术合同可关闭，cross-host / Guest in-flight Fencing / 完整 OpenCode Agent loop **NOT TESTED**；M9 Production NO-GO。以下历史 ACTIVE/OPEN 注记仅为当时切片快照。

## 原始 M5 退出 Gate 实机证据与风险（2026-10-13）

**已完成有界平台合同：** 真实 Cube+PG Binding/同 ID 文件保持和 Release，真正 Hatchet Worker A 进程 SIGKILL→独立 B/8 接原 Sandbox，Guest 内 Shell/Git，旧 Owner/跨 Scope/Lease/Fencing 拒绝、模型-only 0 Cube；所有原 0.1～2.3 正式任务的**平台受控部分**均引用证据：docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md。

**NOT TESTED：** 跨主机恢复、正在执行的 Guest 命令强制 Fence、真实 OpenCode 自主 Agent loop 及生产安全验收；它们不得从单宿主技术合同推导，也不改变 M6/M9 或其他外部 Owner 的既有门禁。GitHub-hosted 真实 Cube 显式 Gate 当前无端点且未执行，不宣称官方 GitHub-hosted 的 MicroVM 实机 PASS，独立本地实机证据如报告。**Production NO-GO**。

## 0. 前置与需求冻结
- [x] 0.1 审阅原有 Accepted ADR/HC 与 G01–G20，识别事实 Owner、安全边界和阻断依赖；OpenSpec 四类规划材料 Strict PASS。 **正式验收**：docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md
- [x] 0.2 确认代表性真实业务/失败样本、环境及测试数据，记录本阶段交付与不做范围。 **正式验收**：docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md

## 已完成的可独立验收切片（不替代后续任务）
- [x] A.1 在纯逻辑 TrustedExecutionGate 中验证不可信 Claim 与可信 ExecutionRecord/Workspace/Scope/Lease/Fencing/Capability 的负例，缺 Sandbox 时 Shell/Files/Git Fail Closed；**证据**：docs/retrospectives/DEV_M3_M5_FIRST_SLICE_20261011.md（TDD Red→Green、PR #61，CI 38132324088）。未执行 Cube Allocate/Bind/Release 或 Worker A→B 实机接管。

- [x] A.2 HC-03 受限 PostgreSQL Recovery Owner/Fencing：当前 Tool Execution 可信 Owner+Epoch+Lease 由 PG 持久化，PG 时钟校验到期后仅对 UNKNOWN 非幂等 Receipt 开放 B Owner CAS 接管；两个并发 B/C 只能一者获 Epoch+1，旧 A 的授权/Receipt 终态提交拒绝，新 B 只能外部读对账不重派 Tool；真实 Hatchet Native Retry 同 Run 验证 A/7→B/8。**证据**：docs/retrospectives/DEV_M4_HATCHET_NATIVE_RETRY_RECOVERY_FENCING_20261011.md。此项只代表**逻辑 Execution Owner** 交接，不等于物理双 Hatchet Worker 实机、真 Cube Sandbox、Workspace/OCI/Policy/Scope Gate。

- [x] A.3 真实 Hatchet 多进程 Fleet 下，Worker A 进程组 SIGKILL（退出码 -9）后，独立 OS Worker B 接管同一 Native Workflow Task；对应 Harness PG Fencing Epoch A/7→B/8，B 只对账已有非幂等 UNKNOWN、旧 Owner 拒绝、外部效果只提交一次。**证据**：docs/retrospectives/DEV_M4_M5_PHYSICAL_WORKER_TAKEOVER_20261011.md。本切片**未使用 Cube**，Scope/WorkspaceRef/真实 Guest/OCI/跨宿主仍 OPEN，不能据此关闭 1.2/1.3 或 DEV-M5 Gate。

- [x] A.4 Native Cube SDK 适配与 Harness PostgreSQL Sandbox Binding 的**控制层开发切片**：真实 PG 保存 Scope/WorkspaceRef/Environment/Owner/Lease/Fencing/Sandbox Locator/Generation/生命周期；跨 Owner 过期接管、旧 Owner 拒绝、同 Workspace 语义和 Fail Closed；测试使用 Fake Cube Transport **仅验证适配合同**。红→绿及 CI 证据：docs/retrospectives/DEV_M5_CUBE_PG_BINDING_20261011.md（真实 PG 5/5 PASS、官方 Cube SDK 方法检查）。**真实 Cube MicroVM 尚未验收，不得勾选 1.2/1.3/2.x**；`dev-m5-cube-live.yml` 配置真实 Cube 后才可执行明确实机 Gate。

- [x] A.5 CubeSandbox 创建 ACK 丢失及 Creator A 崩溃时的持久化 UNKNOWN 对账合同：真实 PostgreSQL `ALLOCATING→CREATING` dispatch barrier，外部创建已成功而 PG Binding ACK 丢失时不得盲目新建；官方 SDK Metadata 冻结，受信任 Native List/Connect/GetInfo 只有唯一完整匹配才允许 `BLOCKED_UNKNOWN→ACTIVE`；PG Fencing B 接管 A 的 `CREATING/UNKNOWN` 时仅能查询同一 Cube。**证据**：docs/retrospectives/DEV_M5_CUBE_CREATE_ACK_RECONCILE_20261011.md（Red 38148112088、Green 38148372940，14/14 PG/SDK 合同）。测试为 Fake Cube + PG，真实 Cube 实机继续 OPEN，不勾选正式 1.2/1.3。

- [x] A.6 **真实 Cube MicroVM 原生 SDK 最小生命周期 Demo**：在已有运行中的 CubeMaster/Cubelet/CubeAPI 和 READY 模板上，官方 `cubesandbox==0.7.0` 实际创建 2 次独立 Sandbox（均真实返回 ID），Guest 文件写入/读回、Native `Sandbox.connect(same_id)` 新 SDK 实例读取原字节、`kill()` 确认成功；运行退出码 0，未使用 Fake Transport。可复现脚本 `poc/sandbox/verify_cube_sdk_smoke.py`，证据 `docs/retrospectives/DEV_M5_REAL_CUBE_MICROVM_SMOKE_20261012.md`。**仅 SDK 实机 Smoke PASS**；Harness PG+真 Cube 以及真实 Hatchet A→B+Cube 联合测试尚未通过，1.2/1.3/2.x 保持 OPEN。

> 2026-10-13 原范围集成进展：Native Cube SDK 明确传模板的 TDD Red→Green、真实 PG 合同 14/14 PASS；真实 Cube + PG 绑定/Lease/Fencing B/8/Guest 持久字节/Destroy 已单独实机 PASS。物理 Hatchet Worker A SIGKILL→B 同 Cube 接管尚无真实 PASS，不能勾选 1.3/2.x，不添加新 A.x。证据：docs/retrospectives/DEV_M5_REAL_CUBE_PG_WORKER_GATE_20261013.md。

## 1. TDD 与集成开发
- [x] 1.1 先写无 ExecutionContext、越权、旧 Lease/Fencing 的拒绝测试；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。 **正式验收**：docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md
- [x] 1.2 完成真实 Cube Provider Allocate/Bind/Release 与 WorkspaceRef；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。 **正式验收**：docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md
- [x] 1.3 OpenCode Shell/Files/Git 和 Worker A→B 实机接管；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。 **正式验收**：docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md
- [x] 1.4 模型-only 0 Sandbox、资源释放、跨 Scope 安全/CI/复盘；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。 **正式验收**：docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md

## 2. 阶段 Gate 与复盘
- [x] 2.1 复验 拒绝过期及越权 的拒绝/故障合同，正例、负例和真实集成全部 PASS；无 SKIPPED 冒充通过。 **正式验收**：docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md
- [x] 2.2 记录故障根因、设计修正、测试覆盖、可复用护栏及风险，完成复盘与 Backlog 状态更新。 **正式验收**：docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md
- [x] 2.3 代码 PR/CI、架构审查通过，确认无后续生产门禁被错误关闭后，勾选 Tasks 并归档该 OpenSpec。 **正式验收**：docs/retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md