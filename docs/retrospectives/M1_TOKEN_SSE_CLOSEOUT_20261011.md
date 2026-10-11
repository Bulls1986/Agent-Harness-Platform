# M1 Token SSE 最终收口复盘（2026-10-11）

> **范围：** model-only PURE Agent POC，真实 LiteLLM Responses 模型 → Pydantic AI / OpenAI Agents SDK 公开流式接口 → Harness PG Event → Run-scoped SSE/Last-Event-ID/主动取消。通过 M1 LIMITED LIVE POC 并不代表企业生产准入；IAM、审计保留、PII/DLP、Backpressure、Cube、Receipt 和 PDLC 迁移仍单独 OPEN。

## 一、真实验证结果

- 完整 Live Run：`run-77d37bcccae64deba2fba31e5b99dba1`；Workflow：`e52d128a-d2f9-4ce2-aeb4-7039dd11248b`；`qwen3.8-flash`，Hatchet + Docker PG。Pydantic AI 发出 78 条、OpenAI Agents SDK 发出 429 条真实 `source=provider_stream` 响应文本片段；共 519 条 PG 事件，Step A/B 实际 Output 与模型回传一致，Run COMPLETED，最终为需求分析及审核报告。
- 两节点 Token 的 `seq` 均严格早于各自的 `step.completed`，不同于旧版结束后一次性 buffered output；执行中网页可通过 SSE 消费，EventSource 使用服务端 event id 自动断线恢复。
- 对该历史 Run 重启 `harness-real-inspector-m1` 容器后，使用同一 Run ID 验证从 0 重放 519/519 条，`Last-Event-ID` 从中途恢复严格大于游标，源 PG 的排序、结果和 Provider Binding 不变。
- 真实取消 Run：`run-e701ab9f4918400e9b0ce74c5b1d593e`；Workflow `39c8addf-04c0-4516-a96e-6e31a6a48d83`；上游真实流产生 4 条 Pydantic delta 后 POST Cancel，持久 `run.cancel.requested`，Worker 终止 SDK Stream 后确认 `CANCELLED`；总 10 条事件，取消后的 Token=0，业务 `run.completed`=0。
- PostgreSQL/UI/模型/取消 17 项无 skip 测试通过；其中多页终态 SSE (>250 events) 专项回归，OpenSpec strict 验证通过。GitHub 主分支 CI 以相同 PR Head 的最终工作流记录为准。

## 二、测试先行 Red→Green 与失败根因

1. **Red：** 先建立三组真实 PG 测试，证明此前无 `append_stream_delta` / `request_cancel` / SSE cursor endpoint，测试失败；Green：新增 PG 串行事件、SSE 通道和 Worker 取消确认。
2. **取消竞态：** 原先 PG 在 CANCEL_REQUESTED 后拒绝新 Token，但迟到的 SDK 回调因此引发 `run.failed`，Worker 误作系统失败，没有确认取消。更改顺序为：SDK 任务已 awaited/停止 → 检查 Durable Cancel Intent → Worker ACK → Harness 才写 CANCELLED；不能在尚有未确定执行时伪造终态。
3. **终态分页丢失：** 已完成 Run 的事件超过 250 条时，最初的 SSE 在第一批返回后直接停止。初版实时黑盒验证只判断收到的序列为 PG 子集，遗漏仍被认为 PASS。修复终态后排空多页（每次 250）并强化验证为 SSE 接收 ID 集合与 PG 事件 ID 集合完全一致；新增 280 条事件的端点回归。
4. **缓冲不等于流：** 原 Adapter 的 buffered event 在模型完成后输出整段文本，不能作为 Token SSE。新 Live 模式 Pydantic AI `run_stream.stream_text(delta=True)` 和 OpenAI Agents `Runner.run_streamed` 的公开 raw Responses event 才会写 `source=provider_stream`。

## 三、架构审计及限制

- Hatchet 是唯一的技术 Workflow/Task/DAG/Retry 权威；Harness PG 是 Domain Run/Step/业务事件/Result/Cancel Intent 权威。AgentRuntime SPI 负责翻译 SDK 事件，不直接决定最终 Run state。
- SSE event id 为 `run_id:seq`，服务器查 PG 并按 cursor 有序重放；跨 Run/无效 cursor 拒绝。浏览器断开不会取消后端 Run。取消必须单独 HTTP 命令及 Worker ACK。
- 任意模型原始文本是**未验证草稿**；经过结构验证、保存 Step 和 domain complete 后才算最终业务结果；不记录模型原始隐藏推理或其他非预期私有信息。
- 当前仅 localhost POC，直接把短文本片段写 PG，尚未实现生产级分块合并、背压、配额、PII 脱敏、Secret Vault、企业 IAM/OSS 大产物或跨 Worker Lease/Cube。不得将其标为 production GO。

## 四、可复用工程经验

**前端实时动了，不等于真正上游流式。** 必须提供真实 Provider Event 的独立证据、持久序列和断线后完整重放。**取消状态不等于取消成功。** 只有 Worker 观察、停止、确认后才提交业务 CANCELLED。**集成验收需要覆盖超过默认分页容量的长历史**，而不是只测小数据 Happy Path。