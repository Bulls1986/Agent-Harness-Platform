# POC-A：Microsoft Agent Framework 完整任务计划

> 状态：执行计划（2026-10-08）  
> 目标：验证 MAF HarnessAgent + Workflow + Self-host + Durable Extension 在 Agent Harness Platform 中的适配位置。  
> 权威约束：[`docs/ARCHITECTURE.md`](ARCHITECTURE.md)、[`docs/POC.md`](POC.md)、根目录 `AGENTS.md` 和相关 Accepted Contracts。  
> **范围控制：不设计另一个 Agent Framework，不自建 Durable Task 后端，不把 IAM/MCP 治理/计费/存储 DR/APM 扩入 Harness。**

## 0. 评估目标与状态口径

POC-A 必须给出三个独立结论：

1. **Agent Runtime**：MAF HarnessAgent 是否适合作为可替换的 Runtime / Agent Component。
2. **Workflow Engine**：MAF Workflow + 公开扩展点是否能表达平台 Plan → Execute → Verify → Replan，并保持平台的确定性状态控制。
3. **Durable Control Plane**：MAF Durable 在完全私有化生产约束下，是否能通过已有官方基础设施实现跨进程/Worker 的可靠恢复与 HITL；如果不能，降级为 Agent Runtime，与外部 Durable Engine 组合。

任何 `PASS` 都需要实际运行/故障证据；Mock/SDK 导入不能声称 G1/G2/G3/G6 通过。每项任务状态取 `TODO / IN_PROGRESS / PASS / FAIL / GAP / BLOCKED`。目前只有 A00 的离线 SDK/单元测试/CI 已通过，真实模型 Smoke 尚未完成。

- **一级硬门禁**：G1 自托管、G2 状态自主、G3 协议桥接、G6 任务级恢复。
- **其余一级门禁**：G4 Model、G5 Sandbox、G7 HITL、G8 License/Managed Feature Cliff；均要记录结果，失败必须说明替代方案及代价。
- **业务场景**：S01～S12 均给出 PASS/FAIL/GAP；非 Coding 的文档对照必须使用同一套平台事件与任务状态。
- **承诺范围**：恢复只处理 Run/Step/Attempt 等任务级执行事实和 Provider Opaque Recovery Reference；不验证数据库/磁盘/OSS/Region Backup/DR。
- **产品边界**：大 Payload 存 OSS/S3-compatible；PostgreSQL 存任务事实、metadata、lineage、digest、storage reference；OTel 优先复用原生 instrumentation。
- **技术路线**：Python 优先；在不依赖 Foundry Hosted Agents 的前提下完成验证。语言本身不是评分项。

## 当前执行证据快照（2026-10-08）

