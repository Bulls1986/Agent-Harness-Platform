# POC-C / C05：Temporal OSS Server + PostgreSQL 自托管基线

> 2026-10-08 | **本地真实 OSS Server + PostgreSQL 技术实证 PASS**
>
> 不是 `start-dev`，但仅单机 Docker Compose、无 TLS/HA/Backup /
> 企业秘密管理。**不等于正式生产部署、跨节点容灾或总体 G1/G6 PASS。**

## 真实服务和责任

| 层 | 实际版本与隔离 |
|---|---|
| Temporal OSS | `temporalio/server:1.31.0`，`poc-c-temporal-oss`，仅宿主机 loopback `127.0.0.1:17234` |
| SQL init/namespace | `temporalio/admin-tools:1.31.0`，独立初始化 `temporal` 与 `temporal_visibility` 正式 SQL schema，namespace `default` |
| Persistence | `postgres:16-alpine`，`poc-c-temporal-pg`，持久卷 `poc-c-temporal-oss-db`，PG 端口**不发布** |
| SDK / Workflow | 官方 `temporalio==1.34.0`，重用 C02–C04 Workflow/Worker/Activity，**不改版业务逻辑** |

Schema/bootstrap 的思路来自 Temporal 官方
[samples-server/compose](https://github.com/temporalio/samples-server/tree/main/compose)
与[自托管指南](https://docs.temporal.io/production-deployment/self-hosted-guide/deployment)。
旧 `temporalio/docker-compose` 已归档。本 POC 的裸 Compose
只是本机单节点技术环境；生产应另按企业运维与安全要求部署。

## C05.1 Worker SIGKILL：原位继续、Verifier/Replan

同一原生 Workflow 的 v1 独立 Verify 拒绝坏 Document Fixture；
Worker A 真正强杀后，B 在同一 Task Queue 继续原生审批等待，
接收到 `APPROVED` 才进入 Plan v2 并完成独立 Verify；
单 Workflow 公共 SDK History **33 个事件、4 次完成 Activity**。
另一个实例的 `REJECTED` 直接失败而不执行 Plan v2。

从 Temporal **自己的 PostgreSQL** 直接查询（截至当时的累计值，
并非单个 Workflow 的事件数）：
`executions=4`、`history_node=32`、
`executions_visibility=4`。

这两个受控 Agent-A/B Adapter 仍是固定 fixture，不是两个真实模型
或代理运行时；外部工具 Exactly Once/SideEffect Receipt 仍 OPEN。

## C05.2 Temporal Server 真停机后，PG History 保留并继续

- 在 `WAITING_APPROVAL` 且 v1 Verify 已失败时强杀 Worker A。
- 停止真实 `poc-c-temporal-oss` Server 容器；独立
  `poc-c-temporal-pg` **保持运行**。
- SQL 查询累计 `history_node`：Server 停止前 **61**、
  Server **完全离线时 61**；没有丢掉已提交的 Native History。
- 真重新启动 Server，由独立 Client/Worker B 重新 Query 同一
  Native ID，审批后 Plan v2 通过。
- 单 Workflow Native History 仍 **33 事件 / 4 Activity 完成**；
  `history_node` 累计在继续执行后增加至 **72**。
  数据库累计差值**不等于单实例事件差值**。
- Native Workflow ID 与平台生成的 Run ID 始终不同；两个
  平台 Attempt ID 在 Worker/Server 重启期间保持原值。

**判定：C05 OSS Server + PG 自托管持久化/本机故障恢复 PASS。**
这验证了 Temporal 自身历史恢复，**尚未验证 Harness Run/Step/
Attempt/Execution 自有 PG、Tool Receipt/UNKNOWN/版本升级、HA/DR**。

## 复现（仅开发机）

复用当前 `poc/temporal/workflow.py`、
`verify_local_handoff.py`、`verify_server_restart.py`，
不要清理已有 DB/History。

```powershell
$env:POC_C_TEMPORAL_DB_PASSWORD = '<unique-poc-only-db-password>'
docker compose -p poc-c-temporal-oss -f poc/temporal/compose-oss-postgres.yml up -d

$env:POC_C_TEMPORAL_ADDRESS = '127.0.0.1:17234'
python poc/temporal/verify_local_handoff.py

$env:POC_C_TEMPORAL_CONTAINER = 'poc-c-temporal-oss'
$env:POC_C_TEMPORAL_POSTGRES_CONTAINER = 'poc-c-temporal-pg'
python poc/temporal/verify_server_restart.py
```

首次启动的 Schema Setup 是**一次性操作**。重复验收时不要对
非空数据库盲目重新初始化，也不要执行 `docker compose down -v`
删除持久卷。随机测试口令只在本地临时设置，不要使用真实 LiteLLM Key。

## 退出边界 / 下一阶段

| Gate | 已证实 | 仍 OPEN |
|---|---|---|
| G1 | Temporal OSS Server + 独立 PG 本地可自托管 | 总体平台自托管协议链路、企业安全/运维 |
| G2 | Temporal Native History 自有 PG，独立于 Worker | **Harness** Domain Task Facts 和 Artifact/Evidence 引用链路 |
| G6 | Worker/Server 崩溃下同 Native Workflow 继续 | SideEffect UNKNOWN/Receipt、任务级恢复、版本与 Sandbox |
| G3 | 未在此实验测试 | Responses-compatible + Typed Events/SSE 桥接 |

**下一步直接转 C06/C07：平台独立 Task Facts + Activity 安全
Retry/UNKNOWN/Reconciliation，而不是继续模拟数据库物理故障。**
