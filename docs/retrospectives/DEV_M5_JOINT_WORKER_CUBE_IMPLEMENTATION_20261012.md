# DEV-M5-B03 · 同 Run Hatchet 物理 Worker 与 Cube 联合故障实施复盘（2026-10-12）

## 当前判定

**2026-10-12 最终增量：B.2 同 Run 真实联合验收 PASS；DEV-M5 整体继续 OPEN，Production NO-GO。** 前期因 WSL 生命周期和 Cube 服务不可用而记为 CODE_READY / LIVE BLOCKED，下文保留了这些历史排障证据；随后修复环境与真实 Hatchet 任务注册/Worker 日志缺陷，取得物理 Worker A SIGKILL→B 原生 Retry→原 Cube Guest、PG Fencing 和 Destroy ACK 的完整联合实测。不得以本 B03 子切片代替 OpenCode、完整 Guest Fencing 或 DEV-M5 阶段退出。

## 目标和边界

单个 Harness Run/Execution/Native Hatchet Workflow 中：A 真实 Worker 获准创建 Cube MicroVM 并写入 Guest 合成字节，实际 OS 进程组 SIGKILL（-9）；Hatchet Native Retry 由独立 B Worker 领取，Harness PG 在 Lease 到期后以事务 CAS 交接 Epoch 7→8；B 通过新 Native Cube SDK 连接**原 Sandbox ID**、读取原 Guest 字节；旧 Owner/错误 Scope 拒绝；最后真实 destroy ACK → RELEASED。保留全部 Run/Workflow/Execution/Provider/OS PID、Native Retry 与 Guest 证据。

## Red → Green 与回归

1. **Native SDK 参数遗漏已修复**：之前 NativeCubeTransport 仅检查 CUBE_TEMPLATE_ID，但创建时调用 Sandbox.create 仅携带 Metadata，真实 SDK 可能使用默认模板。新增无 PG 的单元测试首先 RED（1/2 FAIL），再冻结 Adapter 实例的模板并显式传入 template/timeout/metadata 后 **2/2 PASS**。原有真实 PG/Fake Cube Adapter 调用断言同步更新，PG 测试本轮尚未实测。
2. **联合证据验收合同**：新增纯断言校验同 Run、同 Workflow、不同 OS PID、真实 SIGKILL (-9)、B Native Retry、同 Sandbox ID、原 Guest 字节、Epoch 7→8、旧 Epoch 与 Scope 拒绝、Release ACK。新模块缺失先 RED，随后单元测试 **3/3 PASS**。该断言只保证证据格式及一致性，不能代替实机运行。
3. **真实代码入口**：新增 poc/sandbox/verify_hatchet_cube_worker_takeover.py，沿用 Hatchet SDK、PgFacts、CubeBinding、CubeWorkspaceGateway，不自建第二套 Scheduler；真实 A 在 Guest 文件写读校验后持久记确认事件，控制端才能杀 A，B 通过 Hatchet Retry 和 PG Fencing 取得原 Workspace。测试为加快故障注入会在确认杀死 A 后把 PG Lease 设为过期，这不是生产 TTL/Heartbeat 策略的验收。
4. **CI 编排**：更新 dev-m5-cube-live.yml，明确两独立 PG 数据库、官方 Cube/固定 Hatchet SDK、Strict OpenSpec、离线负例、真实 SDK Smoke、PG Cube Gate，以及本次真实物理 A→B + Cube 联合 Gate。没有 Cube Endpoint/Template 时必须失败，不能跳过后宣称通过。

## 本轮实测范围

- Native SDK 参数测试 Red 失败、Green 2/2 PASS；联合证据合同 Red 缺模块、Green 3/3 PASS。
- Milestone Regression 7/7 PASS；Python py_compile PASS；DEV-M5 OpenSpec Strict VALID。
- 显式运行联合脚本，因缺 CUBE_API_URL、CUBE_TEMPLATE_ID、HARNESS_POC_DATABASE_URL、HATCHET_POC_DATABASE_URL 返回 M5_JOINT_LIVE_GATE_NOT_RUN 和非零退出：**Fail-Closed 测试成功，但 Live Gate NOT_TESTED**。
- 当前默认 WSL Python 未装 cubesandbox/hatchet_sdk/psycopg，CubeAPI localhost:3000 健康接口无法连接（HTTP 000）。本轮没有清理或强行启动未知环境；没有产生本次真实 Run/Provider/Guest ID。
- PR Head CI、真实 PG + Cube + Hatchet 的联合链路 **尚无 PASS 证据**。

