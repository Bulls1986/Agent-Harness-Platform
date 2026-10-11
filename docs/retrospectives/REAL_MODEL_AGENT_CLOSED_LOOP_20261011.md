# M1 复盘：真实模型双 Agent 业务闭环（2026-10-11）

> 本轮只证明真实 LiteLLM Responses + Hatchet + PostgreSQL + Pydantic AI → OpenAI Agents SDK 模型级闭环。生产准入、真实 Token SSE/Cube/Receipt/审批仍为 OPEN。

## 实际结果

- LiteLLM 模型查询和 qwen3.8-flash 的 Responses/Chat Completions 调用均实际成功；API Key 来自本地环境，从未写入仓库/Prompt/Event。
- 实际 CLI Run：loop-26465ee92c4d42bfa26252dbad9312f8；Workflow：c3d7c94f-6fb7-4c7c-a309-de80922b983d；14 条 PG Events、两个 Step 各一次 Attempt，真实业务状态 COMPLETED。
- Pydantic AI 生成约 836 字符、验证通过的需求分析 JSON；OpenAI Agents SDK 审核后形成 2190 字符中文报告，包含功能/业务规则/验收条件/风险，审核判定 NEEDS_WORK；B 输入严格等于已持久化 A 输出。
- Live Inspector HTTP Run：run-04d87078786d46688b7d9d1f4dc4db2b；Workflow：688e6187-899e-43e7-89b9-c57d0bf3ecef；真实请求成功，14 条事件。重启 Live Inspector 后以原 Run 查询，再次通过，结果来自 PG。
- Test-first：先写模型配置/结构化输出/恶意格式负例，初始因实现模块不存在失败，再实现并通过；真实 Docker PG/API/Model 合同 13 项通过，OpenSpec strict PASS。GitHub CI 最终证据以最新提交 Run 为准。

## 失败、根因、修复

1. **Worker 混用：** 旧本地 Inspector Worker 和 Live Worker 曾注册同名 Hatchet Workflow，导致第一个标记为 Live 的 Run 被旧 Worker 执行固定输出，且平台过早写业务 COMPLETED。修复为分离版本化 Workflow 定义、在 Run 创建时冻结模式/模型 ID、Worker 校验实际绑定、Harness 写业务 Terminal 前核对明确且与持久 Step 输出完全一致的 Verification Evidence。加入模式漂移/未验证终态负例测试。错误历史保留，不声称这是 Live PASS。
2. **Task 1 分钟超时：** 第二轮真实模型 A 已成功但 B 超过 Hatchet 默认 execution_timeout，Workflow FAILED。公开 Task 执行超时显式提升至 4 分钟，Responses SDK Client 设为有界 150 秒并关闭内部自动重试，真实第三轮通过。未来按模型 SLA 调整，不把 POC 阈值直接认定为生产值。
3. **正确性分层：** 有效 JSON 只代表结构正确，不代表业务无遗漏；审核输出也需要真实业务验收样本。模型 Provider 网络失败、结构失败和 Durable Task 失败必须明确区分，不得伪造最后结果。

## 固化经验与架构规则

- 同一队列中不同 Runtime Capability、模型运行模式或冻结版本不能静默混用 Worker；Provider Binding/Capability 需要严格匹配。
- Domain terminal 是平台的业务裁决，永远不能单凭 Hatchet SUCCEEDED 推断；真实输出和 Verification Gate 缺失则 Fail Closed。
- Tool/Model 的超时、Retry、预算与 Hatchet Durable Retry 分层配置；未知副作用不能盲目重放。
- 模型密钥只由外部环境/企业 Secret 提供，PG 存业务事实而不是 Secret；Pydantic/OpenAI 使用公开 SDK 扩展点，不创建第二套 Scheduler。
- 确定性 CI 的 PASS 不代表 Live 通过；本轮分别保留实际远程模型运行与本地 Mock-free SDK 证据。

## 仍未收口

真实上游 Token SSE → Harness 持久游标/取消/断线回放，Cube Worker A/B 续连与授权、非幂等 Receipt UNKNOWN、Durable Approval、100 并发、旧 PDLC M0–M4 迁移仍为 OPEN，不因本轮 Model LIVE PASS 就认定完成。