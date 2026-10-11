# DEV-M3 / DEV-M5 第一开发切片 · TDD 证据与复盘（2026-10-11）

> 状态：**IN PROGRESS / 部分开发切片验收**。当前只开发两项平台安全基础能力，不表示 DEV-M3/DEV-M5 里程碑整体关闭。**PDLC-M0 已根据用户要求暂停**：尚未确认实际旧 PDLC 仓库与部署，不执行代码/Schema/API 盘点，也不猜测工程对应关系。

## 1. 当前实现

### DEV-M3 / HC-01 领域计划保护（受控首段）

- 新增 `poc/closed_loop/plan_guard.py`；沿用 Harness PostgreSQL 领域事实，冻结 Plan v1 的 recipe_digest/Provider Binding，支持幂等同内容提交，拒绝版本、摘要、Workflow ID 漂移。
- 引入 **Replan Intent** 的独立持久事实。重复同意图幂等，冲突意图拒绝；关键状态仅为 `BLOCKED_PROVIDER_QUIESCENCE`，不自动增加 `plan_version`，不冒称原 Hatchet Segment 已停止，更不创建 v2 影响原 Workflow。
- `admit()` 是目前仅供后续 Worker 集成的**可审计准入校验**，不是运行时已强制接入的 Gateway；既有两节点 Run 和 Worker 路径没有被此切片修改。禁止根据该校验器存在就声称旧 Worker 已可被全局 Fencing。

### DEV-M5 / HC-03 授权边界（纯逻辑，不是 Cube 实机）

- 新增 `poc/runtime_spi/trusted_gate.py`：`ExecutionClaim`（不可信请求）必须匹配可信服务侧 `ExecutionRecord` 的 Run/Step/Attempt/Execution/Plan Version、Provider Binding、Principal、Isolation Scope、WorkspaceRef、Runtime Adapter Version、OCI Digest、Owner、Fencing Epoch、Lease Expiry。
- 明确 Tool 权限由可信 Record 授权，Sandbox ID、Session ID、Workflow Payload 和模型声明**不赋予 Capability**。Shell/Files/Git 只有在匹配的可信 `SandboxRecord` 下准入；Model-only 无 Sandbox。
- **实际 Cube Provider / Lease 持久化颁发及刷新 / Worker A→B / 原生 OpenCode Guest 仍是 OPEN**。当前仅证明 Gate 在静态可信事实输入下 Fail Closed，不声称完全隔离或可以为 Host Shell 放行。

## 2. 测试先行与结果

1. Red：首先编写 `poc/closed_loop/test_plan_guard_pg.py` 和 `tests/test_trusted_execution_gate.py`。首次执行因两个实现模块不存在失败（`ModuleNotFoundError`，2 errors）。
2. Green：增加最小事实表与只读/写入事务 Gate 后，**10/10 首段测试 PASS**（M3 使用真实 Docker PostgreSQL 事务数据，M5 为可信授权记录纯函数负例）。
3. 与既有真实 PG/API/Model/SSE 回归一起 **27/27 PASS**，包括历史 Run 的数据库持久结果与取消/回放合同。
4. CI 显式纳入 M3 PostgreSQL 测试及 M5 无 Sandbox 授权负例；必须以 PR 具体 Head 上绿色检查为最终证据。

## 3. 故障与架构复盘

- **不得因用户要求“推进开发”而伪装已经具备 Replan v2 安全切换。** Provider Quiescence 是真实 Hatchet STOP/WAIT/Receipt 状态；目前没有足够证据。正确实现是先永久记录意图并阻断新版本执行，让旧 Worker 不确定的副作用仍由 HC-02/03 决策。
- **请求自带字段不是执行授权。** 本次发现现有 Sandbox POC 的 `ExecutionBinding(run_id,isolation_scope)` 过于粗，无法表达 HC-03 需要的 Owner/Fencing/Attempt/Workspace/OCI。新增纯 Gate 不覆盖旧 POC，生产写 Capability 必须经受信任持久执行事实和真实 Cube Provider 证明。
- **不跨界**：Hatchet Workflow/DAG/Retry 仍是 Engine 唯一权威；Harness 只写 Domain Plan 意图、授权核验，不实现自己的技术 Scheduler。
- **旧系统仓库未经确认就不能盘点**：PDLC-M0 保持 NOT_STARTED，本次未以名字相似的知识平台工程当作 PDLC 迁移仓库，没有修改现有 PDLC 代码。

## 4. 后续实测门禁（保持 OPEN）

| 里程碑 | 下一道明确开发 Gate | 说明 |
|---|---|---|
| DEV-M3 | Worker 执行入口真正调用冻结 Plan/Attempt/Segment 校验；真实 Hatchet Provider Quiescence → CAS 创建 v2 Plan/Segment +旧 Owner 拒绝 | 不确认旧执行安全停止就不能启动 v2 写侧任务 |
| DEV-M4 | ACK 丢失对账、Receipt UNKNOWN 和外部非幂等副作用 SIGKILL | 与 M3/M5 的接管测试联合推进 |
| DEV-M5 | 从 Harness PG/Policy 获取可信 Record，真实 Cube Allocate/Bind/Release；Worker A→B 同 Workspace、过期 Owner 拒绝 | 未经真实 Cube 证据不得声明 Sandbox 集成完成 |
| PDLC-M0 | **暂停，等待真正 PDLC 仓库和部署信息** | 不生成虚假盘点表、项目映射或迁移成果 |


