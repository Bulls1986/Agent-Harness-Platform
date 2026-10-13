# Design · DEV-M5 Cube 可信执行与 Coding Runtime

## Logical ownership

Harness PG 持有业务 Run/Plan/Step/Attempt、验证、审批、Receipt/UNKNOWN 与最终事实；Hatchet 持有 Workflow/DAG/Queue/Retry 和 Worker 技术事实。AgentRuntime、SandboxProvider、Process/Durable SPI 可替换。代码不得因实施便利改变已冻结的 HC-01/02/03 与 G01–G20。

## Interfaces and dependencies

HC-03 已冻结；DEV-M3/4 联合接管用例。映射 DEV-HC-03 / HC-03。对外仅使用已授权的 ExecutionContext/Resource Reference，不复刻企业 IAM/OSS/备份/MCP 治理。

## Implementation slice

SandboxProvider→Cube Scope/Lease/Fencing/WorkspaceRef 绑定、按需分配释放和 OpenCode Coding Guest；模型-only 0 Sandbox，禁止 Host Shell 兜底。

### 第二开发切片：持久化逻辑 Execution Owner Epoch 与 Receipt 门禁

- `ToolRecoveryOwner` 在 Harness PG 中以 Execution 为键持久化当前 `owner_id/fencing_epoch/lease_expires_at`，只允许在数据库服务器时钟判定旧 Owner Lease 到期、对应非幂等 Tool 状态 UNKNOWN、Run/Plan/Provider Binding 一致时，通过锁与 CAS 提升 Epoch。此 Permit 仅供**读取外部事实并补录 Receipt**，不赋予 Host Shell/Files/Git、Tool 重派发或 Cube 调用能力。
- `ToolReceiptJournal.reconcile` 的确认事务与现有当前 Owner/Epoch/Lease 同锁校验，排除外部查询与 Receipt 提交之间的夺权竞态；遗留未登记 Recovery Authority 的 POC Journal 内部调用维持原有行为，正式运行时入口仍需要统一接入 HC-03 AuthZ。
- 实际 Hatchet Native Retry 的 A/7→B/8 是**逻辑 Owner 交接**。真正 Hatchet Worker A 进程 SIGKILL→Worker B 进程领取并验证 Sandbox Workspace/OCI/Fencing 是下一门禁；不得将此切片等同实机 Cube/Worker B03/B05 PASS。

### 第三开发切片：真实物理 Hatchet Worker A→B（仅无 Sandbox 的非幂等账本）

- 在共享外部 Hatchet Engine PG 的多进程 Fleet 中，以独立进程 Worker A/B、实际操作系统 SIGKILL 故障注入验证 Hatchet 原生任务派发、受限 ExecutionOwner 的 PG Fencing CAS 与恢复 Receipt。Owner A/7 与 B/8 必须分别对应实际进程角色，不能仅在同一个 Worker 内修改 Owner 字符串。
- 此路径使用受控的外部 synthetic ledger，**不分配 Cube Sandbox**；成功只能证明物理 Worker Crash/Replacement 与 Receipt 接管，不等同 Cubes WorkspaceRef/Git/Shell 权限、Sandbox connect/fencing 和 guest 内核隔离。
- 新 Worker 只有查询/补录已有 UNKNOWN Receipt 的权限，不得重发非幂等操作或使用默认 Host Shell 兜底；原 Worker A 恢复后的新写请求必须受当前授权与 Fencing 约束。

### 第四开发切片：Native Cube SDK / Harness PG Binding（合同 PASS 不代表真 MicroVM）

- PG 为 Execution 保存冻结 Run/IsolationScope/WorkspaceRef/EnvironmentDigest、Owner/Fencing/Lease（PG Server-clock）、Cube Sandbox Locator/Generation/生命周期 `ALLOCATING/ACTIVE/BLOCKED_UNKNOWN/RELEASING/RELEASED`；创建未知不得盲重建，释放未知不得伪造 ACK。
- 真实 Native `cubesandbox` Python SDK Adapter 仅负责 Cube 自身 Create/Connect/Files/Destroy，Cube Master/let 内部调度由其实现；调用前后的 Harness 可信 Binding/Fencing 校验在 Gateway 中完成，旧 Owner、错误 Scope/Workspace/Environment、过期 Lease 必须拒绝，不退回 Host Shell 或本地文件目录。
- SDK 绑定测试以真实 PG + Fake Transport 验证控制平面逻辑；假 Transport 不等于真实 Cube MicroVM、跨宿主隔离、Guest Tool 完整授权，也无法阻止已经进入真实 Guest 的 in-flight 调用。真实验收必须由 `dev-m5-cube-live.yml` 显式使用实际 Cube API/Template/Proxy，创建真实 Sandbox、保存文件、经另一 Native SDK 实例重新连接同一 Sandbox ID、确认文件保留、destroy；未配置必须 FAIL CLOSED，不得 SKIP。
- 本轮没有可用真实 Cube Endpoint/Template，因此真实 M5 1.2/1.3 仍 OPEN、Production NO-GO。

