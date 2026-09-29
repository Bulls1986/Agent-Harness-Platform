# Conversation / UI Protocol 讨论

> 状态：讨论参考

## 1. 为什么需要独立协议层

UI 不应该直接理解某个具体 Runtime / Sandbox 的事件，例如 Agents SDK、Codex、MAF、ADK、CubeSandbox 等。

建议：

~~~text
Runtime Event
    ↓
Event Translator
    ↓
Conversation / Harness Protocol
    ↓
UI
~~~

## 2. 推荐传输方式

常规场景：

- UI → Server：HTTP Command
- Server → UI：SSE Event Stream

特殊场景：

- Terminal：WebSocket
- Voice：WebSocket/WebRTC
- Computer Use：WebSocket/stream channel

## 3. 对象模型

~~~text
Conversation
  ↓
Turn
  ↓
Run
  ↓
Item
  ↓
ContentPart
~~~

### Item

- Message
- ReasoningSummary
- ToolCall
- ToolResult
- Plan
- Activity
- Verification
- Approval
- Artifact
- Error

### ContentPart

- Text
- Markdown
- Image
- File
- Audio
- Citation
- Artifact
- Widget

## 4. Responses-compatible core

OpenAI Responses API 的 Item/Content Part/typed streaming event 模型适合作为协议参考。

但平台协议不能简单等同于 Responses API，因为平台中心是：

~~~text
Harness Run
~~~

而不是：

~~~text
Model Response
~~~

因此建议：

> **Responses-compatible core + Harness Extensions**

Harness Extensions 至少包括：

- plan.created
- plan.step.started
- plan.step.completed
- activity.started
- activity.completed
- verification.started
- verification.failed
- verification.passed
- approval.requested
- approval.approved
- artifact.created
- run.completed

## 5. Reasoning 与 Activity

必须区分：

1. Raw model reasoning
2. Reasoning Summary
3. Observable Agent Activity

平台不把 raw chain-of-thought 作为 UI 协议。

UI 可以展示 Reasoning Summary，也可以展示真实执行活动，例如“正在读取文件”“正在运行测试”“正在检查 Diff”。这些 Activity 必须来自 Harness Event，而不是模型生成的伪进度。

## 6. 文件与图片

图片和文件不应该直接通过 SSE 传二进制。

推荐：

~~~text
Browser
  ↓ create upload
Platform
  ↓ presigned URL
Object Storage (S3/MinIO)
~~~

消息中仅引用 `file_id`。

FileResource 应管理：

- storage key
- mime type
- size
- checksum
- tenant
- permissions
- processing/indexing state

## 7. Artifact

Artifact 与 FileResource 不同。

Artifact 是业务产物，例如：

- Markdown
- PDF
- PPT
- Excel
- Code Patch
- HTML Report

Artifact 应支持：

- version
- lineage
- preview
- source run/step
- backing file

## 8. UI Event Envelope

建议统一事件外壳：

~~~json
{
  "event_id": "evt_123",
  "sequence": 108,
  "conversation_id": "c_1",
  "turn_id": "t_2",
  "run_id": "r_3",
  "item_id": "i_4",
  "type": "plan.step.started",
  "schema_version": "1",
  "timestamp": "...",
  "data": {}
}
~~~

`sequence` 用于 SSE 重连后的 replay。
