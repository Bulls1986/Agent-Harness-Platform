# POC-A G2/G6 / Native Start ACK 不确定窗口（增量）

> 2026-10-09。**真实本机 TCP 连接断开 + 外部 SQLite 提交 + 平台 PG 对账隔离 3/3 PASS**。
> Native Server 是受控 HTTP Stub，**不是**官方 MSSQL MAF Durable；官方 Native+PG 受控窗口证据另见 A34_CROSS_DB_GAP_FINDINGS.md。

## 落地变更

- `NativeStartAckCoordinator.start_once` 先使用原 `DurableLaunchIntentStore.prepare` 在 PG 提交不可变 Native Launch Intent，才调用受信 Adapter 提供的一次 `native_start` 回调（可映射官方 /run）。
- 收到合法官方格式 32 hex Instance ID 后才写 `DurableRunningBindingStore.bind`；成功返回 BOUND。
- 任何 HTTP 断连、无合法 ACK 或绑定结果不明后，不猜测 Native 是否创建、不修改 TaskHub，直接通过真实 `quarantine_unbound` 平台领域逻辑将原 Attempt/Execution 标为 UNKNOWN，并写 PENDING Reconciliation。PG 隔离不能提交时直接失败，不返回虚构成功。
- 修复原 `DurableLaunchIntentStore.prepare` 在 Attempt UNKNOWN 后再次准备时，PG lineage trigger 早于 UniqueViolation 抛错、导致上层拿不到统一平台错误的问题：现在在 Run 锁内提前检查已有不可变 Intent，固定返回 `DurableBindingMismatch`，禁止调用第二次 /run。该保护仅提供 fail-closed，**不是**分布式 Exactly Once。

## 本机证据与边界

`test_native_start_ack_pg.py`：
1. 独立 HTTP 服务器向独立 SQLite 数据库真实提交 native start，然后**故意在任何 HTTP ACK 前直接关闭 TCP socket**；平台运行真实 PG `quarantine_unbound`（不是测试 SQL），对账后尝试第二次 start 在调用外部 HTTP 前被拒绝；外部 Native 记录总数仍为 1。
2. 有合法 ACK 的路径仅一次外部 POST，PG 正确绑定冻结身份/版本；重复 start 被拒绝。
3. 未返回合法 Native ID 会进入同一 UNKNOWN/PENDING 隔离，不创建第二 Attempt。

**3/3 PASS**，同一临时 PostgreSQL 另外执行 A34 Cross DB **8/8**、RecoveryPoint **4/4**、Tool Receipt **5/5**，均通过。测试后销毁隔离数据库。

**未验证：** 官方 MAF+MSSQL Worker 在真实 socket 半包条件下的同一轮实例状态观察；Native Instance ID 遗失后的生产安全定位、跨节点故障和企业 MCP 回执仍需独立验收。不能将本次 HTTP Stub 与历史官方 Native A34 实验拼接成同一完整故障链，G2/G6 仍 PARTIAL/GAP。
## 2026-10-09 / 官方 MAF Functions + MSSQL 真实 ACK 丢失验证（新增）

新增可复测 `test_official_native_ack_pg.py`，需显式设置 `POC_OFFICIAL_NATIVE_BASE_URL=http://127.0.0.1:17082` 和临时 `POC_POSTGRES_DSN`：**1/1 PASS**。

- 使用已启动的**官方 MAF Azure Functions MSSQL Durable Provider**，透过只在本机运行的 TCP Proxy 真实 POST 一次 `/run`；Proxy 已收到官方 InstanceId，但向平台下游**直接断开 socket 不传 ACK**。
- `NativeStartAckCoordinator` 真正走 PG `prepare → /run → quarantine_unbound`；平台原 Attempt/Execution UNKNOWN、Reconciliation PENDING、Native Binding=0；第二次启动在 Intent 处被拒绝，官方 /run 次数仍 **1**。
- 通过官方 GET /status 证实 Native Instance 存在且等待原生 HITL；结束时对该唯一随机测试 Instance 发送 **REJECTED** 并确认输出 DENIED_NO_EXECUTION，避免遗留不安全测试实例。
- 没有直接 SQL 篡改 TaskHub 或代替平台 Adapter 事务。本测试真实 Backend 但故障点是**受控代理下游 ACK**，不等于官方 Worker 自身 SIGKILL/网络半包损坏、跨节点 HA、未知 ID 的全局可信发现，也不等于企业 Tool Receipt Exactly Once。

