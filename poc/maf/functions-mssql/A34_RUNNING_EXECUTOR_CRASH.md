# POC-A / A34：原生 RUNNING Executor Worker 故障重放验证

> 2026-10-08；本机原生 Azure Functions v4 + MAF 1.20.0 +
> agent-framework-azurefunctions 1.0.0b260922 + MSSQL Durable Provider。
> **本报告只证明本机受控 Non-LLM Executor 行为，不是 A34/G6/G8 整体通过。**

## 目标和严格边界

以前的 A33/A34 已证明 WAITING_APPROVAL 原生 Request 恢复、平台同一
CREATED Attempt 身份保持、冻结版本门禁。本实验故意在 **真正 RUNNING
Executor handler 中途**强杀 Worker A，观察另一已上线的 Worker B 会如何
处理未完成的工作，是否有重复派发入口。

未实现真实外部工具、数据库业务写、SideEffectReceipt、幂等键，也没有
真实平台 Native Instance ↔ RUNNING Attempt 不可变绑定。因此观察的
`dispatch_observed` 仅是受控文件中的执行入口标记，**不是外部实际副作用**。

## 隔离与重现

- Docker Compose：`poc/maf/compose-functions-mssql-a34-running.yml`
  项目 `maf-mssql-a34-running`；两个同镜像 Functions Worker 使用
  127.0.0.1:17091 / 17092。
- 独立 MSSQL 数据库 `DurableA34Running`、TaskHub `MafMssqlRun`，
  使用原有已运行的 SQL Server / Azurite 容器，仅消费后端；不清理任何
  MSSQL History，也不重建原 A34 / A33 容器。
- 镜像通过 `Dockerfile.a34-running` 在本地已经验证的
  `maf-mssql-poc-functions:latest` 镜像上仅覆盖 Workflow 文件；
  不重装 SDK，不拉取不同来源的 Docker 基础镜像。
- 先仅启动 Worker A，`Prepare` 发出消息后进入
  `RunningExecutionProbe.run_long`，记录 `dispatch_observed`，
  使用 110 秒可见延时模拟执行过程；此时 native instance 非终态，
  `completed_observed=0`。
- 再启动 Worker B，确认两个容器同镜像同时在线，直接
  `docker kill --signal KILL` 杀掉 Worker A；B 不重启。
- **不再发起第二个 Workflow 请求，不手工触发重试，不编辑 MSSQL
  TaskHub 或其内部 lease/history**；等待原生 Provider 决策。
- 重现入口（须使用已有隔离环境、忽略的本机数据库 secret）：

```powershell
python poc/maf/functions-mssql/init_mssql_db.py DurableA34Running
docker build --pull=false -t maf-mssql-a34-running:cached -f poc/maf/functions-mssql/Dockerfile.a34-running poc/maf/functions-mssql
python poc/maf/functions-mssql/verify_running_handoff.py
```

## 首次真实运行结果（本机 Docker；不依赖平台 PostgreSQL）

- native Instance：`77b30c9ab5ae473e8bbed034d3019cc6`；
  MSSQL `dt.Instances.RuntimeStatus=Completed`、该 Instance
  `dt.History=12`。
- Worker A：`dd3df17a5008`，B：`bf63fd9c51b7`；
  B 接续且未重启。
- `Prepare` 观测 1 次；**RUNNING Executor 入口观测 2 次**；
  Executor 完成观测 1 次。
- SQL Server、Azurite 未重启。受控 Marker 位于
  `functions-mssql/markers`（忽略目录），此前历史不清理。

## 第二次全新 Instance 独立复验（同日）

- native Instance：`fff0761977e6435eacb9212905e36b7d`，MSSQL
  `RuntimeStatus=Completed`、该 Instance `History=12`。
- Worker A：`c309550ab29b`，B：`df5cde74a5f0`；B 在线接续、未重启。
- `Prepare=1`、`dispatch_observed=2`、`completed_observed=1`；
  与第一轮一致。**两轮独立原生 RUNNING 故障实验均 PASS**。
- 此轮显式打印 `platform_execution_state=NOT_RUN` 与
  `platform_reconciliation_state=NOT_RUN`，不把原生成功外推为平台联动。

原生 Workflow 最终完成，**但中断中的 Executor Handler 被再次调用**。
这直接否定“原生 Durable Workflow 已完成 ⇒ 未确认副作用只执行一次”
这种推导；不能把上层一个 Attempt ID 误当成原生执行物理唯一性。

## 平台语义与未完成验收

- 对本机实验的 `NON_RETRYABLE` / 已 dispatch 结果不确定场景，
  平台既有 `RecoveryCoordinator` 语义是
  `UNKNOWN → PENDING Reconciliation`，禁止 New Attempt/blind retry。
  **该语义已有 A28 PostgreSQL 合约测试，但尚未与本次真实 Native
  RUNNING 崩溃在同一个数据库执行事实中联合验收。**
- 平台即便记录 UNKNOWN，也不会自动关闭微软 Durable Engine 内部
  Executor 的再次调用。如果业务副作用在 MAF Executor 内直接发生、
  未经过 Harness-controlled Execution/Tool Adapter 的幂等、
  admission 与 reconciliation 门禁，将可能重复执行。
- `platform_running_same_attempt` 依然 `NOT_PROVEN`；
  本次 native instance 终态只证明底层重放的后果，
  不能证明全链 Same Run/Step/Attempt 恢复契约成立。
- 真实 Workflow 升级不兼容 Worker、跨物理节点、Native HTTP
  Response 中途强杀、外部 Tool Receipt、OSS Workspace、
  生产许可与框架 prerelease 支持均另有 OPEN Gate。

**下一步**：将同一次 RUNNING Native Executor 崩溃与 Harness
Run/Step/Attempt/Execution 的真实 PostgreSQL 事实、安全副作用
Admission/UNKNOWN 紧密绑定；随后做真实版本不兼容 Worker 接管负例。
不 fork 或复制 DurableTask 内部实现。
