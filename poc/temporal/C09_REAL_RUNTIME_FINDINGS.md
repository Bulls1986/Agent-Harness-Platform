# POC-C C09：真实 Agent Runtime SDK 替换实证

> 2026-10-08 | **真实内网 LiteLLM + Temporal OSS/PostgreSQL + Harness PostgreSQL：局部 PASS**
>
> 本次证明的是两种不同 Agent SDK 的 Runtime 可替换性，**不是**
> 更换模型供应商、Sandbox 或正式企业 Tool 的完整 G4/G5/G6 验收。
> 真实调用只在授权的本地开发机执行，CI 无内网凭据、不会执行模型请求。

## 1. 两个实际独立的 Agent Runtime

| 层 | 验证的实物 |
|---|---|
| Native Orchestrator | 官方 Temporal OSS Server 1.31.0、独立 PostgreSQL 16 |
| Harness Domain | 第二套独立 PostgreSQL，Run/Plan/2 Step/2 Attempt/2 Execution、6 个 Typed Event |
| SDK-A | **Microsoft Agent Framework** `create_harness_agent` + `OpenAIChatClient`，Core 1.20.0、OpenAI Adapter 1.15.0 |
| SDK-B | **OpenAI Agents SDK** 0.22.2，`Agent` + `Runner.run` + `OpenAIChatCompletionsModel` |
| Provider | 相同的企业内网 LiteLLM / OpenAI-compatible Gateway、相同 qwen3.8-flash 模型 |
| Platform Verify | 由独立 `c09_independent_verify` Activity 从持久、冻结 PG Binding 读取期望标记，核对真实模型观测值 |

