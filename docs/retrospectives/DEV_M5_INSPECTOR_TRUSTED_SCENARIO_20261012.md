# DEV-M5 B.3a · Inspector 受控场景执行与独立证据接口（2026-10-12）

## 判定

**受控执行 API / 页面合同 PASS；真实 Inspector HTTP → Hatchet/PG/Cube 端到端 Gate B.3b 已 PASS。DEV-M5 整体仍 ACTIVE / Production NO-GO。**

在已有 B03 原生物理故障联合验收 PASS 的基础上，完成一个最小操作员授权的 Worker Takeover 场景运行入口。与之前仅可读的能力目录及 Harness PG 观察证据保持分离，避免将旧 Run 或假 PG Event 误判为当前真实执行。

## 本次实现

1. 原有 Inspector 默认只读，且该默认不因同一进程内另一受控实例启用而被修改；服务端必须明确设置开关、强随机操作员 Token 和独立证据目录才允许 B03。
2. 只有 worker-takeover 可触发固定后端 Verifier 模块。不接受客户端脚本、Shell 命令、执行参数或沙箱 locator；HTTP 无认证/错误认证/跨来源拒绝，服务端 localhost 实验边界保持不变。Cube-only 与非幂等 Receipt 场景仍是只读。
3. POST 仅返回未验证的独立执行 ID；GET 证据需同一 Operator 凭证。可信执行线程校验原生 B03 的 Run/Workflow ID、真实 Worker A/B PID、SIGKILL -9、Native Retry、同 Sandbox、PG Epoch、Guest 文件字节一致、旧 Owner/Scope 拒绝和 Destroy ACK。脱敏字段写入运行器私有目录，不持久化密钥、Guest 实际内容或原始 SDK/进程日志。
4. 一次只允许一个真实受控任务，跨服务进程用独占锁文件防重复执行；完成证据以临时文件 + fsync + 原子替换落盘。异常、错误证据、服务重启时无法确认的在途执行一律 BLOCKED_UNKNOWN 且不能无对账直接重试。服务端实际命令固定、无 shell，独立进程组超时时清理，避免遗留实验 Worker。
5. 保留两个 Tab；有服务端可信能力时 Worker 卡片才提供授权操作入口。临时凭证仅留在本页密码控件，页面不使用 localStorage/URL 存储，也不嵌入任何服务端 Key；UI 用 textContent 呈现受控状态与白名单结果。

## Red → Green 与证据

先增加 tests/test_trusted_scenario_runner.py，此时缺实现模块产生预期 RED；补齐可信执行器、HTTP API 与 UI 后，默认拒绝、错误凭证、Origin 拒绝、单活、错误 Native 证明不得 PASS、重启证据读回、默认目录隔离等测试 GREEN。受控本地合成回归 **6/6 PASS**；设计、OpenSpec 及架构 Guard 独立校验。真实 B03 既有 CLI 测试 PASS 记录位于 docs/retrospectives/DEV_M5_JOINT_WORKER_CUBE_IMPLEMENTATION_20261012.md，并**不能**替代本次新 HTTP 入口的实机执行。

原 B.3a 合同阶段的后续门禁是由新 Inspector API 发起真实 POST → B03 → GET（重启后）的独立实机验证，而非复用历史 CLI 运行；**该门禁现已在本次 B.3b 增量通过，详细证据见下方**。新 PR Head CI 与其他场景/生产门禁仍须分别复验。

## 边界与复盘

### 2026-10-12 B.3b 实机闭环新增证据

在恢复的受控 Linux/WSL CubeSandbox 环境，直接通过 FastAPI TestClient 的真实 Inspector ASGI POST 接口触发固定 B03 Native Verifier；Verifier 调用独立 Hatchet Worker A/B、PostgreSQL 及真实 Cube MicroVM。执行结束之后重新创建 Inspector 实例，再经授权的 GET API 读取已持久化的原生证据。**这不是历史 B03 CLI 结果或 Mock Callback。**

**实机判定：PASS_REAL_INSPECTOR_TRUSTED_B03_API，验证进程 exit 0。**

| 证据字段 | 实机结果 |
| --- | --- |
| Evidence ID | proof-c7b82a4c3c6d4a4d963e5aee8fbf52e5 |
| Run ID | m5-joint-8b90c55281864cfe8f055cb1de6fbb8d |
| Hatchet Workflow | 2a4c51a8-8ade-43cb-b6f9-41a9958babbf |
| 原生 Cube Sandbox | 73d702e69a374e778bcae3ed79d1625a |
| Worker A PID、OS 退出码 | 226263、-9（SIGKILL） |
| Worker B PID、Native Retry | 227114、1 |
| Guest 连续性 | 原 Guest 字节相同，符合 B03 严格证据合同 |
| PG Fencing、Release | worker-B / Epoch 8 / RELEASED |
| 授权 | 匿名及错误凭证均被拒绝 |
| 运行证据 | 重建 Inspector 后按 Evidence ID GET 仍 PASS |

之后另行直接查询 PostgreSQL 的 harness_cube_binding，检查同一个 Run 的原 Sandbox ID、Owner、Epoch 和终态为 RELEASED；Cube API 健康检查 HTTP 200，剩余 Sandbox 数为 0。因此 **B.3b 的受控 Worker Takeover 场景可据实勾选完成**。

限制：E2E 是在真正的 ASGI HTTP 路由上运行，使用 TestClient 而不是用户手工点击浏览器，也不是生产认证/容器长期运行验收；Cube-only、非幂等 Tool Receipt 的独立演示执行、OpenCode 完整 Guest/in-flight fencing 和整个 DEV-M5 安全容量门禁仍 OPEN。新远端 PR Head CI 需复验。

### B.3b 事后超时预算复盘与 CI 复现门禁

实机成功后检查发现可信 Native Verifier 等待上限为 780 秒，但 Inspector E2E Runner 仅等待 250 秒。真实 Cube MicroVM Create 单独允许约 300 秒，慢启动可使 E2E 提前停止查询与销毁临时证据目录，造成错误失败和不确定状态。

新增 tests/test_m5_inspector_live_budget.py 先 Red（缺少共享预算），再把后端 Native Timeout 固定为 780 秒、API E2E 证据等待扩展到 840 秒，并由合同测试保证差额至少 30 秒；本地 Green，针对性合同回归 17/17 PASS。专用 dev-m5-cube-live.yml 的真实环境 Gate 在原 B03 实机检查之后再跑 Inspector 新 API-to-Cube E2E，增加 FastAPI/httpx 依赖并将本阶段外部 watchdog 设置 930 秒。此真实 Gate 仍要求供应方 READY 模板及实际 Cube API，不会通过 Fake Cube 冒充。

此功能仅限本地可信运维实验，不是企业 IAM、会话授权、审批隔离、生产故障注入或 100 Active Runs 验收。Console Host 本身应仅监听 loopback，不应经公网暴露操作员入口；Token 由受信任部署环境提供及轮换，证据目录需受文件系统 ACL 保护。服务重启期间的不确定任务保留锁，按独立 Cube/PG 事实人工对账后才可恢复，并未尝试自动补发危险任务。

后续优先项是扩展 Cube-only、非幂等 Tool 的独立可信执行器与验证合同，而不是让多个场景复用 Worker Takeover 的 PASS。
