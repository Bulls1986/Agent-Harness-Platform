# POC-A34 双数据库同一任务级等待恢复：真实端到端验证

> 2026-10-08。**本地单 Docker 主机整链子目标 PASS**，
> 不是 A34 RUNNING Attempt Same Attempt Resume，也不是生产 G6/G8 PASS。

## 部署与状态所有权

此测试**不是**将两个独立测试的结果拼起来，而是在同一个故障注入
脚本中真实使用两个持久化系统：

- Harness PostgreSQL（127.0.0.1:54329）：Conversation/Turn/Run/Plan/
  Step/Attempt、Approval、原生 Durable Instance/Request 不可变绑定、
  Frozen Workflow/Runtime Version 和不可变事件。
- MSSQL SQL Server（原有 maf-mssql-poc-mssql-1 容器）：
  DurableA34 数据库的 Durable Functions TaskHub、History、
  Native HITL 状态及 Worker 竞争消费。
- Azure Functions Worker A / B：完全相同的应用镜像，
  两个副本在故障前同时在线；B 启动时能查到 A 的 Native Request。
- Azurite：仅供 Functions Host Storage，**不是** Workflow Durable History。
- 本机独立对象：maf-a34-postgres 容器及专用 maf-a34-pgdata 数据卷。
  不删除已存在的 DurableDB / DurableA34 / 原平台业务数据库。

## 一次完整故障链路

1. 使用已有 SQL Server / Azurite 与本地双 Worker Compose
   maf-mssql-a34，独立 PostgreSQL 运行 TaskLedger 的 001～007 迁移。
2. A 启动两个真实 MAF Durable Workflow 直到原生 request_info；
   每个原生 Instance/Request 在**平台一个 PostgreSQL 事务**中与
   Approval + Run/Plan/Step/Attempt + 冻结版本建立唯一不可变绑定。
3. B 在 A 未退出时加入同一个 MSSQL DurableA34 TaskHub，成功
   查询两个实例原始 Request ID。此时在平台测试中故意传入
   不兼容 Workflow Version，require_waiting_resume **拒绝**，并未向
   Native Runtime 投递错误响应。再以冻结版本验证同一原生身份通过。
4. 对 A SIGKILL；B 容器无需重启，SQL Server / Azurite 亦不重启；
   通过 B 再次查询同一 Instance/Request，同时校验 PostgreSQL
   Approval 仍 PENDING、Run WAITING_APPROVAL、Attempt CREATED，
   同一 Run 下只有 1 条 Attempt。
5. 在可信本地 fixture 身份下由平台决定 APPROVED/REJECTED，
   然后由 B 通过官方 Native HTTP Response 接口继续原生流程。
   两实例均 Completed。已完成 Prepare 不重复执行；
   批准模拟动作 1 次，拒绝动作 0 次。
6. 通过**独立 PostgreSQL 查询**确认两个平台 Run 各只有一个
   Attempt、审批分别 APPROVED/REJECTED，并使用原先的 Native
   Instance/Request 和 Frozen Workflow Version；通过**独立 MSSQL**
   查询确认新 Native Workflow 及 History 已落到 DurableA34。

## 真实验收输出

- 双 Worker 镜像一致：sha256:cebc713ba43（前缀）
- Worker A：0c6d5fb1a09d；Worker B：ad8f17e2f97d
- platform_approval_attempt_binding = PASS-WAITING-IDENTITY
- workflow_frozen_version_negative_guard = true
- platform_inflight_same_attempt_resume = NOT_PROVEN
- Native MSSQL 两个新实例：Completed = 2，History = 42
- Prepare replay = 0；approved action = 1；rejected action = 0
- 独立 PostgreSQL 查询：2 个不同 Run，各只存在 **1 个 CREATED
  Attempt**；Approval 分别 APPROVED 和 REJECTED；
  Run 状态对应 RUNNING 和 FAILED
- 独立 MSSQL 全量历史查询：DurableA34 累积 **8 个 Completed
  实例、168 条 History**，包含之前测试记录，未清库