- A00：已完成基础 MAF 官方包导入与离线双轮 Streaming Stub 测试；未发起真实模型调用。
- A01：已固定 Core 1.20.0、OpenAI Adapter 1.15.0，并通过 [GitHub Actions #37714557447](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37715048965) 的 API/version probe；其他扩展点仍未逐一验证，保持 IN_PROGRESS。
- A02：Coding/Document 均配置 broken/reference 两套固定样例，独立 Verifier 与离线回归通过；副作用 UNKNOWN 注入按 A28 另行实施。
- A03：Compose 配置、MAF 镜像构建、PostgreSQL SQL 查询及 OTLP Collector 启动均已通过 CI；OSS 实际接入留给 A15，外部对象存储产品不属于 Harness。
- A04：Evidence 模板及防止默认 PASS 的离线测试已通过 CI；后续每个 Gate 必须分别填写真实记录。
- A05：仅提供真实模型探针；当前没有已验证的实际 Provider 会话结果，因此不标 PASS。
- A31：已形成 [Durable preliminary findings](../poc/maf/DURABLE_FEASIBILITY.md)，但跨 Worker/Functions+MSSQL 尚未实测。

## 1. 阶段与详细任务

列中“验收”描述**可以客观验证的最小完成条件**。每任务必须提交运行入口、测试及 Evidence URI/Trace/Log 摘要，并标注 MAF 公共 API 与 Adapter 边界。不得用 Agent 自我宣称成功替代验证。

### A0 — SDK 与 POC 基线

| ID | 任务 | 依赖 | 交付物 | 可执行验收 | 状态 |
|---|---|---|---|---|---|
| A00 | 建立最小 HarnessAgent Smoke、双轮 Session 单测与 GitHub Actions CI | 无 | `poc/maf/smoke.py`、测试、CI、README | 官方公开 API 包导入、py_compile、离线单测在 CI PASS；**仅这些证据**，不代表真实 Runtime/Gate | PASS（offline） |
| A01 | 固定 MAF Python 依赖/公开 API 可用性矩阵 | A00 | lock/constraints、版本和来源记录、Public API inventory | 在固定版本完成 public import + Session/stream/tool/workflow/host 扩展点探针；升级不兼容有具体记录；识别 prerelease | IN_PROGRESS（直接依赖与公共 API 导入已在 CI 验证；扩展点行为仍待证实） |
| A02 | 统一 POC 测试任务与成功标准 | 无 | `fixtures/` Coding 修复与 Document 对照、expected outputs、criteria | 两类任务输入和验收固定，Verify 由代码独立判断；能稳定注入故意失败与副作用不确定 | IN_PROGRESS（正反验收已验证；UNKNOWN 副作用注入仍属 A28） |
| A03 | 最小自托管环境与运行入口 | A01 | Compose/配置样例、PostgreSQL、OSS-compatible、OTLP 接收端、启动说明 | 无 Foundry 依赖能启动服务/环境；密钥环境注入，不写仓库；不要求外围生产基础设施 | IN_PROGRESS（PostgreSQL/OTLP 实际启动及 MAF image 构建已通过；企业 OSS Adapter 和自托管 Agent API 后续 A15/A18） |
| A04 | 建立 POC Evidence 与 Gate 记录模板 | A02 | 每任务结果清单、case id、版本、run_id、测试记录、Gap 模板 | 每条结论可反查测试命令、配置版本、退出码、事件及 Artifact/Evidence URI；失败不标 PASS | PASS（模板及离线结构验收通过；各 Gate 的真实执行证据另行采集） |

**A0 Exit**：A00～A04 完成，并可以重复启动固定版本的测试环境（不宣称核心门禁通过）。

### A1 — HarnessAgent 原生能力（Runtime Fit）

| ID | 任务 | 依赖 | 交付物 | 可执行验收 | 关联 |
|---|---|---|---|---|---|
| A05 | 真实模型双轮流式 Smoke | A01、A03 | CLI/测试报告 | 实际 Provider 返回流式 chunk；同一 native session 两轮上下文连续；不暴露 API key；失败可分类 | S01 / G1 预验证 |
| A06 | Plan / Todo / Mode 原生能力探针 | A05 | Provider mapping + 示例 | Plan/Todo/Mode 变更可观察并映射到平台 Plan vN/Step；不可将自由文本 TODO 当已验收 Plan；多轮状态正确 | S03 |
| A07 | Harness Context / History / Compaction 探针 | A05 | custom ContextProvider/HistoryProvider prototype | 可通过公开扩展点注入/检索上下文；多轮和 Compaction 前后事实可验证；对不支持能力明确 GAP | Runtime Fit |
| A08 | 循环、停止与限额 | A06 | Runtime loop control adapter | max_iterations/max_replans/max_runtime 可分别触发、退出并形成正确状态；不能只靠 Prompt 自律 | S03/S06 |
| A09 | Tool approval 与 Middleware 边界 | A05 | Middleware/Policy stub、approval trace | 验证默认自动审批策略并关闭或替换；敏感 Tool 在平台批准前不可执行；仅通过公开 Hook/API | G7 预验证 |
| A10 | Custom ChatClient / ModelGateway 映射 | A05 | Provider Adapter、两个 Provider 测试配置 | Provider A/B 替换不修改平台 Run/Step/Artifact Domain，记录兼容差异；本项不自建 Model Gateway | G4/S09 |

**A1 Exit**：确认 MAF HarnessAgent 提供哪些真正可复用的能力；每项明确 Native / Adapter / Unsupported，记录实现复杂度。

### A2 — Workflow、执行与产物（Correctness）

| ID | 任务 | 依赖 | 交付物 | 可执行验收 | 关联 |
|---|---|---|---|---|---|
| A11 | 平台 Workflow 状态机映射 | A02、A06 | MAF Workflow / Executor adapter、状态转移表 | Run/Plan/Step/Attempt/Execution 使用平台 ID；最终状态由确定性代码控制，MAF 内部 ID 仅作 binding | S03 / S04 |
| A12 | Execute 与 Verifier 解耦 | A11 | Executor/Verifier、固定测试入口 | 读取固定 Demo repo、修改文件、执行验证；测试失败形成 VerificationFailure + Evidence，Agent 自我评价不能完成 Run | S04/S05 |
| A13 | Failure Classification / Retry / Replan | A12 | FailureClassifier、ReplanPolicy 适配 | transient 失败可 Same Step + New Attempt；语义/验收失败生成新 Plan Version；历史不可覆盖；超限正确终止 | S06 |
| A14 | SandboxProvider 接入 | A12 | CubeSandbox Adapter、可选 Docker smoke adapter | Shell/Git/文件操作仅在 Sandbox 内发生；Control Plane 不直接运行命令；替换 Adapter 不改 Workflow；不要求第 2 套生产级 Sandbox | G5/S04/S10 |
| A15 | Artifact/Evidence + OSS 对象引用 | A12、A03 | ArtifactStore Adapter、metadata schema | 文件/测试报告/大证据 Payload 进入 OSS；DB 保存 id/digest/size/mime/producer/lineage/object ref；可下载并验证 checksum | G2/S02/S05 |
| A16 | MCP/Tool 能力调用与副作用记录 | A11 | Tool adapter、MCP smoke、SideEffectReceipt | 可调用企业已准入的 MCP Tool 并追踪输入/输出/异常；不建设 MCP Registry/Trust；非 PURE 有回执及 UNKNOWN 处理入口 | G5 边界 |
| A17 | 两类实际 Recipe E2E | A12～A16 | Coding + Document 测试报告 | Coding 可从 Plan/Execute/Verify/Replan 结束并存 Artifact；Document 路径复用统一协议和任务事实，完成抽取/报告校验 | S02～S06 |

**A2 Exit**：存在一个真实端到端 Harness 执行闭环，验证完成条件由平台拥有，不由模型口头宣布。

### A3 — Self-hosting、Responses 与 Event Protocol

| ID | 任务 | 依赖 | 交付物 | 可执行验收 | 关联 |
|---|---|---|---|---|---|
| A18 | 自托管 MAF API Service | A05、A11 | FastAPI 自托管进程、容器/Compose、health/API | Foundry Hosted Agents 不参与；本地/企业可部署；清楚区分 Python prerelease Hosting 库风险与普通 Agent Runtime | G1/S12 |
| A19 | Responses-compatible 请求/响应桥接 | A18 | API contract tests | 文本、会话 continuation、流式 response 到 MAF 请求/响应映射；不直接把 MAF native session id 当平台 Run ID | G3/S01 |
| A20 | Harness Typed Event Translator | A11、A19 | Event Translator 与 golden fixtures | 最少包含 run/plan/step/tool/verification/artifact/approval/terminal events；sequence、run_id、step_id、attempt_id 可对齐；协议版本受控 | G3/S11 |
| A21 | SSE 重连、事件持久化、取消 | A20、A23 | SSE viewer、event replay、cancel API | 断开后按 sequence 恢复历史事件，续流无错序/重复业务状态；取消传播并尊重 CANCELLING/UNKNOWN 规则 | S01/S11 |
| A22 | Multimodal 与非 Coding 输入 | A15、A18、A19 | text+image+file input fixtures、Document result | 必要媒体经 Provider 能力/Adapter 入参映射，产物写 OSS；能力缺失明确记录为 GAP，不造假实现 | S02 |

**A3 Exit**：可被平台 UI 消费的自托管协议可运行；G3 具备事件/重连证据。

### A4 — Task Facts、Checkpoint 与任务级恢复

| ID | 任务 | 依赖 | 交付物 | 可执行验收 | 关联 |
|---|---|---|---|---|---|
| A23 | 平台执行事实持久化 | A11、A03 | Postgres tables/repository/migrations | Conversation/Turn/Run、Plan vN、Step/Attempt/Execution、Approval、Event、RuntimeBinding、RecoveryPoint、Artifact/Evidence reference 可重读；状态迁移原子性有测试 | G2 |
| A24 | SessionStore/HistoryProvider 持久化 | A07、A23 | MAF Session/History Adapter、重启测试 | 不用 in-memory store；两轮会话跨进程恢复且身份不混淆；与平台 Conversation/Run ID 映射不串线 | G2 |
| A25 | Workflow checkpoint Opaque Adapter | A11、A23 | Capability declaration / CheckpointStorage adapter | checkpoint_ref 与能力声明被持久化；可恢复只使用公开 checkpoint API；不可用时返回 unsupported/incompatible，不能复制或解释内部快照 | G2/G6 |
| A26 | Waiting Approval / Input 恢复 | A09、A23、A25 | Approval state + resume handler | WAITING_APPROVAL/WAITING_INPUT 的同一 Run 跨 API/Worker 重启仍处于等待；授权事实来自外部可信输入；批准后继续同一 Run | G7/S08 |
| A27 | Step Boundary Recovery 故障注入 | A12、A23、A25 | Worker kill/restart 回归用例 | 完成 Step 不重做；失效 Step 仅在安全可重试时 Same Step + New Attempt；Runtime 不支持 Same Attempt 时明确记录 | G6/S07 |
| A28 | UNKNOWN/Reconciliation 与重复投递 | A13、A23、A27 | side-effect simulator、receipt/idempotency/reconciliation tests | 发出外部写操作后丢响应进入 UNKNOWN → Reconciliation；不可 blind retry；同 idempotency_key 重投不得产生重复副作用 | G6/S07 |
| A29 | Cancellation/Timeout 与 Worker Ownership | A21、A23、A28 | cancellation tests、fencing/ownership boundary tests | Cancel 不直接置 terminal；已 dispatch 的未知副作用进入 Reconciliation；旧 Worker 的过期写入被拒绝；只管 Harness 自有 Execution | 正确性 Gate |
| A30 | 恢复覆盖矩阵 | A24～A29 | 恢复能力矩阵及 Gap/Evidence | 分别给出 Waiting / Step boundary / Same Attempt / Workspace restore / Sandbox snapshot 的已证实支持范围；不宣称没有测试的能力 | G6 |

**A4 Exit**：能解释 Run 恢复了什么、没有恢复什么，以及为什么没有重复有风险的副作用。G2/G6 以实测判断。

### A5 — MAF Durable Production Viability（独立路线 Gate）

普通 Workflow checkpoint 与 MAF Durable Extension 必须单独测试，**不能用进程内/本地文件 Checkpoint 或 DTS Emulator 通过生产 Durable Gate**。

| ID | 任务 | 依赖 | 交付物 | 可执行验收 | 关联 |
|---|---|---|---|---|---|
| A31 | 固定 Durable 公开能力与基础设施矩阵 | A01 | Python Durable Extension + backend/hosting compatibility matrix | 区分 self-host BYOC + DTS、Durable Functions + MSSQL、Emulator；核对官方支持范围、离线/私有部署、发行成熟度；未知标未验证 | G1/G8 |
| A32 | 完全私有化 Durable 最小可行部署 | A31、A03 | 部署说明、容器配置、依赖清单 | 优先按 Accepted Contract 实测 Python MAF + Durable Functions Runtime + MSSQL；若当前版本不兼容则记录精确 API/托管阻断，不能自建 TaskHub / scheduler | G1/G8 |
| A33 | Durable 跨 Worker/进程恢复及等待 | A32、A26 | 两 Worker + backend 故障注入证据 | Worker A 故障后 Worker B 接续；WAITING_APPROVAL 经过所有 Worker 重启仍存在；检查有无重复执行，后端必须真实持久化 | G6/G7 |
| A34 | Same Attempt Resume / Workflow replay / version | A33、A25 | 真实恢复证据、升级兼容测试 | 仅底层支持 checkpoint/resume 时才报告 Same Run + Same Step + Same Attempt；否则只报告 Step Boundary；Run 冻结版本，不能隐藏不兼容 | G6/G8 |
| A35 | Durable 架构分叉结论 | A31～A34 | `MAF Control Plane / MAF Runtime only` 决策记录 | 私有化 Durable 失败、后端成本超限或依赖侵入式补齐时，明确 MAF 降级为 Runtime，Control Plane 另交 Temporal/已有 Durable Engine；领域模型不变 | 架构决策 |

**A5 Exit**：不能只证明 DTS Emulator 能跑；必须说明可生产私有化的真实 backend、Worker 恢复边界及其运维/许可代价。未通过时停止把 MAF 作为 Durable CP 的投入，但保留其 Runtime 评估结果。

### A6 — Observability、统一验收与退出

| ID | 任务 | 依赖 | 交付物 | 可执行验收 | 关联 |
|---|---|---|---|---|---|
| A36 | 原生 OTel 与关联字段 | A11、A18 | OTLP 配置、trace 例子、correlation schema | MAF native trace/span/log/metric 原样保留；平台仅补 run/step/attempt/execution correlation；长任务允许 Run:Trace=1:N；默认不输出敏感 Prompt/Result | Observability |
| A37 | 故障注入矩阵与安全重试 | A27～A29、A33 | 每个注入案例可重复脚本和输出 | 覆盖 Model timeout、Worker crash、Sandbox crash、Verifier fail、UI disconnect、Approval wait，以及 UNKNOWN 副作用、重复投递、旧 Worker 恢复；不能只跑 happy path | S07/S08 + G6 |
| A38 | 可替换性/性能/成熟度对比 | A17、A20、A30、A34、A36 | TTFT、orchestration overhead、替换改动统计、组件依赖/许可清单 | 记录实测版本、CPU/RAM、恢复重复次数、Provider/Sandbox 切换修改范围、Python prerelease/API breaking risks；不填臆测性能数据 | G4/G5/G8 |
| A39 | POC-A 结论与最终交付 | A30、A35、A37、A38 | MAF POC 报告、G1～G8/S01～S12 矩阵、ADR 候选、可复现入口 | 每个核心 Gate 都明确 PASS/FAIL/GAP + 证据；独立给出 Runtime Fit、Workflow Fit、Durable CP Fit；说明转入 Temporal POC 的待决项 | DoD |

**A6 Exit**：完成决策所需证据，而不是宣称“所有企业能力已经建设完成”。

## 2. 推荐执行与并行关系

```text
A00 已完成（离线/CI）
  ├─ A01 固定 SDK/公开 API
  ├─ A02 任务数据与 Acceptance Criteria
  └─ A03/A04 环境与证据基线
       │
       ▼
A05～A10 Harness 原生能力
       │
       ▼
A11～A17 Workflow/执行闭环 ───────────────┐
       │                                 │
       ├──► A18～A22 自托管/协议           │
       │                                 │
       └──► A23～A30 状态/任务级恢复 ◄──────┘
                  │
                  ├──► A31～A35 Durable 生产验证
                  │
                  └──► A36～A39 观测/故障/最终评审
```

允许 A31「Durable 基础设施路径可行性探针」与 A1/A2 并行，尽早暴露不支持私有部署的问题，避免到最后才发现 Managed Feature Cliff。但只有 A4 基础事实/语义就绪后才能据此宣称平台 G6 通过。

## 3. 最小里程碑及停止条件

| Milestone | 必备任务 | 判定 | 触发后动作 |
|---|---|---|---|
| M0 SDK Ready | A00～A05 | 真实 MAF HarnessAgent 可运行并双轮流式返回 | 若公开 API/版本不可用，记录风险并修复基础兼容后继续 |
| M1 Runtime Fit | A06～A10 | Plan/Todo/Context/Loop/Policy 的原生 vs Adapter 差异明确 | Native 不支持则记录 Gap，不 fork Framework |
| M2 Workflow Fit | A11～A17 | Plan → Execute → Verify → Replan 完整，独立 Verify | 无法保住确定性最终状态 => MAF 不承担平台 Workflow |
| M3 Self-host Protocol | A18～A22 | Foundry-free 自托管、Typed Event、SSE、媒体/Artifact | G1/G3 不通过 => 不进入主架构 |
| M4 Task Recovery | A23～A30 | Task Facts + Waiting/Step Boundary/UNKNOWN 安全恢复 | G2/G6 不通过 => 不能作为独立完整 Harness 主架构 |
| M5 Durable Choice | A31～A35 | 私有化 Durable 可行性 + Same Attempt 真实性 | Durable 不达标 => MAF 作为 Runtime，交其他 Durable CP |
| M6 POC-A Closeout | A36～A39 | S01～S12、G1～G8、故障注入可追溯 | 形成与 Temporal/ADK 可公平对比的最终 ADR 候选 |

## 4. 统一场景覆盖索引

| 场景 | 主责任务 |
|---|---|
| S01 Streaming Chat | A05、A19、A21 |
| S02 Multimodal | A15、A17、A22 |
| S03 Plan | A06、A08、A11 |
| S04 Execute | A11、A12、A14 |
| S05 Verify | A12、A15 |
| S06 Replan | A08、A13 |
| S07 Task Recovery | A23～A30、A33～A34 |
| S08 HITL | A09、A26、A33 |
| S09 Provider Swap | A10 |
| S10 Sandbox Swap | A14 |
| S11 UI Protocol | A19～A21 |
| S12 Deployment Independence | A03、A18、A31～A32 |

## 5. POC-A 总 DoD

- A00～A39 全部有状态和链接到可重放的证据；不适用项目允许 `GAP / UNSUPPORTED`，但必须说明对最终架构的影响。
- G1/G2/G3/G6 各有独立可复测报告；如果任一失败，不能声称 MAF 单独承担主架构。
- G4/G5/G7/G8 均有结论、Adapter/替代方案及成本。
- S01～S12 全部有 PASS/FAIL/GAP；Coding 与 Document 使用统一输入/输出/协议契约。
- 必须区分 `native MAF session`、`MAF Workflow checkpoint`、`Durable Task orchestration state` 和平台的 `Run/RecoveryPoint`。
- 所有非 PURE 副作用故障必须有安全决策；UNKNOWN 不得直接 blind retry。
- 回答两项相互独立的问题：**MAF Runtime 可否使用？MAF Durable 能否用作 Control Plane？**
- 不将 Tenant/IAM、MCP Governance、Billing/Quota、APM 产品、基础设施 Backup/DR 纳入本轮平台建设。

## 6. 外部事实与验证入口

- [MAF HarnessAgent / Python public API](https://learn.microsoft.com/en-us/agent-framework/agents/harness)
- [Planning and Todos](https://learn.microsoft.com/en-us/agent-framework/agents/planning-and-todos)
- [Self-hosting](https://learn.microsoft.com/en-us/agent-framework/hosting/self-hosting)
- [Workflow Checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- [Durable Extension / Bring-your-own-compute](https://learn.microsoft.com/en-us/agent-framework/hosting/azure-functions)
- [Durable Functions MSSQL provider](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-storage-providers)
- [OpenTelemetry instrumentation](https://learn.microsoft.com/en-us/agent-framework/user-guide/observability)
