# POC-C / C00–C04：Temporal Native Workflow 首批实证

> 2026-10-08 | **局部 PASS；POC-C 整体 OPEN**
>
> 正式编号是 C，不能因实施顺序第二而改为 B。
> 本页是本地真实官方 SDK + Development Temporal Server 的
> 实验记录，不是生产自托管 Temporal Backend 验证。

## 运行范围

| 层 | 实际对象 |
|---|---|
| Temporal SDK | Python `temporalio==1.34.0`（公开 Client/Worker/Workflow/Activity/Signal/Query/History API） |
| Native Server | Docker `temporalio/temporal` 固定 digest；内置 **Server 1.32.0 start-dev** |
| Persistence | Docker Named Volume `poc-c-temporal-dev-data` + SQLite `/data/temporal.db` |
| Ports | 仅 loopback `127.0.0.1:17233` gRPC；`127.0.0.1:18233` UI |
| Agent Adapters | 两个本地受控 fixture A/B，**不是真实模型/远端 Runtime** |
| Independent Verifier | 共用 POC-A `poc/maf/verify_fixture.py`，Document 好坏正反例 |
| Platform Task IDs | 外部生成 Run/Attempt；Native Workflow ID 为独立 opaque binding |

## 实验一：真实 Workflow Worker SIGKILL

`python poc/temporal/verify_local_handoff.py`

1. Worker A 独立 OS 进程执行 `DocumentReviewWorkflow`，
   调度 Agent-A 和独立 Verifier Activity；
   `buggy` Fixture 被拒绝，Workflow 进入 `WAITING_APPROVAL`。
2. **OS 强杀** A；新进程 Worker B 处理**同一个**
   Temporal Workflow ID 和 Task Queue，没有再次 `start_workflow`。
3. 从公开 Query 重新读取等待状态，发送一次 Signal `APPROVED`，
   原生 Workflow 切到 Plan v2，执行 Agent-B + 独立 Verifier，
   正确完成，并保持外部生成的 Run/Attempt ID。
4. 另一条完全独立 Workflow，Signal `REJECTED` 后 FAIL，
   没有进入 Plan v2 或调用 Agent-B。
5. 历史来自公开 `fetch_history_events()`：**33 条原生 History Event**、
   **4 次完成 Activity**；两 Plan/Attempt（平台业务含义）保持不变。

**判定：PASS — Native workflow durable wait + Worker failover**。
这不是工具 exactly-once，不是实测实际 Agent Runtime Swap，
也没有独立 PostgreSQL Task Facts 与 Platform Event Gateway。

## 实验二：真实 Temporal Server 容器停止/启动

`python poc/temporal/verify_server_restart.py`

1. 新 Native Workflow 经 Worker A 运行至第一次 Verify 失败后等待审批。
2. **强杀 Worker A，停止实际 Temporal Server 容器**，
   核对 `State.Running=false`；保留独立 SQLite Volume。
3. 在**同一数据卷**启动 Temporal Server，使用全新 Client/Worker B
   Query 读取同一 Native Workflow；发送 Signal 完成 Plan v2。
4. SDK 公开 History 再次记录 **33 个 Event、4 个完成 Activity**；
   Platform Run/Attempt IDs 不变，且无再次启动原生 Instance。

**判定：PASS — dev-server SQLite 持久化下进程/服务重启恢复**。

### 首次环境问题

固定镜像默认以非 root `temporal` 用户运行，新 Docker
Volume 原始所有权不允许 SQLite 写入；曾报告
`unable to open database file (14)`。通过**一次性** root
init 容器 `chown temporal:temporal /data` 修复后，
日常服务继续以非 root 用户运行。未修改镜像权限或关闭隔离。

## 关于 PASS 的严格边界

- **start-dev 会跳过部分 HTTP 安全校验**，不适合生产；
  不能将本机 SQLite Volume 测试表述成生产部署 G1/G6。
- Temporal Server 停止/重启**不是存储基础设施 Backup/DR**；
  是对官方 Workflow History 持久化/恢复功能的有限验证。
- Temporal 的 Activity at-least-once 与 SideEffectReceipt 的
  exactly-once 不相等；NON_RETRYABLE 仍需平台 UNKNOWN/对账。
- Temporal Workflow 存的是原生确定性调度状态和 Native History；
  **平台 Run/Step/Attempt/Execution / Approval / Artifact**
  没有因此自动写入 PostgreSQL。POC-C G2 仍 OPEN。
- 不执行 Shell/Sandbox/Git Push/真实 MCP，也不执行真实模型。
- 不把 Tenant/IAM/MCP Governance/Secrets/备份纳入 Harness 内核。

## 下一步

按 `docs/POC_C_TASK_PLAN.md` 进入 C05 非 dev-server
Temporal OSS+PostgreSQL 持久后端，再处理 C06/C07
副作用与平台事实门禁。**不能在 C05 通过前标生产 G1 PASS。**
