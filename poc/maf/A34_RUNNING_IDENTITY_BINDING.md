# POC-A / A34 — RUNNING Attempt 的 Native Instance 与版本固定绑定

2026-10-08。目标是尽快关闭“平台 RUNNING 身份能否安全、持久关联
原生 Durable Instance”的**数据合约**，不实现 Durable Scheduler。

## 已实现的最小事实

`poc_maf_durable_running_bindings` 属于 Harness PostgreSQL，保存：

- 平台 Run / Step / Attempt / Execution；
- 官方 MAF Durable Instance ID / Workflow Name；
- 冻结 Workflow Version / Runtime Version。

Execution ID 为主键，Attempt ID 与 Native Instance ID 独立 UNIQUE。
Schema 的 BEFORE INSERT 校验完整平台 lineage、MAF Runtime 类型、
活跃 RUNNING 状态和当前最新 Plan。数据库层拒绝 UPDATE / DELETE。
`DurableRunningBindingStore` 通过锁定 Run 行的独立数据库事务
`bind`，随后提供 `require_running`（只读校验预期 ID 与
版本，fail closed）。

`require_running` 不是授权凭据、不能替代 IAM/Policy，不获取
Execution Ownership，也不允许自行调用/重试非幂等 Tool。
真实工具派发需继续通过 `ExecutionOwnership.dispatch`。

## 已有快速证据

在**真实既有 PostgreSQL 实例**中，以 `BEGIN` 运行新增 DDL，
创建受控 Run/Plan/Step/Attempt/Execution + Native Binding：

- 首次合法绑定：PASS。
- 再次绑定同一 Instance/Execution：UniqueViolation，PASS。
- 更新 frozen runtime version：不可变 trigger 拒绝，PASS。

实验以 `ROLLBACK` 完结：不清理或覆盖历史 Task Facts。
编译及离线测试属于独立验证。

新增 `test_durable_running_binding_pg.py` 六组 PostgreSQL 用例，
CI 执行后才能进一步宣称完整数据库合约 PASS：跨连接读取、各
ID/Version 失配、重复 Native Instance、非法 SQL lineage、
UNKNOWN/superseded Plan 拒绝、验证绑定不自动产生 Tool 权限。

## 明确保留的缺口

- 原生 Native Instance 必须由可信 Adapter 通过 MAF 官方 API 建立，
  之后才有 Instance ID 可绑定。**Native 创建成功但 PostgreSQL
  Binding 尚未提交**的跨数据库故障窗口没有分布式原子性；
  orphan detection/reconciliation 仍 OPEN。
- **实际 MSSQL Native RUNNING Worker 崩溃 + 平台同一 Attempt**
  的 single-chain 受控实证仍 OPEN，不得把本地已通过的原生
  SIGKILL 与本次平台 PG Binding 两个独立证据当作一次证明。
- 不支持凭此固定绑定自动更换不兼容 Workflow/Runtime Worker。
  真正不兼容二进制 Worker 接管负例仍需验证。
- 完整 G6/G8、生产跨物理节点 HA、真实 Tool Receipt 均继续 OPEN。

方案不在 Harness 中复制 DurableTask TaskHub 或 Runtime 内部状态。