## 遗留风险、经验与后续门禁

修复的直接原因是原有 Fake Cube 测试没有覆盖真正 SDK Create 的模板参数；新增 SDK 参数合同保护真实创建选项。此前独立技术实验不代表组合功能可靠；现在强制**同 Run 的关联真实事实**以防误判。

后续在授权的 Linux、真实 READY Cube、两独立 PostgreSQL/Hatchet 数据库上运行联合 Gate，确认全部 Native/Guest/OS/Fencing/Destroy 证据，再进行 Head CI/架构 Guard/复盘。失败时维持 OPEN 或 UNKNOWN，禁止盲目新建第二 Sandbox 或 Host Shell 回退。

**尚未验证**生产 IAM、Guest in-flight Fencing、OpenCode Guest 全链、真实 OCI digest、跨宿主 HA、100 Active Runs。Inspector 暂不暴露未经认证的故障注入和 Cube 特权执行端点。

## 2026-10-12 后续推进：真实环境阻塞与新安全回归

在继续验证本次联合 Gate 时，确认已有 Ubuntu WSL CubeSandbox 一键部署目录与真实 Cubelet 服务存在，但此次启动后的 Cube API localhost:3000 没有监听（curl exit 7 / HTTP 000），CubeMaster / Cube API 未就绪。Cube 的 MySQL/Redis systemd 单元一度持续处于 start-post；Docker 记录 MySQL Exited (137)、Redis 正常退出，不能仅据 137 推断内存耗尽。cube-egress-net 的失败日志为 RTNETLINK answers: File exists，表明已有网络规则与启动脚本存在冲突待对账，**未擅自删除路由、重置 Docker 或修改安全隔离**。本机 WSL 内已有专用 Cube SDK 0.7.0 虚拟环境，但该环境当时缺 hatchet_sdk/psycopg；Windows 侧 SDK 单元测试不能替代 Linux 端到端运行。

继续采用 Red→Green 补上受信任 SDK connect 返回实例身份校验：旧实现虽以 PG 中的 Sandbox ID 调用 Native Connect，却没有核对原生 SDK 返回的 Sandbox ID，错误的 Provider 返回对象可能在有效 Owner Permit 下被读写。新增 tests/test_m5_cube_connect_identity.py 首次运行 3 个错误 Native ID 子例全部失败；修改 CubeWorkspaceGateway._attach 对返回的 Native ID 做精确比较，缺 ID / 错 ID 均在 Guest 数据调用之前 UnsafeDispatch，正确 ID 正例仍可读取，Green 2/2 PASS。对应 PG 合同增加恶意 Fake Transport 测例，须待真实 PG CI 执行后判定。

常规 dev-m5-cube-binding 工作流现明确执行 Immutable Template、Native Connect identity、Joint Evidence 三组纯单测及原有真实 PG/Fake Cube 合同；专用真实 Cube Workflow 也包含这些安全负例。**本次后续提交的最终 Head CI 仍需核验**，且不能把任何普通 PG/Fake Cube CI 成功视作真实 Cubes/Worker 联合 PASS。

其后发现资源释放同样缺少对 Native Connect 返回身份的最终核对，错误的 SDK 返回对象可能导致删除另一 Sandbox 并误将原 Sandbox 记录为已 RELEASED。新增 Destroy 负例首次 Red（2 个错误身份场景 FAIL）；Release 在 Kill 前核对原生实例 ID，不符合则保持 RELEASING 等待对账，正确实例才 Kill 并确认 ACK；Green 共 4/4，组合离线回归 16/16 PASS。Native 连接、Destroy 均不能把 Provider Locator 当作授权依据。

