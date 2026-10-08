# POC-A / A40：MAF Workflow 跨 Agent SDK Adapter 对照实验

> 2026-10-08 | **本地真实 LiteLLM 双 Agent SDK + MAF Native Workflow PASS**
>
> 本文是已经归档的 POC-A A00–A39 决策之后的**增量对照**，
> 只验证 MAF Workflow 的 Agent Runtime Adapter 可替换性；
> 不重开原 POC-A 硬门禁，不把 MAF 升级为唯一 Harness Control Plane。

## 实际使用的公开 MAF 扩展点

- `WorkflowBuilder`：MAF 真正的 Workflow 执行图。
- `AgentExecutor`：官方可接纳 `SupportsAgentRun` 的封装器。
- `BaseAgent`：`AgentSdkBridge` 实现 `run(stream=False)`
  和原生 `AgentResponse / Message`；其背后真实执行外部
  **OpenAI Agents SDK `Agent + Runner.run`**，而不是模拟为
  MAF 自有 ChatClient。
- `Executor / @handler / WorkflowContext`：两个可信独立
  Verify 节点。中间通过官方 `AgentExecutorRequest` 将
  **同一原始模型输入**交给第二个 SDK，明确不传承第一个
  Agent 的原始对话历史或 Session。
- 第一段是 **MAF `create_harness_agent`**，禁用 File Memory、
  Web Search、自动 Tool Approval、Compaction，`store=False`；
  第二段 OpenAI Agents SDK 关闭 tracing，不启用 Tool。

二者运行在**同一 MAF Workflow** 的不同 `AgentExecutor`
实例；适配器不是静态标签/Provider 模型名切换。架构上仍是
Harness owns task facts，Agent SDK 可以通过 Adapter 替换。

## 与 C09 的公平对照

| 维度 | C09 Temporal Workflow | A40 MAF Workflow |
|---|---|---|
| 原生调度 | 真 Temporal OSS Worker/Activity | 真 MAF WorkflowBuilder/AgentExecutor |
| Runtime A | MAF HarnessAgent | 相同 MAF HarnessAgent |
| Runtime B | OpenAI Agents SDK | 相同外部 OpenAI Agents SDK，经 BaseAgent Adapter |
| 模型 | 同一内网 LiteLLM `qwen3.8-flash` | **同模型** |
| 模型输入 | 同一受控 `C09-xxxxxxxx` 标记结构 | **同输入** |
| 独立 Verify | 各一 Verify Activity | 各一可信 Verify Executor |
| Run/Attempt | PG 冻结与落盘 PASS | Platform-owned ID 穿图正确；**本 A40 不做 PG 落盘** |
| Session/Streaming/Crash 恢复 | 仍有全链 GAP | **A40 不支持跨 SDK Stream/Session/Checkpoint** |

本地真实模型验收 **两轮** PASS（初版和改用官方
`AgentExecutorRequest` 明确输入隔离后的最终版）：

`PASS_A40_REAL_MAF_WORKFLOW_WITH_TWO_AGENT_SDKS`

- 两套 SDK **均实际调用**同一模型网关，得到非空结果；
- 两个独立 Verifier 均从真实输出检查标记，才生成
  `COMPLETED`；
- 同一个平台 Run ID、两个不重复 Step/Attempt/Execution ID
  沿 MAF Workflow 传递，结构未改变；不将 MAF Session 当作
  平台 Run ID。
- 5 项无网络 SDK Workflow 负例/正例 PASS，尤其第一段 Verify
  FAIL 时第二个 Agent **调用次数为 0**；第二段失败不能产出
  成功结果。全部未写真实模型文本/Key/地址入仓库或 CI。
- 单独 CI 使用相同 pinned SDK 包进行真实 MAF 工作流
  **离线执行**，绝不因为 Mock 成功宣称真实模型调用 PASS。

## 范围与结论

本实验依赖 `agent-framework-core==1.20.0`、
`agent-framework-openai==1.15.0`、
`openai-agents==0.22.2`，参考
`poc/temporal/C09_REAL_RUNTIME_FINDINGS.md`。
A40 Adapter 仅实现 **非 Streaming** 的 `run`；
`run(stream=True)` 明确报 `NotImplementedError`，
不假装跨 SDK Token Streaming、Tools、History/Session、
HITL 或 Checkpoint 接口同构。

这里不复用 C09 的 Temporal 特定 Binding/PG 表，
也没有证明 MAF Workflow 使用外部 SDK 时的跨进程恢复、
真实非幂等 Tool、安全性或独立生产部署；这些仍受既有
POC-A G1/G2/G3/G6 判定约束。

**技术选型纠偏：在基本 Agent SDK 调用/编排/Verify 能力上，
MAF Workflow 与 Temporal Workflow 都可以通过公开扩展点
换用另一套 Agent Runtime。此能力不再作为 Temporal 的
独有优势；两者核心差异仍是 Durable Worker/History、
任务级恢复边界与生产运维成本。** G4 模型供应商替换仍 GAP。
