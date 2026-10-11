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

## Test-first and failure injection

正常验收：Worker A 在授权 Cube 中工作后中断 → Worker B 持有新 Lease 绑定同一 Workspace，恢复操作和已有文件。

安全负例：旧 Owner 或其他 Scope 访问 Workspace/执行 Shell → Fencing 和执行权限拒绝，禁止宿主 Shell 旁路。

## Exit gate

真实 Worker A→B 可信重连同 Workspace；跨 Scope 和旧 Owner 被拒，Shell/Git 仅在 Cube。。测试 Red/Green/Refactor、真实端到端、CI/架构、OpenSpec 完整核对及复盘均须留下可检索证据。阶段与生产 GO 明确区分。