上一阶段 PR Head 2ae054e 的 Architecture Guards CI 38225131623 **SUCCESS** 与 DEV-M5 Real PG/Fake Cube CI 38225131595 **SUCCESS** 已核实；因此 B.1 模板与 SDK 参数合同子切片有可核查的远端结果。最新释放身份保护仍须在新 Head 单独复验。真实 Hatchet + Cube 联合 Gate 在 Cube API 不可访问情况下仍无可计入的 PASS 证据。

## 2026-10-12 实机环境专项续查与 Task Budget TDD

继续检测到 Docker 29 在 Ubuntu WSL 内反复处于 activating/restoring 状态，服务端请求偶发阻塞。旧版 Python docker-compose 1.29.2 的日志有 `compose/project.py` 事件监听 `KeyError: 'id'`，导致一键部署 MySQL/Redis 服务反复起停，CubeMaster/API 一直不可用。这是环境故障线索，不凭日志单独断言 Docker daemon 反复退出的唯一根因。MySQL **确实曾打印 ready for connections**，随后因服务停止收到正常的 shutdown；不得把这段 ready 日志当作长期健康运行。Cube MySQL 持久化使用 Docker volume /var/lib/mysql，本次未清除 volume、未改内网路由/防火墙规则、未删除 Sandbox。

经验证发行版 Ubuntu Noble 提供 docker-compose-v2 2.40.3，且现有 Cube `support-compose-lib.sh` 原生优先 `docker compose`，已在 WSL 以 apt 安装 2.40.3 并核验 `docker compose version`。此举不改 Cube 源码，旧版 Python Compose 保留用于诊断；MySQL/Redis 以原始 systemd Unit 非破坏性重启，但最后复查仍存在起停/activating，尚未证明 Cube API 健康。因此真实联合 Gate **NOT RUN / OPEN**。

另外发现 native Sandbox.create 使用 `timeout=300` 秒，而联合 Hatchet Task 原来仅 `execution_timeout=120` 秒，创建接近上限时必然被 Task Deadline 抢先中断。先写 `tests/test_m5_live_worker_time_budget.py` Red（缺共享 Time Budget），再显式定义 Cube Native Create 300 秒和 Hatchet Task 420 秒，CLI Live Gate watchdog 增至 780 秒、专用 workflow job 上限 30 分钟；Green 离线回归 **17/17 PASS**。这些代码和离线测试本身并不证明真实 Cube/Hatchet/PG 联合执行。

## 2026-10-12 根因最终追溯：WSL 实例生命周期与 Compose 兼容性

对齐系统日志时间轴后，确认主因不能写为「MySQL 自己 OOM 崩溃」：在部分故障窗口，`systemd-logind` 明确记录 `The system will power off now!`，随后 `shutdown.target` / `poweroff.target`、文件系统卸载、Docker 守护进程收到 **SIGTERM**，MySQL/Redis 因受控停止而退出；同一 Boot 内还观察到 Docker 正常 Stop/Start，MySQL 已 READY 后被停止。没有证据表明数据库卷需要重建。此前的 Docker Compose V1 1.29.2 发生 `KeyError: 'id'` 事件解析错误，与 Docker 29 不兼容，属于独立的放大因素；升级为发行版 Compose V2 2.40.3 后，单靠系统服务仍无法防止 Windows 结束空闲 WSL 实例。

**可复现修复**：在 Windows **Task Scheduler** 中创建独立、不带自动触发器的按需 WSL 前台进程，例如 `wsl.exe -d Ubuntu -u root -e sleep 43200`。Windows 定时任务本身必须为 `Running`，不能只从短暂的命令行启动并随父进程退出。新增 `scripts/dev_cube_wsl_keepalive.ps1`：`-Action Start` / `Status` / `Stop`，默认 12 小时，**仅开发实验按需运行，不建立自动登录启动任务**。实测保活持续期间 Ubuntu Boot 时间不变，Docker/MySQL/Redis/MinIO/CubeMaster/CubeAPI 均 ACTIVE/HEALTHY，HTTP `GET /health` 返回 200；未删除 MySQL volume、未清理未知 Docker 数据或修改宿主网络安全策略。保活有明确时间上限，测试结束后可停止；Windows 主机退出/睡眠、WSL 被其他进程强制关机等行为未在此切片验收。