**这是不同 Agent Runtime SDK 的实际切换。** 两边连接同一个模型
网关，不属于两家模型供应商切换。官方 Python API 为
[MAF Harness Agent](https://learn.microsoft.com/en-us/agent-framework/get-started/harness)、
[OpenAI Agents SDK 的非 OpenAI Provider](https://openai.github.io/openai-agents-python/models/)。

## 2. 同一 Run 下真实闭环

1. Harness PostgreSQL 先提交唯一 Run、Plan v1、两个 Step/Attempt/
   Execution（本实验模型读取类任务为 PURE），冻结同一个 Native
   Workflow ID、Workflow 版本与两个 Adapter SDK 的运行版本。
2. 同一个 `poc-c09-real-runtime-swap` 原生 Workflow 顺序调度
   `c09_real_agent_runtime` 和 `c09_independent_verify` 两对
   Activity；最后 `c09_finalize_platform_run`。
   仅 Adapter 路由描述变化，Native Workflow 业务控制代码不导入
   MAF、OpenAI Agents、HTTP、PG 或文件 IO。
3. 实际 MAF HarnessAgent 使用 `store=False` 的 Client-managed
   History 模式，禁用 File Memory、Web Search、自动工具审批、
   Compaction；OpenAI Agents SDK 使用 Chat Completions 模型
   接口并关闭第三方 tracing。两边均调用真实 LiteLLM 模型。
4. 每个 Agent 的原始文本只在 transient Worker Activity 中存在；
   仅提取短标识与回答字符数，给独立 Verify Activity 检查。
   模型原始回复、Key、Proxy URL **不进入** Temporal History、
   Harness PostgreSQL、Event/SSE 或 CI。
5. 独立 Verify 在冻结的平台 Attempt/SDK Version 上通过后，
   原子更新 Execution/Attempt 与追加
   `activity.completed`、`verification.passed`。
   两边都通过才可提交 Run `COMPLETED`；
   若 Verify 不通过则落盘 FAILED，取消后续未运行 Attempt，
   不伪装为成功。
6. 真正的 Workflow Complete 不是唯一的业务事实；
   Harness 自有 Run/Attempt/Event 独立 PG 持久化可查询。

## 3. 实测与验收结果

两次独立本地 Live Run 在完成前后代码变更后均 PASS，最终结果：
`PASS_C09_TWO_REAL_AGENT_RUNTIME_SDKS_ONE_TEMPORAL_WORKFLOW`。

| 指标 | 实际值 |
|---|---|
| Agent Runtime | `maf-harness`、`openai-agents` |
| 真实模型请求 | 两种 SDK 均成功 |
| 同一 Native Workflow | **1** |
| Harness Run / Attempt | **1 / 2**（不同 Step 和 Execution） |
| 独立 Verification | **2 PASS** |
| Native Activity Completion | **5** |
| Native History Event | **35** |
| Harness Event | **6 条**：`run.started`、两组 `activity.completed` / `verification.passed`、`run.terminal` |
| Harness Run 终态 | **COMPLETED** |
| 模型回答或凭据写入 DB/History | **否** |

本地额外三项真实 PostgreSQL Contract 单测 PASS：
冻结版本/身份/不可变绑定、Verifier 与 Finalize 幂等、
Verifier 失败不得错误成功。另一条本地 Temporal OSS Workflow
采用显式 **Fake Agent Activity** 运行，验证与真实 SDK 同一
Workflow 的 2 Attempt、6 Event 契约；它不构成第二份真实模型证据。

## 4. 安全复现方式

Python 依赖固定在 `requirements-c09.txt`。
使用 C05 已运行的 Temporal OSS+PG 与 C06 的 Harness PG。
`verify_c09_real_runtime.py` 只从受信任进程环境读取
`POC_C_LITELLM_BASE_URL`、`POC_C_LITELLM_MODEL`、
`JUSDA_LITELLM_API_KEY`、`POC_C_PLATFORM_DSN`、
`POC_C_TEMPORAL_ADDRESS`。
**不可将 API Key 放入 argv、CI secrets（本轮无需）、提交文件、PR
正文或日志**。CLI 仅打印可公开的验证计数/状态，出错只打印异常类别。

```text
python -m pip install -r poc/temporal/requirements-c09.txt
python poc/temporal/verify_c09_real_runtime.py
```

公开 GitHub CI 不连接内部 LiteLLM。独立
[GitHub Actions #37772949991](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37772949991)
的 **4 个作业全部 SUCCESS**：其中 C09 SDK 同环境安装/导入
成功，实际 OSS Temporal + Harness PostgreSQL 的 11 项
Contract 检查和显式 Fake Activity 的原生 Workflow 成功；
C05/C06/C07/C10/C12 回归均保持通过。
[PR #31](https://github.com/Bulls1986/Agent-Harness-Platform/pull/31)
已合并 main（提交 `ed8c175`）。
**CI 不调用内网模型，不能将 CI Fake Activity PASS 当作 Live Model PASS；
真实 Live PASS 是独立开发机实测证据。**

## 5. 仍未覆盖

- 真实模型供应商/模型**切换**（G4 Provider Swap）未验证；
  这里两个 SDK 共享同一个 LiteLLM 模型和网关。
- 没有真实 Tool、Shell、Sandbox、Artifact OSS Payload、
  UI Model Token 流、多轮 Session 迁移或 Agent 跨进程断点恢复。
- C09 采用两次 PURE 模型读取；对非幂等 Tool 的 UNKNOWN/
  Fencing 仍以 C06/C07 为独立证据。本实验不证明 SDK 级 exactly-once。
- Native Workflow 与 Harness PostgreSQL 非分布式事务；
  Start ACK 丢失仍有潜在未绑定/未完成窗口，未在 C09 解决。
- 现有 C10 只读协议桥接只覆盖 C06 UNKNOWN 子集，尚未完整
  映射 C09 新的正例 Activity/Verification 事件到 UI；
  总体 G3 继续 PARTIAL。

**结论：C09 的真实双 SDK Runtime Adapter 替换 scoped PASS，
整体 POC-C 保持 OPEN；不得直接据此作最终平台选型。**
