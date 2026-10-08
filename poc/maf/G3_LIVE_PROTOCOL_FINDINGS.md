# POC-A G3 — 真实模型 Token → 平台 API / Typed Event / SSE

> 2026-10-08 | 状态：IMPLEMENTED / DATABASE TESTED / **REAL PROVIDER E2E NOT YET VERIFIED**

## 已新增的实现

- 独立 POST /v1/live/responses，与只接受 Document fixture 的原接口隔离。
- 公共 MAF create_harness_agent + OpenAIChatClient streaming，store=False，
  禁用文件记忆、Web、工具自动批准和 Compaction；模型由可信本地配置限制。
- Run/Plan/Step/Attempt/Execution 先入 PostgreSQL。每一个真实非空
  chunk 在发出 SSE 之前写入 poc_events（sequence 与 Run 绑定）。
- Event type = response.output_text.delta；run.started/run.terminal 均为
  平台 Typed Event。GET Snapshot 只拼接已持久化 token。
- SSE Last-Event-ID 和 after 游标双路径；不同 Run 的游标拒绝，不一致游标拒绝。
- 空输出不宣告成功，模型异常/连接中断有明确失败分类，
  保留此前已落库的片段，不自动重试。
- verify_live_model_protocol.py 提供真正的 Uvicorn/LiteLLM/PG/重启验收入口；
  API Key 从 stdin 读取，不进入 argv、仓库或测试报告。

## 已执行验证

- Python 3.12 开发环境已导入 FastAPI/httpx/psycopg/agent_framework。
- test_live_model_protocol.py：离线 5 个 PASS；包括真实模型片段 Mock
  的先持久化再 SSE、失败脱敏、空流失败、Responses Snapshot、游标约束。
- 同一脚本连接本地 Docker PostgreSQL 隔离临时库：
  6 个 PASS（包含 HTTP ASGI -> PostgreSQL -> Token Event -> 断线游标重放）。
  本条明确为 **Mock Provider / Real PG**，不能冒充真实 LLM 验证。
- Python compileall 新实现通过。
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
