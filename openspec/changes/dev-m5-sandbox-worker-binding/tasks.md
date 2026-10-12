# DEV-M5 Cube 可信执行与 Coding Runtime · Tasks

> 状态：**ACTIVE · 真实 Cube/Worker B03 联合接管已 PASS，其他 DEV-M5 阶段退出条件仍 OPEN**。工期、Owner 和 Sprint 需要在真实代码/团队容量基线上评估；所有勾选项以运行证据为准。来源 DEV-HC-03 / HC-03。

## 0. 前置与需求冻结
- [x] 0.1 复核 Accepted ADR/HC-01/02/03 与 G01–G20，保留 Domain/Process/Sandbox Owner 与拒绝 Host Shell 等硬约束；DEV-M5 OpenSpec Strict 验收。证据：docs/retrospectives/DEV_M5_PHASE_EXIT_AUDIT_20261012.md。
- [x] 0.2 冻结本阶段代表性真实故障机制、合成载荷/环境和不做范围，不复制私有业务消费者代码或数据；真实 Worker SIGKILL、Cube Create ACK-loss、Scope/Lease、模型-only 和 OpenCode Guest 样本在复盘明确。证据：docs/retrospectives/DEV_M5_PHASE_EXIT_AUDIT_20261012.md。

## 已完成的可独立验收切片（不替代后续任务）
- [x] A.1 在纯逻辑 TrustedExecutionGate 中验证不可信 Claim 与可信 ExecutionRecord/Workspace/Scope/Lease/Fencing/Capability 的负例，缺 Sandbox 时 Shell/Files/Git Fail Closed；**证据**：docs/retrospectives/DEV_M3_M5_FIRST_SLICE_20261011.md（TDD Red→Green、PR #61，CI 38132324088）。未执行 Cube Allocate/Bind/Release 或 Worker A→B 实机接管。

- [x] A.2 HC-03 受限 PostgreSQL Recovery Owner/Fencing：当前 Tool Execution 可信 Owner+Epoch+Lease 由 PG 持久化，PG 时钟校验到期后仅对 UNKNOWN 非幂等 Receipt 开放 B Owner CAS 接管；两个并发 B/C 只能一者获 Epoch+1，旧 A 的授权/Receipt 终态提交拒绝，新 B 只能外部读对账不重派 Tool；真实 Hatchet Native Retry 同 Run 验证 A/7→B/8。**证据**：docs/retrospectives/DEV_M4_HATCHET_NATIVE_RETRY_RECOVERY_FENCING_20261011.md。此项只代表**逻辑 Execution Owner** 交接，不等于物理双 Hatchet Worker 实机、真 Cube Sandbox、Workspace/OCI/Policy/Scope Gate。

- [x] A.3 真实 Hatchet 多进程 Fleet 下，Worker A 进程组 SIGKILL（退出码 -9）后，独立 OS Worker B 接管同一 Native Workflow Task；对应 Harness PG Fencing Epoch A/7→B/8，B 只对账已有非幂等 UNKNOWN、旧 Owner 拒绝、外部效果只提交一次。**证据**：docs/retrospectives/DEV_M4_M5_PHYSICAL_WORKER_TAKEOVER_20261011.md。本切片**未使用 Cube**，Scope/WorkspaceRef/真实 Guest/OCI/跨宿主仍 OPEN，不能据此关闭 1.2/1.3 或 DEV-M5 Gate。

- [x] A.4 Native Cube SDK 适配与 Harness PostgreSQL Sandbox Binding 的**控制层开发切片**：真实 PG 保存 Scope/WorkspaceRef/Environment/Owner/Lease/Fencing/Sandbox Locator/Generation/生命周期；跨 Owner 过期接管、旧 Owner 拒绝、同 Workspace 语义和 Fail Closed；测试使用 Fake Cube Transport **仅验证适配合同**。红→绿及 CI 证据：docs/retrospectives/DEV_M5_CUBE_PG_BINDING_20261011.md（真实 PG 5/5 PASS、官方 Cube SDK 方法检查）。**真实 Cube MicroVM 尚未验收，不得勾选 1.2/1.3/2.x**；`dev-m5-cube-live.yml` 配置真实 Cube 后才可执行明确实机 Gate。

