# POC-C / C06+C07：真实 Temporal Activity 重试与 Harness PostgreSQL 防重故障链

> 2026-10-08 | **本地 OSS Temporal + 双 PostgreSQL + 真实 Worker 进程故障 PASS**
>
> 本任务只验证 **平台任务级事实的归属与非幂等工具的 fail-closed**
> 决策，不证明整个 Agent Harness G2/G6 或生产 Exactly Once。

## 结构与核心责任

- **Native Temporal OSS Server 1.31.0** + 自有 PostgreSQL 16，
  保留官方 Temporal Workflow/Activity Retry/History。
- **第二个独立 PostgreSQL 16**：`poc-c-harness-pg`，
  数据库 `harness_poc`，由 Harness 持久记录
  Run/Step/Attempt/Execution、Native Workflow Binding、Owner
  Fencing、Event、UNKNOWN Reconciliation。
- 复用 POC-A 的**平台 Task Facts 基础 SQL 和 ExecutionOwnership**，
  不引入 Temporal 私有租约/新 Scheduler。
- 新 `poc_c_temporal_bindings` 固定
  Execution/Run/Step/Attempt ↔ Native Workflow ID + Workflow/Runtime
  Version；SQL INSERT 检查合法血缘和 RUNNING/NON_RETRYABLE，
  UPDATE/DELETE 被数据库触发器拒绝。新 Worker 在 Tool Admission
  前重新读取冻结版本、平台当前 Plan 和 Attempt 身份。
- **Temporal Workflow** 只调度字符串名称的 Activity；
  **Activity** 才导入 psycopg、HTTP/Tool Adapter/文件。初次联调
  发现 Sandbox 禁止在 Workflow 初始化时导入文件 I/O 模块，
  已按确定性约束拆分，而不是绕过 Sandbox。

## 两种重试的真正区别

1. **PURE 基础设施错误**：Activity 故意在第 1 次执行抛出
   `TRANSIENT_INFRA`，Temporal 官方 RetryPolicy 第 2 次成功。
   这仅是同一 Native Activity 意图的基础设施重试，
   **不是业务 Replan，不应新建平台 Attempt**。
2. **NON_RETRYABLE 外部派发**：
   - Worker A 在真正的 PG Owner/Fencing/Dispatch Claim 成功后，
     向受控 HTTP Tool Sink 发出一次 POST；Sink 实际收到并返回 200。
   - Worker A 在**收到 HTTP 应答后、Native Activity 结果 ACK 前**
     调用 `os._exit(74)`，相当于进程级强制退出；
     Temporal Activity 完成状态无法确认。
   - Temporal OSS 根据 `start_to_close_timeout` 自动执行
     第 2 次 Activity 尝试，由 Worker B 接管。
   - B 发现**同一个 Execution 的既有所有权/派发事实**，无法申请
     新派发。待原 Owner TTL 到期后，受控平台恢复入口原子地将
     Attempt/Execution 置 `UNKNOWN`、撤销旧 Owner 并将 Fencing
     Token 从 1 增至 2，创建 `PENDING Reconciliation`。
   - Tool Sink 最终**仅收到 1 次**请求；没有新建 Attempt，
     也没有重新调用外部工具。

**本地实测第二轮（加入 PURE 对照后）：**

| 指标 | 实际 |
|---|---|
| Native Temporal Backend | 真 OSS 1.31.0 / PostgreSQL |
| Harness Task Facts | 第二个 PostgreSQL，原生 UUID 风格平台 ID |
| PURE Activity 进入次数 | 第 2 次重试后成功 |
| NON_RETRYABLE Activity | 第 2 次重试被 Harness 拒绝再次派发 |
| Worker A 真实退出码 | **74**（HTTP 200 后） |
| Tool HTTP Sink Receipt | **1** |
| Native History | **17 个事件**，**2 个 Activity Completion** |
| 平台 Run | RUNNING（未错误标成业务成功） |
| 平台 Attempt / Execution | **UNKNOWN / UNKNOWN** |
| 平台 Reconciliation | **PENDING** |
| Execution Owner Fencing Token | **2** |
| Frozen Binding 和原 Attempt | 原 ID 保持；未重建或更新 |
| Harness Typed Events | **2 条**：`run.started`、`execution.unknown`，包含 Execution/Attempt 标识 |
| `test_platform_binding_pg.py` | **4 项**真实 PG 负例通过 |

`native_history_events` 是单 Native Workflow 的历史计数；
并非外部工具业务收据或平台事件总数。Temporal 本次 Native
Workflow 返回分类结果 `UNKNOWN`，这是平台需要继续对账的事实，
**不是外部执行已成功**。

## 不能夸大的边界

- HTTP Sink 是测试受控的合成 Receipt；没有真实企业 MCP
  工具回执/签名信任、业务状态反查或自动 Reconciliation Resolve。
  即使本轮只有一次真实 POST，也不构成跨系统 exactly-once 保证。
- PG 原子门禁隔离了外部 Tool Admission，但 **PostgreSQL + Temporal
  启动事务不能原子提交**。初次 Native Start ACK 结果不明、平台
  Binding 预写后 Native 未提交等断点仍需后续专门验收。
- 本 POC 的版本校验仅校验可信配置传入的冻结字符串，
  **不能当作恶意 Worker 镜像身份鉴别**。
- Activity 已派发但 Owner 仍未过期时，不允许过早改 UNKNOWN。
  真相不明时宁愿保留未决状态，也不执行第二次危险动作。
- 平台 Run 仍可为 RUNNING，执行 Attempt/Execution 是 UNKNOWN；
  最终终态需受信外部 Receipt 对账后另行推进。
- 不把多租户治理、OSS 数据备份、Temporal History 自建迁移、
  沙箱内核或企业 IAM/MCP Governance 重新纳入 Harness 范围。

## 运行与 CI

```powershell
# 先按 C05 运行真 Temporal OSS/PostgreSQL；
# 再单独启动 Harness PostgreSQL，使用**两套独立 POC 数据库**：
$env:POC_C_HARNESS_PG_PASSWORD = '<random-local-poc-only-password>'
docker compose -p poc-c-harness-pg -f poc/temporal/compose-platform-pg.yml up -d

# 指向第二个 PostgreSQL 的 DSN 放到可信的本地进程环境中：
$env:POC_C_PLATFORM_DSN = 'postgresql://harness:<password>@127.0.0.1:17236/harness_poc'
$env:POC_C_TEMPORAL_ADDRESS = '127.0.0.1:17234'
python -m unittest discover -s poc/temporal/tests -p "test_*.py" -v
python poc/temporal/verify_c06_c07.py
```

CI 使用每次随机生成的两个独立 PG 密码，不存代码仓库；
运行官方 Temporal OSS+PG、真实 PG 负例和 Worker 崩溃链。
**只有 CI 真实通过后，C06/C07 才可标记为正式 scoped PASS。**

下一步是 C10 Responses/Typed Event Bridge、C12 Workflow Versioning
或 C09 实际可替换 Agent Runtime 的受控对照；本轮不会继续
扩展 Temporal 的 Native Scheduler。
