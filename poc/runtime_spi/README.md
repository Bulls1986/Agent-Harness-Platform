# AgentRuntime SPI / 三适配器最小 POC（2026-10-10）

> **POC / 未 Accepted**；归属 ARCH-TODO-025，不替代已有 Run/Step/Attempt、Execution Lease/Receipt 的 Accepted Contract。

## 已交付

- `contract.py`：平台自有 `ExecutionContext`（Run/Turn/Session/Execution/Owner/Fencing/Scope/WorkspaceRef）、`SandboxGrant`、`RunRequest`、`AgentRuntimeDispatcher`、严格绑定预检、取消和顺序 Typed Event/SSE 编码，不按历史 Session 数建立专属进程。
- `adapters.py`：Pydantic AI **官方公开 `Agent.run`**、OpenAI Agents **官方公开 `Runner.run`**，输出统一 `response.output_text.delta`（目前缓冲文本**不是逐 Token SSE**）。OpenCode 2 的 `session.prepare` 适配器接受经可信 Sandbox Lease 绑定的公开 V2 Session Factory；**不宣称实现 OpenCode 模型 Agent Loop**，对 `model.run` 明确 `run.unsupported`。
- `verify_runtime_spi.py`：无 SDK 离线模式验证 6 类无租约/错 Scope/错 Fencing/错 Owner/错 Execution/错 Capabilities 全部 Fail Closed、无 Sandbox 的普通 Run、取消后副作用 UNKNOWN、运行失败、事件伪造拒绝、OpenCode Session Factory Mock。
- `--sdk`：在真实安装的 `pydantic-ai-slim==2.54.0` 和 `openai-agents==0.23.1` 上调用各自**实际 Runner/Agent SDK**，使用各自公开的确定性本地 Model（零外部模型访问）；两个 `model.run` 都映射平台 Run 事件 **PASS**。

## 可复验

```sh
python -B poc/runtime_spi/verify_runtime_spi.py
# 在具备 pydantic_ai 与 openai-agents 的隔离 Linux venv：
python -B poc/runtime_spi/verify_runtime_spi.py --sdk
```

## 仍未实现/准入

- Runtime 持久化、真正 **Token 级 SSE**、统一 Run 到 Tool 执行归属、可信 Source 生成并持久化 Sandbox Grant、平台 Tool Dispatch Intent / Receipt 落盘及 ACK 对账、Worker Crash Recovery/Cancel 真实进程停止；
- Pydantic Harness 内置 E2B/Coder、OpenCode V2 真实模型调用和 `model.run`、MAF Adapter；
- CPU/内存/高密度多 Run/Session、跨 Scope 真实并发及 Host 绕过全面负例。

平台级的 `ToolReceipt` 只能来源于外部可信执行/Receipt Reconciler，**当前 POC 不会从成功的模型文本或取消事件伪造持久化 Receipt**。SDK 模型返回的 `delta` 仅表示适配后的文本片段，不应展示为真实 token streaming。