### 第五开发切片：Cube 原生创建 ACK 丢失、不可重派与崩溃恢复

- Harness PG 的 Sandbox Binding 在真正调用 Cube `Sandbox.create(metadata=...)` **之前**持久写入 `CREATING`（控制层 durable dispatch barrier）；即使 Cube 创建已经完成但客户端在写 Provider ID 前死亡，也不得再对相同 Execution 调用 Create。
- 创建时向 Cube 原生 Metadata 注入平台根据冻结事实生成的相关键：Execution/Run/IsolationScope/WorkspaceRef/Environment/immutable allocation generation；此 Metadata 是定位和审计信息，**不是授权凭证**。Worker B 失去旧 Creator ACK 后只能 `BLOCKED_UNKNOWN→(native list + connect + get_info unique proof)→ACTIVE`；无匹配、多匹配、错误 Scope/Workspace/Generation、不可信列表均拒绝恢复，不重新创建 Sandbox。
- `CREATING` Worker A 失联并且 PG Server-clock Lease 到期时，Worker B 只可经 Scope/Workspace/Environment 一致性和 Owner/Epoch CAS 把它转入 `BLOCKED_UNKNOWN` 并核实既有原生 Cube；绑定的 `binding_generation` 递增不改变原创建标识。
- 真 PostgreSQL + Fake Cube Transport 执行 Red→Green 故障合同；官方真实 Python Cube SDK 的 `create/list/connect/get_info` 参数由 Mock SDK 单元测试确认。**这些结果不能计入真实 Cube MicroVM Gate**；物理 Hatchet A→B+Cube Guest 数据保持、OCI/Guest Fencing、跨 Scope/Principal/Repo 仍需独立实机验收。

### 第六开发切片：真实 Cube Native SDK MicroVM 创建/重连的首个实机证据

- 使用已经运行的单节点 CubeSandbox，而不是仅根据 Docker 容器清单推断服务不存在。前置检验 Cube API /health、CubeMaster/Cubelet Node Ready、模板真实 READY Replica。API 启动时与模板副本未健康的创建失败均属于红色环境诊断证据，不得冒称创建成功。
- 官方 Cube Python SDK `Sandbox.create(template=...)` 真正创建 MicroVM；Guest SDK `files.write/read`；通过 `Sandbox.connect(same_native_id)` 建立第二个 SDK 连接，并读取同一原字节；执行原生 `kill` 收到销毁确认。测试不使用 Fake Cube、Docker 代替 Sandbox、Host Shell 文件回退。
- 已两次完成真实本地 MicroVM Smoke 并记录匿名真实 Sandbox ID（2026-10-12，详见 `docs/retrospectives/DEV_M5_REAL_CUBE_MICROVM_SMOKE_20261012.md`）。常规 PG 合同 CI 仍无法代替真实 Cube 实机；仅当真正携带 Harness PG 权威 Binding/Fencing、真实物理 Hatchet Worker A→B、Guest Workspace 数据保持及跨 Scope/旧授权拒绝后，才可以评估正式 1.2/1.3/2.x 退出 Gate。

### 第七开发切片：真实 Harness PG + Cube Native MicroVM，同 Workspace Owner Fencing

- `verify_cube_live.py` 在本机启动一个隔离真实 PostgreSQL 16，配合已运行的 CubeMaster/Cubelet/API/Proxy 与 Ready 模板验证：Harness PG 落库 Sandbox/Run/Scope/WorkspaceRef/EnvironmentDigest/Owner/Lease/Fencing，Native Cube SDK Create/Files.Write/Files.Read，PG 服务器时钟 A/7→B/8 接管、旧 Owner 被拒绝，新 `PgFacts` + Native SDK Connect 同 ID 读原字节，Cube Native Kill 与 PG Release 同步确认。已取得真实 Sandbox ID、Run ID、Workspace ID、退出码 0；详见 `docs/retrospectives/DEV_M5_REAL_PG_CUBE_FENCING_20261012.md`。
- **这仍是同一进程内的逻辑 Owner 转移**，不等于物理 Hatchet Worker A→B + Cube 的联合容灾，也不代表异步 Guest 内已进入执行的命令可以被 PG Fencing 撤销。新增的 `verify_hatchet_cube_worker_takeover.py` 须独立以实际 A SIGKILL、原生 Hatchet Retry、原 Cube ID/Guest 数据、B SDK Connect/PG Epoch/Release 的实机证据判定，保持 Test-first，未测试即 OPEN。

## Test-first and failure injection

正常验收：Worker A 在授权 Cube 中工作后中断 → Worker B 持有新 Lease 绑定同一 Workspace，恢复操作和已有文件。

安全负例：旧 Owner 或其他 Scope 访问 Workspace/执行 Shell → Fencing 和执行权限拒绝，禁止宿主 Shell 旁路。

## Exit gate

真实 Worker A→B 可信重连同 Workspace；跨 Scope 和旧 Owner 被拒，Shell/Git 仅在 Cube。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。