- [x] A.5 CubeSandbox 创建 ACK 丢失及 Creator A 崩溃时的持久化 UNKNOWN 对账合同：真实 PostgreSQL `ALLOCATING→CREATING` dispatch barrier，外部创建已成功而 PG Binding ACK 丢失时不得盲目新建；官方 SDK Metadata 冻结，受信任 Native List/Connect/GetInfo 只有唯一完整匹配才允许 `BLOCKED_UNKNOWN→ACTIVE`；PG Fencing B 接管 A 的 `CREATING/UNKNOWN` 时仅能查询同一 Cube。**证据**：docs/retrospectives/DEV_M5_CUBE_CREATE_ACK_RECONCILE_20261011.md（Red 38148112088、Green 38148372940，14/14 PG/SDK 合同）。测试为 Fake Cube + PG，真实 Cube 实机继续 OPEN，不勾选正式 1.2/1.3。

- [x] A.6 **真实 Cube MicroVM 原生 SDK 最小生命周期 Demo**：在已有运行中的 CubeMaster/Cubelet/CubeAPI 和 READY 模板上，官方 `cubesandbox==0.7.0` 实际创建 2 次独立 Sandbox（均真实返回 ID），Guest 文件写入/读回、Native `Sandbox.connect(same_id)` 新 SDK 实例读取原字节、`kill()` 确认成功；运行退出码 0，未使用 Fake Transport。可复现脚本 `poc/sandbox/verify_cube_sdk_smoke.py`，证据 `docs/retrospectives/DEV_M5_REAL_CUBE_MICROVM_SMOKE_20261012.md`。**仅 SDK 实机 Smoke PASS**；Harness PG+真 Cube 以及真实 Hatchet A→B+Cube 联合测试尚未通过，1.2/1.3/2.x 保持 OPEN。

