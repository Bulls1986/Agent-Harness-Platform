# A34 / 平台 Attempt 绑定与 Workflow 版本恢复门禁

> 2026-10-08，状态：部分验证；不是生产架构 ADR，也不是整体 G6/G8 PASS。

## 为什么继续做

前一轮 A33 实证：在单 Docker Host 上，两套相同版本 MAF Python
Azure Functions Replica 同时使用 MSSQL Durable Provider，
Worker A 退出而 B 无需重启便能接续原生 HITL。
**但原生 Instance/Request 的保留，不足以证明平台 Same Attempt Resume。**

## A34 本轮可验证的事实

- 仅在官方原生 Workflow request_info 已真实进入等待、持有 Instance ID +
  Request ID 后，由平台 PostgreSQL 在 **一个事务** 中创建
  Conversation/Turn/Run/Plan/Step/Attempt、平台 Approval 和
  poc_maf_durable_approval_bindings。绑定的字段包括：
  平台 Run/Step/Attempt/Approval ID，Opaque Native Instance/Request ID，
  Native Workflow Name，冻结 Workflow Contract Version、
  Runtime SDK Version。不复制 MSSQL History/Checkpoint。
- 关系和保护：绑定 Approval FK；Run/Step/Attempt 关系由同一事务产生；
  Native Instance / Request 唯一；更新/删除不可变；Binding 不能与本地
  FileCheckpointStorage 的 checkpoint_ref 混用。部分字段缺失的请求
  在发生写入前拒绝；冲突 Rollback 不留孤儿事实。
- 恢复时，新 Worker 通过公开 HTTP API 查询 Native Pending Request，
  再调用平台 require_waiting_resume() 校验同一 Run/Attempt、
  Native Instance/Request、Frozen Workflow/Runtime Versions，
  检查 PostgreSQL Approval 为 PENDING、Run 为 WAITING_APPROVAL、
  Attempt 为 CREATED，及 Plan→Step→Attempt 的平台关联。
  只有全部吻合才允许向原生 HITL Response API 投递。
- 不兼容版本测试使用 fixture-v2 vs 已冻结 fixture-v1，
  检查 **Harness Adapter 必须拒绝**：属于预防性的 Fail Closed，
  并非微软 MAF 在真正升级到新版本后成功迁移/回放的证据。

## 已证明和未证明的分界

前次 A33 已在本地真实 MSSQL Durable Provider 上完成两轮并发双 Worker
接管，4 个 Completed / 84 条 dt.History。A34 本轮增加 PostgreSQL
真实集成与平台 Native Approval 绑定、版本错配负例；只有把平台 DSN
提供给完整跨 Worker 测试，并看到同一 Attempt ID 跨故障持续存在，
才记录本地整链 PASS。CI 独立 PostgreSQL 测试与静态合约校验同样
不能取代双数据库完整整链。

**平台 Attempt 在 WAITING_APPROVAL 阶段为 CREATED，而不是某个正在进行的
外部执行 Attempt 的原生 checkpoint 续跑。因此当前最多声称
Same Waiting State + Same Platform Attempt Identity 的映射，
不得声称 RUNNING Attempt 中途崩溃后 Same Attempt Resume 已通过。**

真正 A34 全部完成还需要：

1. 在原生 Execution RUNNING（非仅等待审批）期间注入故障，
   验证同 Run/Step/Attempt 且对已完成副作用没有盲目重试，
   根据 SideEffectContract 需要进入 UNKNOWN/Reconciliation。
2. 固定运行中 Workflow 的真实配置/模型/Runtime 版本；部署不兼容
   Worker 后验证原生回放失败表现、拒绝接管或版本隔离策略；
   没有在实例运行期间偷偷升级 Runtime 的假设。
3. 真实 Workspace/OSS 恢复与 Worker 实际环境版本校验、
   企业 IAM/Policy 可信审核来源仍为各自独立门禁。

证据入口：
- SQL: poc/maf/sql/007_durable_attempt_binding.sql
- Store: poc/maf/durable_approval_binding.py
- PostgreSQL tests: poc/maf/tests/test_durable_approval_binding_pg.py
- Local optional full join: poc/maf/functions-mssql/verify_concurrent_handoff.py
- 已通过双 Worker 实验: poc/maf/functions-mssql/A34_CONCURRENT_WORKERS.md
