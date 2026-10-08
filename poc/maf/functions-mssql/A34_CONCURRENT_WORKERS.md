# A34 前置验证：MAF Azure Functions + MSSQL 双 Worker 并发接管

**2026-10-08：本地单 Docker Host 子目标 PASS × 2；A34 Same Attempt / Version 整体 OPEN。**

这是 A33 自管 Durable 后端的在线并发 Worker 补充实验，
不等于 A34 中 Harness Run/Step/Attempt 映射已完成，也不是跨物理节点 HA。

## 复现部署

基于 [A32/A33 单 Worker 自托管 POC](README.md)，复用现有 SQL Server
maf-mssql-poc-mssql-1、Azurite maf-mssql-poc-azurite-1 和本地镜像
maf-mssql-poc-functions:latest。A34 单独使用 DurableA34 数据库
（BIN2_UTF8）、maf-mssql-a34 Compose Project、17081/17082 回环端口。
不改动原先的 DurableDB，不删除旧测试记录或卷。

两个 Functions 容器是同一应用的两个副本：相同 MAF Workflow、
镜像、MSSQL Database 和 TaskHub；不同 Host ID
maf34workera / maf34workerb。不同应用不得随意共享 TaskHub。

从仓库根目录运行：

    python poc/maf/functions-mssql/init_mssql_db.py DurableA34
    docker compose -p maf-mssql-a34 --env-file poc/maf/functions-mssql/.env.local -f poc/maf/compose-functions-mssql-a34.yml config --quiet
    python poc/maf/functions-mssql/verify_concurrent_handoff.py

测试流程：

1. 停止本专项旧 Worker B（如有），重建 A，确认 A 的 HTTP 健康检查
   和日志明确表明使用 mssql provider 与启动 TaskHub worker。
2. 只有 A 在线时创建两个 MAF 原生 request_info 等待 Workflow，
   保存原生 Instance/Request ID。Prepare 各 1 次、Action 0 次。
3. 启动 B；确认 A/B 同时运行且真实 Docker Image ID 相同；
   B 通过自身 HTTP API 查到 A 创建的相同 Instance/Request ID，
   两个日志均明确显示使用 MSSQL Provider。
4. 强制 SIGKILL A；B 容器、SQL Server、Azurite 保持不变。
   通过 B 的 HTTP API 分别 APPROVED 和 REJECTED。
5. 两实例都需 Completed；批准输出 SIMULATED_EXECUTION，
   拒绝输出 DENIED_NO_EXECUTION。Prepare 不重放、批准动作正好一次、
   拒绝零次；MSSQL dt.Instances + dt.History 必须有对应实例及历史。
6. 每次自动生成新的 case ID，保留历史，不清库。

## 本机真实证据

- 第一次：Worker A=ed6f381e671d，B=240b28140575；两实例
  Completed，History 42，Prepare replay=0，批准 Action=1，拒绝=0，PASS。
- 第二次：Worker A=1faa7d769ca6，B=5173a62e155a；
  双容器相同实际 Image ID 前缀 sha256:cebc713ba43；
  两实例 Completed，History 42，Prepare replay=0，
  批准 Action=1，拒绝=0，PASS。
- 两轮完成后单独查询 DurableA34.dt.Instances：Completed=4、
  dt.History 累计 84 条；没有清理第一轮历史。
- 两次都证明 Worker B 在 Worker A 被杀之前已经运行，
  A 被杀后 B 无须重启即可继续同一原生 HITL。

## 未验收

- 全部容器位于同一 Docker 宿主机。没有测试跨物理节点、
  SQL Server 自身故障或 HA、网络分区、版本滚动升级。
- marker 只是本机测试观察器，不是外部 SideEffectReceipt
  或 Exactly Once 保证；没有真实外部写工具。
- 没有与 PostgreSQL Harness 的 Run/Step/Attempt/Execution
  任务级事实原子绑定；不得据此标记平台 Same Attempt Resume 为 PASS。
- 匿名测试 HTTP 只允许回环使用，未验证企业 IAM/Policy。
- MAF Functions Extension 当前为 beta，SQL Server Developer 仅测试许可。
  生产级支持、正式许可、性能、可用性与安全仍待独立评估。
- 未实现自定义 Scheduler、TaskHub 或 Lease。

参考：
https://github.com/microsoft/durabletask-mssql/blob/main/docs/scaling.md
https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-hubs