## 2026-10-12 真实分层正例及同 Run 联合证据

1. **真实 Native SDK Smoke 再次 PASS**：新 MicroVM Sandbox ID `21935fd308c14f43803ee12c3f5ddd00`。官方 `cubesandbox==0.7.0` 实际 Create、Guest 文件写读、独立 SDK Connect 同原 ID 读取原字节、Kill 确认、进程退出码 0；结束时 Cube `sandboxes=0`。
2. **Harness PG + 真实 Cube PASS**：独立本地合成 PostgreSQL 16 测试容器（仅监听 `127.0.0.1:5432`、专用持久化 volume，未触碰 Cube MySQL）。`poc.sandbox.verify_cube_live` 真正运行并以 0 退出：Run `m5-cube-live-4a8d7bf5d1a7470b9de6e4d699ab65dc`，原 Sandbox `c51b673619e0404da77913dda4e7eaf4`，PG A/7→B/8、原 Guest 字节一致、旧 Owner 拒绝、Provider Destroy ACK→RELEASED。
3. **Hatchet Embedded 引擎正常**：原生引擎 v0.110.5 在独立的 `hatchet_poc` 数据库成功启动、执行实际数据库迁移；SDK `hatchet-sdk==1.42.1`。第一次联合启动遇到真实 `NameError: Context is not defined`（`from __future__ import annotations` + 局部 `Context` import 与 Hatchet `typing.get_type_hints` 不兼容）。新增 `tests/test_m5_hatchet_task_registration.py` 首先 Red 后 Green，按模块级作用域注册 SDK Context，但普通离线测试不必依赖安装 Hatchet。
4. **真实 Worker 诊断修复**：第二次联合运行原 Worker stdout/stderr 被重定向 `DEVNULL`，导致无法定位「没有 Cube Allocate」是任务未派发还是执行错误。新增 `tests/test_m5_worker_diagnostics.py` Red→Green，将独立 Worker stdout/stderr 留在唯一合成日志文件；当次阻塞 Synthetic Run 安全终止时 PG 为 ALLOCATING，未创建 Sandbox，未执行非幂等操作。随后再次运行才取得完整真实联合 PASS。
5. **同 Run 物理 Worker + 真 Cube 正式 PASS**：`poc.sandbox.verify_hatchet_cube_worker_takeover controller` 真正执行并以 **退出码 0** 返回 `PASS_PHYSICAL_HATCHET_CUBE_SAME_RUN`。Harness Run `m5-joint-c2e2deb3c5414190a61b03209c29fb81`；Execution `cube-exec-m5-joint-c2e2deb3c5414190a61b03209c29fb81`；Hatchet Native Workflow `b68e09ec-1a44-492e-9977-91572c7466f4`；A PID **28410**，OS SIGKILL exit **-9**；独立 B PID **29342**，Hatchet Native Retry **1**，B 日志有原 Workflow/Step 的重新分配和完成；A/B 原生 Cube Sandbox 均 `5934b961fd72494094e891a497ee1490`；PG Fencing **7→8**、错误 Scope 与旧 Epoch 拒绝、原 Guest 数据逐字一致、仅一次 Cube 创建、Destroy ACK `RELEASED`，Cube /health 最后 `sandboxes=0`。Controller 校验了 PG 真实事件数和全关联身份字段，无 Fake Cube / Host Shell 替代路径。

### 阶段退出范围和诚实边界

**B.1、B.2、M5 1.2 PASS**。仍 **OPEN**：B.3 Inspector 可信 Scenario Runner/Evidence API、M5 1.3 完整 OpenCode Shell/Files/Git Guest、任务恢复所有负例/故障窗口、in-flight Guest Fencing、跨宿主 HA、生产 IAM、100 Active Runs、M5 2.x 阶段 Exit Gate。B.2 中 PG Lease 超期由测试控制器在确认 A SIGKILL 后以服务器时钟下的 SQL 故障注入完成，**不代表自动生产心跳/TTL 门禁 PASS**。OpenSpec 不归档，M5 整体不升级为 CLOSED。
