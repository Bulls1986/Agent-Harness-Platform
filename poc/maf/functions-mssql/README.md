# POC-A A32/A33 — Python MAF + Azure Functions + MSSQL Durable

状态（2026-10-08）：本机 Docker 受控场景连续两轮 PASS；生产级验收 OPEN。
独立私有部署候选，不使用 DTS Emulator：MAF AgentFunctionApp + Azure Functions v4
+ Durable Functions MSSQL Provider + SQL Server。Azurite 仅存 Functions Host 信息，
不存储 Durable TaskHub/History。无真实模型、IAM、外部写工具或生产数据。

## 本机镜像、版本与安全范围

- mcr.azure.cn/mssql/server:2022-latest：Developer Edition CU27 16.0.4295.3，
  当前镜像 RepoDigest sha256:4402d880dd4c34bfa7d8705e56a86cd6c88da80a1f6bbbe741f999e76264a090
- mcr.azure.cn/azure-functions/python:4-python3.11：Python 3.11，Azure Functions v4
- mcr.azure.cn/azure-storage/azurite:3.35.0：与微软全球 registry linux/amd64 manifest 相同
- agent-framework-core==1.20.0，agent-framework-azurefunctions==1.0.0b260922 (beta)；
  Host 日志：DurableTask MSSQL 扩展版本 3.15.0
- Compose project maf-mssql-poc 专属网络/具名卷；仅回环地址公开本地端口：
  SQL Server 127.0.0.1:11433、Functions HTTP 127.0.0.1:17071

仅供本地 POC：Functions HTTP 使用 ANONYMOUS，且仅绑定 127.0.0.1；
生产必须使用可信 IAM/Policy，不得把 instanceId/requestId 当成授权凭据。
SQL Server Developer Edition 仅供开发与测试，不可作为生产许可依据。

## 重现步骤（PowerShell，仓库根目录）

随机 SQL 密码写到 .gitignore 排除的 .env.local；不覆盖已有文件：

    $envFile = 'poc/maf/functions-mssql/.env.local'
    if (!(Test-Path $envFile)) {
      $password = 'MafPOC-' + [guid]::NewGuid().ToString('N') + '!Aa1'
      Set-Content -Path $envFile -Encoding ascii -Value ('POC_MSSQL_SA_PASSWORD=' + $password)
    }
    $compose = 'poc/maf/compose-functions-mssql.yml'
    docker compose -p maf-mssql-poc --env-file $envFile -f $compose config --quiet
    docker compose -p maf-mssql-poc --env-file $envFile -f $compose up -d mssql azurite

第一次需在专用 SQL Server 中准备 DurableDB，要求
collation = Latin1_General_100_BIN2_UTF8。
初始化脚本仅使用专用容器内部的 MSSQL_SA_PASSWORD；支持重复运行，
已有数据库不会被删除或重新初始化（不打印密码）：

    python poc/maf/functions-mssql/init_mssql_db.py

确认数据库就绪后：

    docker compose -p maf-mssql-poc --env-file $envFile -f $compose up -d --build functions
    python poc/maf/functions-mssql/verify_handoff.py

测试脚本每次生成新 12 位十六进制 case ID，保持前次 TaskHub 历史；
先让两个原生 HITL Workflow 进入 WAITING，再 docker kill --signal KILL
终止 Functions Worker A，以 --force-recreate --no-deps functions 启动 Worker B。
确认相同 instanceId/requestId、Completed + 原生输出、
Prepare 各执行 1 次、批准 Action 1 次、拒绝 Action 0 次。
SQL Server/Azurite 过程中保持运行。

## 真实运行证据：WebCodex / 本机 Docker，2026-10-08

- Functions 健康检查 HTTP 200，Host 日志明确：
  'Using the mssql storage provider'，TaskHub 'MafMssqlPoc'。
- DurableDB 的 dt.Instances、dt.History、dt.NewEvents、dt.NewTasks
  等 MSSQL Storage Provider 对象真实存在且持续写入。
- 两轮独立 Worker A 强杀→Worker B 新容器恢复/HITL APPROVED、REJECTED
  **均 PASS**；已完成 Prepare 不重放；APPROVED 受控执行 1 次、
  REJECTED 0 次；状态接口原生输出也匹配。
- 两轮测试后查询 dt.Instances：Completed=5、Failed=1，
  dt.History=126；失败记录来自前期 fixture 命名问题，被完整保留。
- 初次 HTTP 500 是缺少本地 WEBSITE_HOSTNAME；之后 fixture handler
  命名 execute 覆盖了 Executor.execute，触发 source_executor_ids 参数错误；
  均已修复并通过两轮新实例的实际恢复测试。
- Docker 镜像拉取最初反复受 120s 命令超时打断；
  WebCodex 长时 Job 从微软中国区 registry 成功拉取。
  不能把同 tag 但不同 digest 的第三方镜像当作等价来源。

## 门禁说明

已证实单机 Docker 上的真实私有化存储 Provider + 跨不同 Worker 进程
HITL 恢复路径可运行；这已超出 DTS 开发 Emulator 的测试证据。
未证明正式生产跨物理节点 HA、SQL Server 生产授权/价格、框架 beta
的支持政策、外部 Tool SideEffectReceipt / Exactly Once、
Harness Same Run/Step/Attempt ID 绑定、OSS/Sandbox State、
真实 IAM/HITL 安全边界。**G1/G2/G6/G7/G8 整体仍 OPEN**。
本平台不自研 TaskHub，Harness 业务事实仍由 PostgreSQL 存储。

参考：https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-storage-providers

## 双 Worker 同时在线验证

见 [A34 前置并发双 Worker 实测报告](A34_CONCURRENT_WORKERS.md)。与上一轮顺序替换不同，第二个 Worker 在第一个被 SIGKILL **之前**已同时在线并连接 MSSQL；两轮单主机测试通过，但生产跨节点/完整 Same Attempt 仍未验收。

## A34 PostgreSQL Harness identity + version pinning

可选设置可信本地 POC_POSTGRES_DSN 后，双 Worker 脚本在原生 request_info 建立后通过 PostgreSQL ApprovalWaitStore 在同事务持久化 Run/Step/Attempt/Approval/native Instance/Request 和冻结版本；Worker B 先检查平台不可变绑定，再投递原生审批响应。此合并测试如不提供 DSN 会明确输出 platform_approval_attempt_binding=NOT_RUN。版本不匹配按 Adapter fail-closed 而不是交给 MAF 未验证的热升级机制。详见 [A34 边界](../A34_ATTEMPT_VERSION_FINDINGS.md)，不得把 WAITING 的 Attempt CREATED 误报成 RUNNING Attempt same-attempt replay。

## A34 本机 PostgreSQL + MSSQL 双数据库完整故障注入

2026-10-08 已在同一次真实跨 Worker HITL 测试里加入独立 PostgreSQL 平台 Run/Step/Attempt/Approval 持久绑定与冻结版本校验，独立数据库审计 PASS。见 [双数据库实验手册与证据](A34_PLATFORM_MSSQL_E2E.md)。该验收只覆盖审批等待阶段 Attempt CREATED 身份保持，不能提升为 RUNNING Attempt 同次执行恢复或生产级版本升级验收。
