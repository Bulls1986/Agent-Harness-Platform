# POC-A：Microsoft Agent Framework 完整任务计划

> 状态：执行计划（2026-10-08）  
> 目标：验证 MAF HarnessAgent + Workflow + Self-host + Durable Extension 在 Agent Harness Platform 中的适配位置。  
> 权威约束：[`docs/ARCHITECTURE.md`](ARCHITECTURE.md)、[`docs/POC.md`](POC.md)、根目录 `AGENTS.md` 和相关 Accepted Contracts。  
> **范围控制：不设计另一个 Agent Framework，不自建 Durable Task 后端，不把 IAM/MCP 治理/计费/存储 DR/APM 扩入 Harness。**

**阶段性结论与门禁证据统一台账**：[POC_A_STAGE_FINDINGS.md](POC_A_STAGE_FINDINGS.md)。实际运行 PASS 与最终架构 ADR 不能混同。

**2026-10-08 终局决策型收口**：见 [POC-A 最终评估与 NO-GO / Adapter 候选结论](../poc/maf/POC_A_DECISION_CLOSEOUT.md)。A34 完成不等于硬门禁全过；本报告将所有 A00–A39、G1–G8、S01–S12 定为 PASS/PARTIAL/GAP/DECIDED。MAF 可作为可替换 Runtime/Workflow/Durable Adapter 候选，但不单独充当 Harness Control Plane。

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
- A06/A07（新增）：`poc/maf/harness_capabilities.py` 运行真实 MAF Provider 装配、native Session 序列化及自定义 ContextProvider Hook 的无网络探针；未验证模型真正生成 Todo、Compaction 或跨进程恢复。
- A11（新增）：`poc/maf/workflow_probe.py` 通过真实 MAF WorkflowBuilder/Executor 验证平台 ID 沿图传播，且 terminal 成功必须有外部 Verification Fact + Evidence；完整 Plan/Execute/Verify/Replan 与持久化仍待实施。
- A12（新增局部验证）：`poc/maf/document_workflow.py` 通过真实 MAF Workflow 调用独立 Document Verifier；通过与故意失败用例形成正反断言。Sandbox、OSS Evidence、完整 Execute 实现仍待 A12/A14/A15 后续集成。
- A23（新增，**PARTIAL / 核心事实链路 CI PASS**）：PostgreSQL 已实测保存 Conversation/Turn/Run、版本化 Plan、Step/Attempt/Execution、Verification、Event、RuntimeBinding/RecoveryPoint 引用结构；真实 MAF Document Workflow 后经原子事务写入，4 项 PostgreSQL 集成测试 PASS，完整 Run 进程退出后通过独立 Python 进程读取成功。Approval、Artifact/Evidence 正式 Metadata、其他恢复关联字段及真实生产事务边界仍待补齐。CI 证据：[GitHub Actions #37717839849](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37717839849)。**不代表 G2/G6 已通过。**
- A24（部分实现）：通过 MAF 公共 `AgentSession.to_dict()/from_dict()` 与独立 Runtime Store 持久化原生 Session；Run Binding + Provider Fingerprint + 乐观 Revision 防旧写入。已在真实 PostgreSQL 测试中验证往返读写。**真实模型多轮 History 和 Compaction 未验证；不属于任务恢复 G6 的 PASS 证据。**
- A27（部分实现）：明确指定 interrupted Attempt 后，PURE/只读 Step 可从 Same Run + Same Step + New Attempt 恢复，旧 Attempt 最终结果不能提交；通过真实 MAF Document Workflow + PostgreSQL 实测。模拟 Worker 进程强制退出后，在独立进程中续跑的端到端测试已通过：[GitHub Actions #37718726040](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37718726040)。
- A28（部分实现）：NON_RETRYABLE 中断判为 UNKNOWN，生成 `poc_reconciliations(PENDING)` 且不创建新 Attempt；暂未真正调用外部副作用或实现人工 Reconciliation 收口。
- A25（**部分通过**）：固定版 MAF 原生 `FileCheckpointStorage` 在受保护的单机目录保存 3 个 Checkpoint，新 Python 进程恢复到末端并完成 Workflow，已完成 PrepareExecutor 未重复执行；未验证私有分布式 Backend/生产 Same Attempt 恢复。[CI #37719461420](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37719461420)。
- A26（**部分通过**）：PostgreSQL 平台 WAITING_APPROVAL + 审批信息/状态/拒绝持久化，3 项 DB 测试及进程外等待/审批 PASS；默认不创建 Execution，拒绝终止且不能篡改审批人、审批动作或决定。MAF 原生 request_info 与企业 IAM 仍未串接，G7 OPEN。[CI #37719461420](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37719461420)。
- A26（本轮追加，**PARTIAL**）：固定版 MAF 原生 Workflow `request_info` + `@response_handler` + FileCheckpointStorage 在跨 Python 进程中完成 APPROVED / REJECTED 两条路径；PostgreSQL 事务绑定原生 Request ID、Opaque Checkpoint ID 与平台 Approval/Run。审批前没有派发 Execution；拒绝不进入模拟敏感 Executor。**IAM/Policy 仍是可信 CI Fixture，生产 Durable Backend、实际 Tool Approval 和审批决策持久化后的崩溃窗口未验证**。[PR #9 最终 CI](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720102476)。
- A25（恢复点选择修正）：`FileCheckpointStorage.list_checkpoints` **无有序保证**。回归测试发现按 `checkpoints[-2]` 选点会偶发重跑 Prepare；已改用 MAF 公开 `previous_checkpoint_id` 血缘选择唯一末端及其前驱，连续 3 次跨进程恢复均未重跑 PrepareExecutor（`prepare_reexecuted=false`），不复制内部 Checkpoint 状态。
- A26（崩溃窗口增量）：在真实 MAF `request_info` + FileCheckpointStorage 与 PostgreSQL Approval 绑定上，进程 92 表示审批决定提交后但响应未投递，此时另一个进程可沿原 Request/Run 安全恢复；进程 93 表示响应投递意图后结果未知，必须 `UNKNOWN` 并禁止 blind replay。响应已 APPLIED 时重复恢复也不会重复执行模拟敏感动作。3 项 PostgreSQL 测试和进程故障注入已通过。[CI #37720639309](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720639309)。
- A29（部分通过）：遵循 ARCH-TODO-008，只针对平台自有 Execution 的 PostgreSQL Claim/Heartbeat/Dispatch Admission、Lease、Fencing Token；数据库级 4 项测试覆盖有效 Owner、过期 Owner 拒绝、PURE New Attempt 与非 PURE UNKNOWN/Reconciliation。**不是 MAF/Durable 内部 Worker Ownership，也没有完成 Cancel/Timeout 传播和真实副作用 Token 校验。**[CI #37720639309](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37720639309)。
- A29（Cancellation/Timeout 增量，**PARTIAL / DB CI PASS**）：`poc/maf/execution_control.py` 新增取消请求 `RUNNING→CANCELLING`、Adapter ACK 不等于 TERMINATED、等待审批无派发取消、取消后阻止新 Execution dispatch；非 PURE 已派发结果不确定时保留 UNKNOWN/Reconciliation。Timeout 未派发归 FAILED/TIMEOUT、已派发高风险归 UNKNOWN/TIMEOUT_AFTER_DISPATCH；PURE 已派发未确认终止不提前结束。6 项真实 PostgreSQL 合约测试通过。[CI #37721115581](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37721115581)。**未接入实际 Provider Cancel/Abort/Timeout。**
- A30（恢复覆盖矩阵，**PARTIAL / 文档证据收敛**）：[POC_A_RECOVERY_MATRIX.md](POC_A_RECOVERY_MATRIX.md) 按 Session、Step Boundary New Attempt、MAF File Checkpoint、HITL、Production Durable 分层，逐一列出验证条件与 OPEN/GAP，不把 Mock 或本地开发能力提升为 G6 PASS。
- A31（版本/后端矩阵已复核）：原生 DTS Emulator 与 Functions+MSSQL 路线已分离；Python AgentFunctionApp+Durable Functions MSSQL Storage Provider 已在完全本地 Docker 完成两轮跨 Worker HITL 恢复。生产 HA/支持/许可仍未验证，不推断整体生产 PASS。
- A32/A33（**开发 Emulator 子目标 PASS、生产目标 OPEN**）：官方 DTS Emulator（隔离 Compose 项目 `maf-dts-poc`、TaskHub `pocmaf`）上，真正启动 MAF `DurableAIAgentWorker.configure_workflow` 的无模型 Workflow。Worker A 进入 2 个原生 HITL 等待后被强制终止；Worker B 新进程恢复并分别 APPROVED/REJECTED。已完成 Prepare 没有重复，拒绝路径无受控动作。[真实 CI #37722178889](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37722178889)。**不提供生产 Private Backend、Same Attempt 平台映射或真实外部副作用 Exactly Once 证据**。
- A32/A33（**本地自托管 Functions+MSSQL 子目标 PASS，生产成熟度 OPEN**）：独立 Compose 在本地 Docker 启动 SQL Server 2022 Developer Edition、Azurite、Python Functions v4，固定 MAF Core 1.20.0 / AzureFunctions Extension 1.0.0b260922。真实 Host 日志确认 mssql Provider，SQL Server dt.Instances/dt.History 持续写入；两轮新的原生 HITL Workflow 在 Worker A 被强制 kill 后由 Worker B（新容器）恢复，APPROVED/REJECTED 均完成，Prepare 不重放；没有模拟 DTS。具体可重现代码、隔离范围、故障注入、历史失败保留及证据见 [本地 POC 手册](../poc/maf/functions-mssql/README.md)。**不代表正式生产 HA、许可、真实副作用一致性或完整 G1/G2/G6/G8。**
- A33 / A34 前置（**同机双 Worker 并发 PASS × 2，不代表 A34 完成**）：两个**同一应用镜像**的 Azure Functions Replica 同时连接新建的私有 DurableA34 MSSQL DB 与相同 TaskHub。A 先完成 Prepare 并等待原生 HITL，B 在 A 存活期间上线并读到相同原生 Instance/Request；SIGKILL A 后 B 不重启，APPROVED / REJECTED 均在 MSSQL Completed，每轮 History=42、Prepare replay=0、批准 Action=1、拒绝=0。复现见 [双 Worker 真实验证](../poc/maf/functions-mssql/A34_CONCURRENT_WORKERS.md)。**跨物理节点 HA、版本升级、真实副作用、Harness Same Attempt 恢复未验证，G1/G2/G6/G8 仍 OPEN。**
- A34（**WAITING_APPROVAL Same Attempt Identity LOCAL PASS / A34 整体 PARTIAL**）：通过 PostgreSQL 平台 Run/Step/Attempt/Approval 与官方 Azure Functions Native Instance/Request 持久绑定，Recovery Adapter 在原生 HITL 续投前核对 Run/Attempt 和 Frozen Workflow/Runtime Version，冻结版本不匹配应 fail-closed。保留原生 SQL Server History Ownership。**已在同一次本机 PG+MSSQL Worker 强杀测试实测**两原生实例 Completed、42 条 MSSQL History，PG 各 Run 仅一个 CREATED Attempt；冻结版本负例在平台 Adapter 被拒绝。[双数据库验收](../poc/maf/functions-mssql/A34_PLATFORM_MSSQL_E2E.md)。**WAITING_APPROVAL Attempt=CREATED；Running Attempt 途中 Same Attempt Resume、真实不兼容版本上线后的回放测试仍 OPEN，不能视为 A34 整体收口。**
- A34 RUNNING Executor（**本机 Native 故障观察 PASS / 平台恢复门禁仍 OPEN**）：新增完全隔离的 `DurableA34Running` MSSQL DB/TaskHub 和同镜像双 Worker。两轮全新 Native Instance 在 Executor handler 已开始、尚未 Completed 时 SIGKILL A，B 不重启、等待原生调度；每轮 Native Instance Completed / History=12，已完成 Prepare=1、**中断中的 Executor 入口标记=2**、完成标记=1。证实官方原生 Worker 会重新调用未确认的 Executor；不能宣称外部 SideEffect Exactly Once、RUNNING Same Attempt 身份或平台 UNKNOWN 联合验收。详见 [A34 RUNNING 故障证据](../poc/maf/functions-mssql/A34_RUNNING_EXECUTOR_CRASH.md)。G6/G8/A34 整体仍 OPEN。
- A34 MAF Executor/Tool Admission（**快速集成子目标**）：公开 MAF `WorkflowBuilder/Executor` 接入已有平台 PostgreSQL `ExecutionOwnership.dispatch`，门禁提交后才进入模拟 Tool Adapter。两次原生 Handler 调用对同一个 Execution 不产生第二次危险派发；结果不明则保留 UNKNOWN/Reconciliation 责任。独立 2/2 本地 MAF 单测 PASS，PostgreSQL 三组联动纳入 CI。详见 [A34 派发门禁](../poc/maf/A34_GUARDED_TOOL_DISPATCH.md)。不替代真实 MSSQL RUNNING Worker SIGKILL + PG 同故障链。
- A34 RUNNING Attempt 固定身份（**快速 SQL Schema 验证 PASS / 真实 Durable 联合恢复仍 OPEN**）：新建独立 PostgreSQL Immutable Execution → Run/Step/Attempt + Native Instance/Version Binding，唯一性、lineage、active state、latest Plan 及 frozen version 失配均 fail-closed；6 组数据库合约已纳入 CI。详见 [A34 RUNNING 身份](../poc/maf/A34_RUNNING_IDENTITY_BINDING.md)。不读取/改写 MSSQL TaskHub，更不声称跨数据库事务或 Same Attempt 续跑。
- A34 联合故障 P0（**单轮本机 Native MSSQL + PG + HTTP Tool Sink 真实 SIGKILL PASS**）：在官方 MAF Durable Worker A Native Executor 首次进入并通过 PG Fenced Admission 后，受控外部 Tool Sink 回执 1 次，B 在线时 SIGKILL A；原生重入第二次被 PG Admission 拒绝（HTTP 409），Tool Sink 仍 1 次；Native Instance `Failed` / MSSQL History 12，PG Immutable Native Binding、Attempt 仅 1、UNKNOWN/Reconciliation=PENDING。核心结论：可通过平台 Tool 出口阻断危险重放，但任务必须 fail-closed，不能保证真实工具 exactly-once。PG UNKNOWN 状态采用受控故障注入 SQL 更新，非本次直接调用 RecoveryCoordinator。见 [A34 单链实证](../poc/maf/functions-mssql/A34_GUARDED_NATIVE_PG_E2E.md)。版本混跑、跨数据库窗口仍 OPEN。
- A34 不兼容 Worker 实测（**工作流实现版本 P0 负例 PASS**）：真实不同摘要的 V1/V2 Azure Functions 应用镜像、同一 MSSQL TaskHub。A 旧版本执行中 SIGKILL，B 新版本原生接管旧 Instance 且 Handler 确实被调用；Harness Gateway 检查 PG Immutable Frozen Workflow Version 并返回 412，外部工具 0 次；Native `Failed`、PG 一个 Attempt `FAILED`。**关键发现：MAF 原生不能据此认定自动隔离不同版本 Worker**；工具边界必须强制执行冻结版本。此为应用实现版本差异而非 MAF SDK 二进制升级；Worker 版本身份必须可信，不能生产使用自报 Header。见 [A34 版本负例报告](../poc/maf/functions-mssql/A34_INCOMPATIBLE_WORKER.md)。剩余跨数据库断点 P1。
- A34 P1 跨数据库崩溃窗口（**本机真实 Native HTTP + PG 受控断点 PASS，专项 PG Adapter 合约纳入 CI**）：Native 启动前在 PG 留唯一 Launch Intent，创建成功却未保存 Binding 时不能盲目二次 /run，保持 Attempt/Execution UNKNOWN 和 PENDING Reconciliation；Native /respond 已投递但未收到 PG ACK 时只能读原生官方终态，Completed + Output Match 才确认 APPLIED，其他始终 UNKNOWN，不重投。同轮本机两个真实 Native Instance 和 MSSQL History 已取证，PG 转移由故障注入 Test Driver SQL 执行。详情 [跨库窗口报告](../poc/maf/A34_CROSS_DB_GAP_FINDINGS.md)。至此 **A34 约定 P0/P1 POC 范围内的技术实验全部具备结论**，G6/G8/生产 HA/真实企业 Tool 回执及网络半包 SIGKILL 仍不宣称通过。
- A31：已形成 [Durable 生产可行性报告](../poc/maf/DURABLE_FEASIBILITY.md)；Functions+MSSQL 已在本机跨 Worker HITL 实测，但生产门禁仍 OPEN。

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
