# POC-A / A34 — 真实不兼容应用镜像接管负例

> 日期：2026-10-08。单机 Docker、官方 MAF Durable Azure Functions、
> MSSQL Provider、真正两套**不同应用镜像 SHA**、真实 PostgreSQL
> 不可变 RUNNING Native Instance / Version Binding、受控 HTTP Tool Sink。
> 测试**工作流实现版本不兼容**，未更换 MAF SDK/Durable Provider 二进制。

## 要验证的判定

如果平台 V1 Attempt 已冻结 `maf_mssql_poc_guarded:v1`，
只部署 V2 不兼容的应用代码来接管旧 Native Instance，原生 Durable
是否还会调用 V2 的 Handler？Harness 会不会放行危险工具派发？

**预期：不能信赖 Native Provider 自动隔离旧应用代码。**
Harness 受控 Tool Adapter 读取数据库冻结版本，比较可信 Worker
的实际执行版本，不一致即拒绝派发；允许任务安全失败，但绝不能让
V2 随意在旧 Execution 上产生 SideEffect。

## 实测运行与环境隔离

- 为本实验新建 SQL Server DB `DurableA34Version` + 原生
  TaskHub `MafMssqlVersion`。不碰已有 Native TaskHub 历史、
  不清理 PostgreSQL 测试事实。
- Worker A：`maf-mssql-a34-version-v1:cached`，镜像 SHA
  `sha256:8a76cc214a6731be75a8b79be0dea1b9dac0d34a056e103a6984f098de4afefa`。
- Worker B：`maf-mssql-a34-version-v2:cached`，镜像 SHA
  `sha256:0e43d53a2ebbed97186e35c0abb95ede44d63d7e2f577e9885aba07097f3afec`。
  V2 **实际镜像文件内容变化**：版本常量为
  `maf_mssql_poc_guarded:v2-incompatible`，成功输出行为也更改。
  两镜像共享完全相同的固定 MAF SDK，非 SDK 二进制升级。
- V1 Native Instance：
  `57d934a2c6954edebf87f85534d3dcd6`。
  创建后在 PostgreSQL 固化完整 Run/Step/Attempt/Execution
  + Native Instance + Workflow Version V1 / Runtime Version。
- 旧 Worker A `Prepare` 处于真实原生 RUNNING 时、
  新 Worker B 已在线，SIGKILL A。B 不重启也不重新提交 /run。
- B 拿到旧任务进入 V2 的 `GuardedRunningExecutionProbe.run_guarded`；
  V2 在工具入口送出 `X-POC-Worker-Workflow-Version:
  maf_mssql_poc_guarded:v2-incompatible`。Harness 测试 Gateway
  从 PostgreSQL 不可变 Binding **重新读取** V1 冻结版本；
  不匹配返回 HTTP **412**，Executor 抛出
  `HARNESS_INCOMPATIBLE_WORKER_VERSION`，并未执行 Tool Sink。

## 真实结果

| 事实 | 结果 |
|---|---|
| 原生两套应用镜像 SHA 不同 | PASS |
| Worker B 实际进入旧 Instance 上的不兼容 Handler | 1 次 |
| 受控 Gateway 判定序列 | `version_denied` |
| 外部 Tool Sink 写入次数 | **0** |
| Native MSSQL `dt.Instances` | **Failed** |
| Native MSSQL History（本 Instance） | 12 行 |
| PostgreSQL Native Binding | 仍冻结 V1 |
| PostgreSQL Attempt 数 | 1 个 |
| PostgreSQL Run / Attempt | **FAILED / FAILED** |
| Execution Owner fencing token | 2 |
| A / B | `d0cb5c910aa0` / `823c5c200971`，B 未重启 |

脚本结果 `PASS_ACTUAL_APP_VERSION_REJECTED`，
运行路径 `poc/maf/functions-mssql/verify_incompatible_worker.py`。

**判定：P0 工作流实现版本不兼容负例本机 PASS（Harness Tool Admission fail closed）**。
这不是原生 Durable TaskHub 自带安全版本隔离。相反，B 的不同代码
**已经运行到 Handler**；安全边界在实际 Tool 调用前的 Harness。

## 范围与安全约束

- 冻结版本头在此单机 POC 中来自 Worker 应用代码常量；**它是
  Worker 自我声明的元数据，不是经可信部署控制器证明的镜像
  摘要或可信启动证明**。生产中必须依赖受信 Worker 身份/
  Artifact Digest / Runtime Routing 绑定，而非允许调用方自行伪造
  版本头。因此不能把这次测试描述成抵御恶意 Worker 的安全验证。
- 本实验针对**不兼容的应用 Workflow 实现版本**；没有安装不同
  SDK 版本来测试 Durable 层兼容性。后者作为生产升级测试范围，
  不在本轮平台 POC 继续扩张。
- Test Driver 注入 `Run/Attempt/Execution=FAILED` 并撤销
  Owner/Fencing 是受控 SQL 实验收尾，**不是生产自动分类引擎的证明**。
- 即使 Handler 已进入，未通过 Harness Tool Admission 的路径仍
  不应产生外部副作用。所有危险工具出口必须通过受控 Adapter。
- 此验证没有执行真实企业 MCP、跨物理节点 HA、生产许可证、
  自动回滚部署和不兼容数据结构迁移。

## 本机复现

前提：已有本地缓存镜像
`maf-mssql-a34-running:cached`、既有 PostgreSQL/MSSQL/Azurite
容器、被 gitignore 排除的 `.env.local`。

```powershell
python poc/maf/functions-mssql/init_mssql_db.py DurableA34Version
docker build --pull=false -t maf-mssql-a34-version-v1:cached -f poc/maf/functions-mssql/Dockerfile.a34-version-v1 poc/maf/functions-mssql
docker build --pull=false -t maf-mssql-a34-version-v2:cached -f poc/maf/functions-mssql/Dockerfile.a34-version-v2 poc/maf/functions-mssql
python poc/maf/functions-mssql/verify_incompatible_worker.py
```

隔离 Compose 文件：
`poc/maf/compose-functions-mssql-a34-version.yml`。
本地 HTTP Gateway 仅作受控故障注入，进程退出即关闭。
