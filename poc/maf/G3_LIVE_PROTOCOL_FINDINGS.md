# POC-A G3 — 真实模型 Token → 平台 API / Typed Event / SSE

> 2026-10-08 | 状态：IMPLEMENTED / DATABASE TESTED / **REAL PROVIDER E2E NOT YET VERIFIED**

## 已新增的实现

- 独立 POST /v1/live/responses，与只接受 Document fixture 的原接口隔离。
- 公共 MAF create_harness_agent + OpenAIChatClient streaming，store=False，
  禁用文件记忆、Web、工具自动批准、Compaction、Todo 和 Mode；显式 tools=[]。
  **实测发现**之前仅禁用工具自动批准时 MAF 仍将 Todo/Mode 工具定义发给上游，
  已修复并通过真实 SDK wire-contract 测试校验。模型由可信本地配置限制。
- Run/Plan/Step/Attempt/Execution 先入 PostgreSQL。每一个真实非空
  chunk 在发出 SSE 之前写入 poc_events（sequence 与 Run 绑定）。
- Event type = response.output_text.delta；run.started/run.terminal 均为
  平台 Typed Event。GET Snapshot 只拼接已持久化 token。
- SSE Last-Event-ID 和 after 游标双路径；不同 Run 的游标拒绝，不一致游标拒绝。
- 空输出不宣告成功，模型异常/连接中断有明确失败分类，
  保留此前已落库的片段，不自动重试。
- verify_live_model_protocol.py 提供真正的 Uvicorn/LiteLLM/PG/重启验收入口；
  API Key 从 stdin 读取，不进入 argv、仓库或测试报告。
- 新增 Live Route 的非 loopback 拒绝和请求模型 allowlist 校验；异常取消不能
  生成成功终态，过长或超出 PostgreSQL seq 范围的 Last-Event-ID 返回 422。

## 已执行验证

- Python 3.12 开发环境已导入 FastAPI/httpx/psycopg/agent_framework。
- test_live_model_protocol.py：当前离线 **8 PASS / 1 PG 集成按条件 SKIP**；
  明确标识 Mock provider，测试先持久化再 SSE、失败脱敏、空流失败、
  取消失败、GeneratorExit/aclose() 后不遗留 RUNNING、Responses Snapshot、
  Loopback/Model Admission、超长或越界游标拒绝。GeneratorExit 用例先
  复现失败再修复验证通过（red → green）。
- 最终在独立一次性 Docker PostgreSQL（完成后删除）执行：
  G3 协议集成 **9/9 PASS**，原 A18-A21 协议回归 **3/3 PASS**；
  使用独立 HTTP 进程重启的 verify_selfhost_protocol.py **PASS**。
  其中 Token 片段明确为 **Mock Provider / Real PG**；独立进程重启是
  真实 MAF Document Fixture，不能冒充真实 LLM Token 全链路验证。
- Python compileall 新实现通过。
- 新增 verify_sdk_wire_protocol.py，使用**真实锁定版本 MAF/OpenAI SDK**、
  合成 OpenAI Responses SSE 上游（非真实模型）、两个真实 Uvicorn 进程和
  一次性 PostgreSQL。已执行 **PASS_REAL_SDK_WITH_SIMULATED_UPSTREAM**：
  SDK 向 /v1/responses 发送 stream=true/store=false、空工具列表；
  正常回复 3 个 Delta / 5 条事件均先落库再经平台 SSE 输出；重新启动 HTTP
  Worker 后 Snapshot 与 Last-Event-ID 回放一致。上游 HTTP 400 错误会形成
  FAILED / MODEL_STREAM_INTERRUPTED，服务端错误 Canary 不泄漏且不重试；
  失败 Run 同样可跨进程重放。脚本已纳入 GitHub Actions 工作流，但本轮未运行
  远端 CI。**模拟的是上游模型 API，不是 MAF SDK 或平台 Adapter。**
- LiteLLM 网关 /v1/models 在无凭据探测下返回 HTTP 401：证明目标可达，
  **不能**据此判定凭据有效或 G3 E2E PASS。
- Runner 全局 Python 缺 agent-framework-openai，且原有全局 openai SDK 版本
  不兼容。已在系统临时目录创建隔离 venv，安装仓库锁定依赖；
  **MAF OpenAIChatClient + create_harness_agent + Session 初始化 PASS**，
  `pip check`、`compileall` PASS。隔离环境最新离线回归 **90 tests，
  33 PASS、57 条因未启用所需集成条件而 SKIP**；上述独立 PostgreSQL
  集成已另外执行 9+3 项，不把 SKIP 伪称 PASS。
- 本轮试图通过执行工具递交聊天中已给的 API Key 受安全检查阻止；
  禁止以改写/混淆密钥规避检查，也不从聊天复制密钥到代码或 CI。
- A05 既有独立 LiteLLM + MAF 双轮流式与 History smoke PASS，不能替代本次
  全链路验证。

## 必须补齐方可将 G3 本切片判 PASS

1. 在独立临时 PostgreSQL 库与现有 LiteLLM 网关运行
   verify_live_model_protocol.py；检查真实 Stream 产生多个（至少一个）
   token delta、nonce 回忆/输出吻合、Event 持久化顺序。
2. 杀掉第一 HTTP 进程，由第二进程无模型密钥按 Last-Event-ID 读取相同 Run，
   比对快照内容与完整 Token 事件序列。
3. 若以上出现网络限制、Provider 错误、超时，应保留 GAP 而非模拟 PASS。

## 没有宣称的能力

这不是完整 Responses API（缺完整 item/content、Tool/Approval/Artifact/多模态）。
没有模型会话跨请求的持久 Chat History、真生产运行中重启自动恢复、
响应/Tool Exactly Once、生产 IAM/Admission 或公网安全边界。
本轮没有启动 G2/G6 非幂等 Receipt 自动对账，因为 G3 真实 Provider
端到端门禁尚未达到通过条件。旧 POC-A 决策 NO-GO 结论不被改写。
