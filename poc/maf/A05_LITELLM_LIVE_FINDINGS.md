# A05 — 真实内网 LiteLLM / MAF HarnessAgent 流式验证

2026-10-08。全部调用在开发机进行；任何 API Key、内网地址和
模型原始回复都不写入仓库、CI、Issue/PR 或 Evidence。

## 执行结果

- LiteLLM /v1/models 通过鉴权，返回 14 个模型。
- MAF OpenAIChatClient 经 OpenAI-compatible Gateway，
  使用真实 qwen3.8-flash，流式文本连续两轮。
- 首次原生默认 Server-managed History：两轮都有文本，
  但第二轮没有回忆到第一轮校验标记；MAF 发出了
  HistoryProvider in_memory / stores history server-side 警告。
  **不能把复用 AgentSession 对象当作会话连续性 PASS。**
- 使用官方 MAF create_harness_agent 的
  default_options={"store": False} 以后，显式客户端 History：
  两轮 stream 非空、第二轮准确回忆校验码，
  same_native_session=true、recall_verified=true。
  **A05 本次具体 Live Smoke PASS。**
- 第二模型实际调用未获得有效结果，A10/G4/S09 保持 GAP。
  能列出多模型不能替代真实 Provider Swap。

## 无凭据写盘的复现入口

以可信的临时 stdin 管道传入 API Key 的第一行，随后执行：

    python poc/maf/litellm_live_probe.py --model YOUR_MODEL --base-url YOUR_LITELLM_BASE_URL

实际脚本从 stdin 读取密钥，不在 argv、文件、stdout 中回显；所有
HTTP/工具权限默认不启用 File Memory、Web Search、Tool Auto Approval、
Compaction、Shell。未完成生产安全与正式 Session 持久化。

## 架构记录

LiteLLM/OpenAI-compatible Gateway 可能不支持服务端 Responses
conversation state；客户端模型 Adapter 必须验证具体 History 语义，
必要时使用 store=False + 平台持久 Session/History，并确保多轮、
跨进程复用及切换模型后的格式兼容。不能修改 MAF 内核来掩盖问题。