真实 PostgreSQL 约束/负例另有本地 6/6 PASS 与
[GitHub Actions #37738700282](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37738700282)；
CI 不启动 MSSQL/Functions，因此双数据库故障实测来自本地 WebCodex Docker。

## 重现入口

确保现有 MSSQL Functions Docker POC 可运行，使用独立
PostgreSQL 16（可复用基线 poc/maf/compose.yml 的 postgres 服务，
只需选择独立 Compose Project/volume，避免端口冲突），并将
POC_POSTGRES_DSN 由可信本地环境提供。任何密码均不要提交 Git。

在 PowerShell 中的示例仅适用于此次已创建的随机本机凭据：

    $cred = Join-Path $env:TEMP 'maf-a34-pg-pass.txt'
    $pw = [IO.File]::ReadAllText($cred)
    $env:POC_POSTGRES_DSN = 'postgresql://poc:' + [uri]::EscapeDataString($pw) + '@127.0.0.1:54329/poc_harness'
    python -m unittest discover -s poc/maf/tests -p test_durable_approval_binding_pg.py -v
    python poc/maf/functions-mssql/verify_concurrent_handoff.py
    Remove-Item Env:POC_POSTGRES_DSN

验证脚本会自行使用新随机 fixture ID，旧 TaskHub History 保留。
只有收到 platform_approval_attempt_binding=PASS-WAITING-IDENTITY，
才证明**这一次**两数据库整链经过了验证；
NOT_RUN 表示只跑了原生 MSSQL Worker 故障测试。

## 边界：不能从上述 PASS 推断的能力

- Platform Attempt 仍是 CREATED 的**审批等待态**。这次并没有
  让外部 Execution 在 RUNNING 时崩溃，因此无法声称
  Same Run + Same Step + Same Attempt 的真正执行中 Resume。
- 平台 APPROVED 后 Run 仍是 RUNNING，因为其最终完成需要可信
  Execution Receipt / 独立 Verification；Native Completed 不自动
  等价于 Harness Run COMPLETED。REJECTED 后 Run 是 FAILED，
  未向敏感模拟 Executor 发出 Dispatch。
- 两数据库**没有跨库分布式事务**。原生 Native Request 已创建
  而 PostgreSQL Binding 尚未提交的崩溃窗口，以及平台审批已落库
  而 Native Response 尚未送达/送达未知的窗口，在这条 SQL Server
  生产候选路径上仍需独立故障/对账验证。
- 不兼容版本**仅在平台 Adapter 冻结版本检查被拒绝**；没有运行
  真正不同 MAF Workflow 代码镜像进行原生 replay/migration。
  官方 Durable Functions Orchestration Versioning 支持
  defaultVersion、versionMatchStrategy，但固定 Python MAF
  AzureFunctions beta 的集成/升级仍需实测。
- 没有企业 IAM、真实外部 SideEffectReceipt、跨物理节点 HA、
  Workspace/OSS 恢复、正式 SQL Server 许可或预发布 SDK 支持保证。

**结论**：A34 等待态身份与冻结版本子目标完成；A34 整体、G6/G8
仍为 OPEN，平台不得自行实现 Durable TaskHub。

## 2026-10-08 追加独立复验（原始历史不清理）

在 PR #15 已合并的代码基础上，本轮重新运行 6 项 PostgreSQL 真实 DB 单测，
**6/6 PASS**；再执行整条 MSSQL+PostgreSQL 双 Worker SIGKILL 链路，
输出为 platform_approval_attempt_binding=PASS-WAITING-IDENTITY、
workflow_frozen_version_negative_guard=true、
platform_inflight_same_attempt_resume=NOT_PROVEN。两 Worker 均使用同一镜像，
A=0ff90b3f5629、B=66aa7ba93f94；原生 Completed=2 / History=42，
Prepare replay=0、批准 Action=1、拒绝 Action=0。

随后的两库**独立只读查询**验证：PostgreSQL 最近两个不同 Run
状态分别为 APPROVED→RUNNING、REJECTED→FAILED，均只有一个 Attempt，
冻结版本均 maf_mssql_poc_hitl:v1；MSSQL 查询这两个精确 Native Instance，
两条均 Completed、对应 History 42。没有清库，原始错误历史保留。

同样只证明审批等待态身份连续性；不代表 RUNNING Execution 原生续跑、
真实 Workflow 镜像升级/迁移、跨库原子提交或生产 HA。

## 2026-10-08 增量：审批决定后原生 Response 投递窗口

在前述相同的本机 PostgreSQL + MSSQL、在线双 Worker SIGKILL 链路中，
新增平台投递门禁 `durable_approval_delivery.py`：平台 Approval 决定
在 PostgreSQL 事务中提交后，重新创建 Adapter/连接，再按 Run/Attempt、
原生 Instance/Request、冻结 Workflow/Runtime Version 原子领取一次投递令牌。
只有 `CLAIMED` 才允许调用官方 Native Response API；原生状态查询确认
Completed 且输出与平台决策匹配后，才把投递记录标记 APPLIED。
相同决策的再次 claim 返回 ALREADY_APPLIED，不产生再次响应。

**实跑证据：** 4/4 新 PostgreSQL 合约测试 PASS；完整双数据库故障链
`committed_decision_before_native_delivery=PASS`、
`native_response_delivery_token=APPLIED`、`mssql_completed=2`、
`mssql_history_rows=42`、`prepare_replayed=0`、批准 Action=1、拒绝 Action=0。
Worker A=5a39b119aa5d、B=b4d643af84e7，B 在 A SIGKILL 后没有重启。
原始 TaskHub History 不清除。

**严格边界：** 投递令牌已经持久化、但 Native HTTP 响应结果未知时，
新 Worker claim 会原子将其标成 UNKNOWN_REQUIRES_RECONCILIATION，
不能 blind retry；该分支目前只由真实 PostgreSQL 负例证明，
**没有**在 MSSQL Native API 请求中间真实 kill Worker、也没有完成
后续 Reconciliation/Receipt。审批已提交但尚未领取令牌的安全窗口，
本轮是两个独立数据库连接/Adapter 的断点检验，并非进程强杀注入。
Native Request 已存在但平台 Binding 尚未提交的窗口只验证了平台
fail-closed，未完成自动发现/对账。上述测试不是跨库分布式事务，
也不是 RUNNING Execution 中途 Same Attempt Resume 或 G6/G8 PASS。
