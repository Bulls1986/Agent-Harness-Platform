# POC-A G2/G6 / RecoveryPoint 引用语义（增量）

> 2026-10-09。**本地真实 PostgreSQL 4/4 PASS**，不代表 MAF 原生 checkpoint 已恢复，更不代表 G2/G6 整体 PASS。

## 平台职责和最小事实

- `poc_recovery_points` 已有字段 run_id/step_id/attempt_id/runtime_checkpoint_ref/workspace_state_ref；增量 SQL 011 补充 runtime_type、repository_revision_set、environment_fingerprint、sandbox_snapshot_ref、provider_fingerprint，并为恢复点引用加**不可修改**触发器。
- `RecoveryPointStore.record` 在真实 PG 事务中验证 Run、Step、Attempt 的血缘及 RUNNING 状态、冻结 Runtime 类型；平台只存 **opaque reference**、仓库 revision、环境/Provider 指纹，不保存 MAF 内部 History/Checkpoint JSON、Sandbox/OSS payload。
- 冻结环境指纹是恢复候选的必要条件；Native checkpoint 引用必须配套 Provider 指纹；Sandbox Snapshot 只能作为 Workspace 恢复的可选参考，不能单独构成安全恢复。
- `choose` 只挑原 Attempt 最新 RecoveryPoint，遇到 Runtime、Provider、环境指纹不匹配、缺少所需 Runtime/Workspace Capability，一律返回 `RECOVERY_INCOMPATIBLE` / `RECOVERY_UNSUPPORTED_*`；不得自动选更旧版本继续，也不得推测 checkpoint 可用。
- 有 Opaque Checkpoint 的合法引用只得到 `CANDIDATE_REQUIRES_PROVIDER_VERIFICATION`，**真正的有效性验证与 Resume 仍需要 Runtime Adapter 公开 API**；只有 Workspace 状态引用时得到 `STEP_BOUNDARY_REQUIRES_SEPARATE_DECISION`，不假装 Same Attempt Resume。

## 本地证据

`test_recovery_point_store_pg.py` 使用独立 Docker PostgreSQL：
1. Run/Step/Attempt 正确血缘、冻结 Runtime 与外部引用的持久化读取；引用 UPDATE 被 PG Trigger 拒绝；可以追加新恢复点。
2. 跨 Run/Attempt、错误 Runtime、缺 Workspace/Snapshot 血缘、缺必要指纹均拒绝。
3. 未存在 RecoveryPoint、Runtime/Workspace Capability 不支持、Provider/环境不兼容，均明确 fail-closed。
4. Workspace-only 引用不宣称同一 Attempt 恢复。

**4/4 PASS**。同一隔离 PostgreSQL 上回归非幂等 Tool Receipt **5/5 PASS**。没有调用真实 MAF Durable checkpoint/resume，没有恢复 Workspace 内容，也没有企业 OSS PIN / Artifact 存取验证；这些门禁继续 OPEN。
## 2026-10-09 / 真实 MAF FileCheckpointStorage 跨进程恢复（新增）

`verify_native_recovery_point.py` 连接真实 PG：进程 A 用 MAF Workflow `request_info` 和官方 `FileCheckpointStorage` 持久化原生 Checkpoint，平台记录同一 Run/Step/Attempt 的 Opaque RecoveryPoint；进程 A 退出后，进程 B 使用 PG `choose` 并验证 Native `list_checkpoints`，执行真实 `workflow.run(checkpoint_id=...)`，验证 Native RequestId 相同，再用 REJECTED 响应无工具副作用完成。另一个独立进程用错误 Provider 指纹被拒绝。

**1/1 PASS**：两个不同 Python 进程 + 实际 MAF 公开 SDK + PG RecoveryPoint，Same Run/Attempt 身份保持。这是 FileCheckpointProvider 的 WAITING 请求恢复，不等于官方 MSSQL Durable RUNNING Executor same-attempt、Workspace Restore 或端到端 Tool Receipt 一致性。

