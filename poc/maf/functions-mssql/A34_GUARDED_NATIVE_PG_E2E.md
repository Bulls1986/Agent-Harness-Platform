# POC-A / A34：原生 MSSQL Worker SIGKILL × PostgreSQL Attempt × 受控工具写入（单链实测）

> 2026-10-08；本地 Docker Desktop 单主机；**受控 HTTP 工具写入**，
> 不是生产真实 MCP/企业副作用的 exactly-once 证明。
> 本报告记录一次完成的真实 Native Durable Worker 故障注入。

## 验证目标及执行链

1. 独立 Docker Compose 项目 `maf-mssql-a34-guarded`，
   MSSQL DB `DurableA34Guarded`、TaskHub `MafMssqlGuard`；
   SQL Server、Azurite 使用原有运行实例，不清理原有历史。
2. PostgreSQL 中创建一个真实 RUNNING Run/Step/Attempt/Execution
   （`side_effect_class=NON_RETRYABLE`），冻结 Workflow/Runtime
   Version；注册 `poc_execution_ownership` 一次 Worker A/Fencing 1。
3. 用官方 Azure Functions `AgentFunctionApp` 启动新 Native
   Durable Instance，经 `Prepare` 限定时间内提交不可变
   `poc_maf_durable_running_bindings`。Instance 并非平台主键。
4. Native Executor `@handler` 通过 `host.docker.internal`
   调用临时受控 HTTP Tool Gateway。Gateway 的提交前置条件为真实
   PostgreSQL A29 `poc_execution_ownership` + RUNNING 任务身份、
   有效 Lease、Fencing Token、固定 Native Instance 和版本。
   `UPDATE ... SET dispatched_at` 首次返回 1，事务已提交才写入
   **独立 Tool Sink 文件回执**；同一 Execution 再次进入返回 409。
5. Tool Sink 已写 1 次而 Native Handler 仍处于睡眠窗口时，
   Worker B 加入并运行，Worker A SIGKILL。B **不重启**，同一
   Native Instance 原生重新派发中断的 Executor。
6. 第二次 Handler 请求 HTTP Tool Gateway 返回
   `409 REPLAY_BLOCKED`，工具未第二次写入。MAF Native
   Activity/Workflow **Failed**，错误
   `HARNESS_TOOL_REPLAY_DENIED`（设计上 fail closed）。
7. 可信故障注入端通过独立 PostgreSQL 事务按现有
   RecoveryCoordinator A28/A29 的安全分类规则，将唯一 Attempt
   和 Execution 标记 `UNKNOWN`，撤销 Owner/Fencing 变为 2，
   创建 `PENDING Reconciliation`。**该 E2E 中状态更新由受控
   SQL 测试入口执行，并非调用 Python RecoveryCoordinator 方法**；
   该方法本身另由 CI 专项 PG 合约验证。

## 本机真实实验结果

- Native Instance：`51a9f9d38b3542f2b86d152b9b13278a`。
- Worker A 被 SIGKILL：`255788ffa39d`；
  Worker B：`2eeeb874d91a`，没有重启。
- 原生 Executor Handler 进入 **2 次**；
  HTTP Gateway 响应顺序：**admitted → denied**。
- Tool Sink 实际回执 **1 次**；受控 HTTP 拒绝 **1 次**。
- Native MSSQL `dt.Instances.RuntimeStatus=Failed`；
  本实例 `dt.History` **12 行**；
  随后官方 Native HTTP Status 也返回 **Failed**，
  失败原因是 `HARNESS_TOOL_REPLAY_DENIED`。
- PostgreSQL Attempt 数量 **1**；Attempt/Execution
  `UNKNOWN`；Fencing Token **2**；
  Reconciliation `PENDING`。
- 原生 Durable 实例未被重新提交、MSSQL TaskHub 未被写入或手工
  修改，历史数据没有删除。

**判定：PASS — 单次 Worker SIGKILL + 原生 Executor 重入 +
实际 PostgreSQL 派发门禁 + 受控外部 HTTP Tool Sink 只写一次 +
平台安全 UNKNOWN/Reconciliation。**

此处的“安全”意味着**不允许第二次非幂等派发**；任务可能失败并等待
人工/外部回执对账。不保证业务工具真的 exactly-once，也不能把 Native
Workflow Failed 宣称为成功恢复任务结果。

## 重现（只在隔离开发机）

使用已启动的 SQL Server/Azurite/PostgreSQL 容器、原有忽略的
`functions-mssql/.env.local`，不访问生产工具。需先存在本地
`maf-mssql-a34-running:cached` 镜像。

```powershell
python poc/maf/functions-mssql/init_mssql_db.py DurableA34Guarded
docker build --pull=false -t maf-mssql-a34-guarded:cached -f poc/maf/functions-mssql/Dockerfile.a34-guarded poc/maf/functions-mssql
python poc/maf/functions-mssql/verify_guarded_native_handoff.py
```

`verify_guarded_native_handoff.py` 在进程生命周期内短暂通过
`0.0.0.0:17105` 暴露临时 POC Gateway 供 Docker Desktop 连接，
每次仅接受新生成的随机 Case + 独立 Token，结束即关闭和删除
Token 文件。生产环境绝不能暴露该临时 Gateway；真实 Tool/HTTP
必须使用企业已有的 IAM、网络和 MCP 治理体系。

## 仍然 OPEN

- 真正生产 MCP/外部业务写与独立可信副作用 Receipt 的语义；
  本次工具端只是带真实写入回执的受控本机 HTTP fixture。
- 平台 UNKNOWN 到真实业务核对/补偿的自动化闭环；
  本轮人工注入状态，未实现 Reconciliation Engine。
- 原生版本不兼容 Worker 实际接管负例（A34 P0）。
- Native Instance 已启动而 PostgreSQL Binding 还未提交，
  以及原生 Response HTTP 投递中途断开的跨库窗口（A34 P1）。
- 跨物理节点 HA、生产级 MSSQL 支持/许可、MAF prerelease SLA、
  G6/G8 等生产门禁。

不 fork MAF，不复制 DurableTask 的 TaskHub/Lease；把不可确认的
副作用保持 UNKNOWN 是平台任务级恢复协议，而非框架内核改造。