## 1. TDD 与集成开发
- [x] B.1（2026-10-12 控制层子切片收口）真实 Native Cube Create 显式传入已冻结模板；无 PG 的 SDK 参数负例覆盖缺模板拒绝、Metadata 不被修改及 Template 冻结；Red→Green 2/2，真实 PG/Fake Cube CI Head 38225131595 PASS。**证据**：docs/retrospectives/DEV_M5_JOINT_WORKER_CUBE_IMPLEMENTATION_20261012.md。仅 SDK 参数合同完成，不构成 B.2 联合实机 PASS。
- [x] B.2 实机联合 B03：同 Run、同 Hatchet Workflow、真实 Worker A SIGKILL→B 原生 Retry；真实 Cube ID、同 Guest 字节、PG A/7→B/8、旧 Owner/Scope 拒绝、销毁回执；独立进程 PID/退出码/Provider IDs、Guest 证据齐全。**2026-10-12 实机 PASS**：Run `m5-joint-c2e2deb3c5414190a61b03209c29fb81`，Workflow `b68e09ec-1a44-492e-9977-91572c7466f4`，Sandbox `5934b961fd72494094e891a497ee1490`；A PID 28410 / SIGKILL -9，B PID 29342 / Native Retry 1；PG 7→8、Guest 原字节一致、旧 Epoch/Scope 拒绝、RELEASED、真实脚本 exit 0。**证据**：docs/retrospectives/DEV_M5_JOINT_WORKER_CUBE_IMPLEMENTATION_20261012.md。仅 B03 联合子切片 PASS，DEV-M5 完整阶段仍 OPEN。
- [x] B.3 Worker Takeover 受控执行子切片 PASS：Inspector 经操作员认证的可信服务端发起固定 B03，真实 OS/Cube/PG 验证通过、持久证据可重启后查询。新 Evidence proof-c7b82a4c3c6d4a4d963e5aee8fbf52e5、新 Run m5-joint-8b90c55281864cfe8f055cb1de6fbb8d。见 docs/retrospectives/DEV_M5_INSPECTOR_TRUSTED_SCENARIO_20261012.md；其他场景与生产 IAM 保持 OPEN。
- [x] B.3a 首个受控 HTTP 执行合同（代码与负例）：固定 B03 Native Verifier，不接受客户端 Shell/任意命令；服务端显式 opt-in、操作员认证、来源边界、单活运行、独立证据 ID、原生输出校验、脱敏持久化、失败/未知禁止假 PASS。**证据**：docs/retrospectives/DEV_M5_INSPECTOR_TRUSTED_SCENARIO_20261012.md；真实 HTTP→Hatchet→Cube 联合 Gate 另见 B.3b，已 PASS。
- [x] B.3b Inspector HTTP→真实 Hatchet Worker A SIGKILL→B Retry→原 Cube Guest/PG Fencing 实机 PASS；新 Evidence proof-c7b82a4c3c6d4a4d963e5aee8fbf52e5、Run m5-joint-8b90c55281864cfe8f055cb1de6fbb8d、Workflow 2a4c51a8-8ade-43cb-b6f9-41a9958babbf、Sandbox 73d702e69a374e778bcae3ed79d1625a、A PID 226263 (-9)、B PID 227114 (Retry=1)、PG Epoch 8/RELEASED、Guest 连续性与重启 Inspector 后 GET 证明；E2E 退出码 0。**证据**：docs/retrospectives/DEV_M5_INSPECTOR_TRUSTED_SCENARIO_20261012.md。
- [x] 1.1 TDD 无可信 ExecutionContext、跨 Scope、过期 Lease、旧 Fencing、操作名伪造权限和未知 Capability 拒绝；先 RED 后 GREEN，Runtime 6/6、可信 Gate 6/6、真实 PG Cube Binding 15/15；无授权时 Adapter 不被执行。证据：docs/retrospectives/DEV_M5_PHASE_EXIT_AUDIT_20261012.md。
- [x] 1.2 完成真实 Cube Provider Allocate/Bind/Release 与 WorkspaceRef；**实机证据**：docs/retrospectives/DEV_M5_JOINT_WORKER_CUBE_IMPLEMENTATION_20261012.md。PG+Cube Live Run `m5-cube-live-4a8d7bf5d1a7470b9de6e4d699ab65dc`，Sandbox `c51b673619e0404da77913dda4e7eaf4`；真实 PG B/8 重连、Guest 原文件逐字一致及 RELEASED；同 Run Hatchet Worker 联合 B03 另见 B.2。范围不包含 OpenCode Shell/Git 或 in-flight Guest Fencing。
- [ ] 1.3 OpenCode Shell/Files/Git 真实 Cube Guest 路由、受信任会话/Worktree/环境冻结、Worker A→B 恢复和在途 Guest Fencing；Guest 探针首次真实看到 OpenCode 文件存在，但完整 Native Tool E2E 尚无 PASS，不得使用 Host Shell 替代。证据与后续门禁：docs/retrospectives/DEV_M5_PHASE_EXIT_AUDIT_20261012.md。
- [x] 1.4 模型-only 0 Sandbox、资源释放、跨 Scope 安全/CI/复盘：真实 Cube Provider Inventory Before/After = 0，PASS_REAL_PROVIDER_ZERO_SANDBOX；原真实 B03 Destroy ACK RELEASED；Scope/Lease 真实 PG 15/15 与新增单元 3/3，已纳入 CI。仅 POC/本地资源合同，不冒充生产容量。证据：docs/retrospectives/DEV_M5_PHASE_EXIT_AUDIT_20261012.md。

## 2. 阶段 Gate 与复盘
- [ ] 2.1 复验 拒绝过期及越权 的拒绝/故障合同，正例、负例和真实集成全部 PASS；无 SKIPPED 冒充通过。
- [x] 2.2 记录 WSL/Compose、Hatchet SDK、Cube Native 身份/ACK 和 Runtime 操作能力错配的根因、Red→Green 测试与风险；架构 Backlog 明确保留 OpenCode Guest/在途 Fencing 等未完硬门禁。证据：docs/retrospectives/DEV_M5_PHASE_EXIT_AUDIT_20261012.md。
- [ ] 2.3 代码 PR/CI、架构审查通过，确认无后续生产门禁被错误关闭后，勾选 Tasks 并归档该 OpenSpec。
