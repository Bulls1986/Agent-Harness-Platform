# DEV-M5 B.3a · Inspector 受控场景执行与独立证据接口（2026-10-12）

## 判定

**受控执行 API / 页面合同 CODE_READY；真实 Inspector HTTP → Hatchet/PG/Cube 端到端 Gate 仍 OPEN，DEV-M5 整体 ACTIVE / Production NO-GO。**

在已有 B03 原生物理故障联合验收 PASS 的基础上，完成一个最小操作员授权的 Worker Takeover 场景运行入口。与之前仅可读的能力目录及 Harness PG 观察证据保持分离，避免将旧 Run 或假 PG Event 误判为当前真实执行。

## 本次实现

1. 原有 Inspector 默认只读，且该默认不因同一进程内另一受控实例启用而被修改；服务端必须明确设置开关、强随机操作员 Token 和独立证据目录才允许 B03。
2. 只有 worker-takeover 可触发固定后端 Verifier 模块。不接受客户端脚本、Shell 命令、执行参数或沙箱 locator；HTTP 无认证/错误认证/跨来源拒绝，服务端 localhost 实验边界保持不变。Cube-only 与非幂等 Receipt 场景仍是只读。
3. POST 仅返回未验证的独立执行 ID；GET 证据需同一 Operator 凭证。可信执行线程校验原生 B03 的 Run/Workflow ID、真实 Worker A/B PID、SIGKILL -9、Native Retry、同 Sandbox、PG Epoch、Guest 文件字节一致、旧 Owner/Scope 拒绝和 Destroy ACK。脱敏字段写入运行器私有目录，不持久化密钥、Guest 实际内容或原始 SDK/进程日志。
4. 一次只允许一个真实受控任务，跨服务进程用独占锁文件防重复执行；完成证据以临时文件 + fsync + 原子替换落盘。异常、错误证据、服务重启时无法确认的在途执行一律 BLOCKED_UNKNOWN 且不能无对账直接重试。服务端实际命令固定、无 shell，独立进程组超时时清理，避免遗留实验 Worker。
5. 保留两个 Tab；有服务端可信能力时 Worker 卡片才提供授权操作入口。临时凭证仅留在本页密码控件，页面不使用 localStorage/URL 存储，也不嵌入任何服务端 Key；UI 用 textContent 呈现受控状态与白名单结果。

## Red → Green 与证据

先增加 tests/test_trusted_scenario_runner.py，此时缺实现模块产生预期 RED；补齐可信执行器、HTTP API 与 UI 后，默认拒绝、错误凭证、Origin 拒绝、单活、错误 Native 证明不得 PASS、重启证据读回、默认目录隔离等测试 GREEN。受控本地合成回归 **6/6 PASS**；设计、OpenSpec 及架构 Guard 独立校验。真实 B03 既有 CLI 测试 PASS 记录位于 docs/retrospectives/DEV_M5_JOINT_WORKER_CUBE_IMPLEMENTATION_20261012.md，并**不能**替代本次新 HTTP 入口的实机执行。

保留的验证欠账：在受控 Linux/Cube/双 PG 的实际部署，运行 poc/closed_loop/verify_trusted_scenario_api_live.py 完成真实 POST → B03 → 持久证据 → GET（重启后）全链，并记录新产生的 Evidence ID、Run、Native Workflow、原 Sandbox/PID/Guest 回执。尚未取得这项结果前不得勾选 B.3/1.4 全项或对外宣称 Inspector 场景完全可执行。工作流 PR Head CI 也必须复查。

## 边界与复盘

此功能仅限本地可信运维实验，不是企业 IAM、会话授权、审批隔离、生产故障注入或 100 Active Runs 验收。Console Host 本身应仅监听 loopback，不应经公网暴露操作员入口；Token 由受信任部署环境提供及轮换，证据目录需受文件系统 ACL 保护。服务重启期间的不确定任务保留锁，按独立 Cube/PG 事实人工对账后才可恢复，并未尝试自动补发危险任务。

后续优先项是实际 API-to-Cube Live E2E，然后扩展 Cube-only、非幂等 Tool 的独立可信执行器与验证合同，而不是让多个场景复用一个假状态按钮。
