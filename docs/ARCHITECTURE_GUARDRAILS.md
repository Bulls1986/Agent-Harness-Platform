# Architecture Guardrails：架构原则、约束和开发准入

> **状态：既有 Accepted Contract 的实施护栏（2026-10-10），不是新 ADR。** 本文件将 [正式架构](ARCHITECTURE.md)、[Accepted Contracts](references/README.md) 与 [架构待办](ARCHITECTURE_BACKLOG.md) 转化为开发规范、PR 评审门禁和有限自动检查。
> **优先级：** Accepted ADR / 正式架构 → Accepted Contract → POC Contract → 当前 Backlog Decision → 本护栏 → 框架默认实现。选型候选不得自动升级为正式决策；POC LIMITED PASS 不等于生产 GO。

## 1. 等级与执行方式

- **H / Hard Invariant：** 已被 Accepted Contract 冻结，违反时拒绝合并。若确需改变，先修改 ADR 与 Contract，并说明兼容、迁移及回退。
- **R / Review Gate：** 需要 PR 提供边界归属、设计论证、运行或故障注入证据；没有足够证据时不能以绿色 CI 代替评审。
- **D / Decision Required：** 仍是候选或取舍未决，必须走 Backlog → 同口径 POC → Decision / ADR；不能靠 README、默认依赖或一条 POC PASS 偷偷定案。

自动化只能检查**能从仓库静态判定**的少量子集。Gxx 是完整的审查清单，不能宣称已经完全由 CI 机器证明。

## 2. 架构不变式

| ID | 等级 | 必须遵守的架构约束 | 违例示例 / 应提交的证据 | 权威来源 |
|---|---|---|---|---|
| G01 | H | **领域事实归平台。** Conversation → Turn（1:N Run）→ Run → versioned Plan → Step → Attempt；Retry/Resume/Replan 含义分离；terminal Run 不重开。 | SDK Session ID 当平台 run_id、Replan 覆盖历史 Plan。 | [Domain](references/DOMAIN_MODEL_AND_STATE_CONTRACT.md) |
| G02 | H | **Control/Data Plane 隔离。** Kernel 由确定性状态机决定审批、调度和 Run/Step 终态；Agent、Tool、Sandbox 只返回结果/事件/证据。 | Control Plane 直接执行宿主 Shell/Git；模型自行修改审批终态。 | [Control/Data](references/CONTROL_DATA_PLANE.md) |
| G03 | H | **领域/SPI 不依赖厂商 SDK。** Public API/Adapter 优先；不以 fork/monkey patch/SDK 私有 API 补成平台强制能力。 | Domain 导入 pydantic_ai、agents、opencode、Temporal；Adapter 替换迫使修改 Run 语义。 | [正式架构 2.1](ARCHITECTURE.md#21-公开扩展点优先原则) |
| G04 | H | **AgentRuntime、Process/Durable、SandboxProvider、ModelProvider 独立替换。** | 把 Temporal 当 Agent SDK；在 Pydantic 内部实现另一个 Runtime；把某个框架 Session 作为唯一任务事实。 | [分层架构](../README.md#31-八类分层架构视图) |
| G05 | H | **Session ≠ Run ≠ OS Process ≠ Workspace ≠ Sandbox。** 无 Shell/Files 需求允许零 Sandbox；不能强制每历史 Session 常驻独立进程/VM。 | 1 Session = 1 永久容器；无执行需求也申请 MicroVM。 | [Topology](references/RUNTIME_TOPOLOGY.md)、[Workspace](references/WORKSPACE_AND_GIT_MODEL.md) |
| G06 | H | **Sandbox 与 Tool 授权可信绑定。** Scope/Execution/Owner/Capability/Lease/Fencing 必须来自平台可信上下文；Sandbox ID 不是凭据；Coding 生产默认隔离。 | Scope 不匹配时回退 Host Shell；以 Session ID 授权 Git。 | [Identity](references/IDENTITY_AND_AUTHORIZATION_PROPAGATION.md)、[Lease](references/EXECUTION_LEASE_FENCING_HEARTBEAT.md) |
| G07 | H | **仅任务级恢复事实归平台。** 平台持久化 RecoveryPoint / Opaque Runtime Ref，不复制 SDK Checkpoint、不用 Sandbox Snapshot 代替业务状态、不搞跨组件 2PC。 | 依赖进程内 Session 才能恢复；要求所有 SDK 任意 Token 续跑。 | [Recovery](references/TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md) |
| G08 | H | **UNKNOWN → Reconciliation。** 非 PURE 执行声明 SideEffect/Receipt；旧 Fencing Epoch 不能提交；Cancel ACK 不是 TERMINATED。 | Git Push 超时无回执直接重试；Worker 失联后直接二次发信。 | [Failure](references/FAILURE_IDEMPOTENCY_AND_RECOVERY.md)、[Cancel](references/CANCELLATION_TIMEOUT_PROPAGATION.md) |
| G09 | H | **Run 创建时冻结准确版本。** Recipe/Runtime/SDK/Adapter/Tool/Policy/Model/Environment/OCI Digest 不可运行中静默漂移；Unsupported 明确拒绝。 | 运行到一半自动使用 latest；不支持能力悄悄 no-op。 | [Version](references/REGISTRY_AND_VERSIONING.md) |
| G10 | H | **Task Facts/Payload 分离。** PG 负责状态、Event、Binding、Lineage、Digest、Ref；大 Artifact/Evidence 在 OSS，Raw Trace 不替代事实。 | 长文件塞 PG 状态表；OTel Log 作为唯一恢复依据。 | [Retention](references/ARTIFACT_EVIDENCE_LOG_RETENTION.md)、[OTel](references/OBSERVABILITY_CONTRACT.md) |
| G11 | H | **身份/组织边界。** 企业内部单组织基线，不引入 SaaS Tenant 一等领域；Initiator 与 Executor 身份分离；敏感执行按实时权限重验，Token/Secret 不向 Guest/模型传播。 | 所有 Run 强制 tenant_id；把长期 SSO Token 注入 Prompt。 | [Identity](references/IDENTITY_AND_AUTHORIZATION_PROPAGATION.md) |
| G12 | H | **Harness 职责收敛。** IAM、MCP 准入治理、计费/额度、密钥平台、监控后端、镜像供应链、数据库/OSS 备份/DR 都由外部 Owner 持有。 | 在 Kernel 创建 MCP Trust Score、用户余额账本或系统备份平台。 | [Scope](references/HARNESS_SCOPE_ALIGNMENT_REVIEW.md)、[正式架构 2.2](ARCHITECTURE.md#22-harness-platform-职责边界) |
| G13 | H | **Runtime Topology 只是事实关系。** 记录 Participant 身份、生命周期、稳定 OWNS/SPAWNS/HANDOFF/ON 等，不代表 Workflow/Scheduler；高频 Tool 进 Event/Trace。 | 每个 Token 建拓扑节点；Topology 决定下一 Step。 | [Topology](references/RUNTIME_TOPOLOGY.md) |
| G14 | H | **Git/Workspace 单一权威。** Git Server 是主干权威，Run 冻结 Revision Set；并发可写 Worktree 默认隔离，Push/Merge 走 Policy。 | 共享可写 Worktree；执行中隐式 rebase；未授权 force push。 | [Workspace](references/WORKSPACE_AND_GIT_MODEL.md) |
| G15 | R | **真实可回放的协议。** SDK 事件转换成平台 Responses-compatible/Harness Typed Event；不伪造实时 Tool Activity/Token SSE；业务 Event 不受 OTel Sampling 影响。 | buffered 文本伪装 Token 级 streaming；SDK 私有事件直接驱动 UI。 | [Protocol](references/CONVERSATION_PROTOCOL.md)、[OTel](references/OBSERVABILITY_CONTRACT.md) |
| G16 | R | **跨 Agent 串联由平台编排。** Recipe/Step 依赖、受控结构化 Artifact/WorkspaceRef 交接、Verification/审批/失败阻断都由平台保障。 | 仅通过 Prompt 请下一个 Agent 继续；交接裸 Sandbox ID 和全历史。 | [PDLC 迁移](references/PDLC_REPLACEMENT_MIGRATION_20261010.md) |
| G17 | R | **存量 PDLC 迁移单 Writer。** 老历史/接口/资产可查，旧新执行端不双写副作用；影子比较只读或无副作用。 | 新旧端都执行同一 Tool/MR/Git Push；历史聊天被当成新平台已执行的 Run。 | [PDLC 迁移](references/PDLC_REPLACEMENT_MIGRATION_20261010.md) |
| G18 | R | **部署、数据、协议与模型独立性。** 关键 Harness 能力不强制依赖厂商托管 Control Plane；不无依据新增分布式锁、重型引擎。 | 为简单任务强制另一 SaaS 控制面；新增统一 Registry 或锁服务。 | [Deployment](references/DEPLOYMENT_INDEPENDENCE.md)、[Lease](references/EXECUTION_LEASE_FENCING_HEARTBEAT.md) |
| G19 | D | **候选不等于 Accepted。** Pydantic、OpenCode、OpenAI/MAF、Cube、PG Worker/Temporal/MAF Durable 均按专项 POC 证据决定角色，不因局部 PASS 自动生产 GO。 | 仅凭 Demo 就移除 Process SPI 或宣布生产选型完成。 | [候选](references/MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md)、[Backlog](ARCHITECTURE_BACKLOG.md) |
| G20 | R | **验收等级不可混淆。** Mock、Offline、Docker、Live、Production 逐项注明，必要时保留失败反例，禁止 skip 降门禁。 | 一个 FunctionTool 独立成功就声称跨 Runtime 全链恢复可用。 | [POC](POC.md)、[Admission](references/MULTI_HARNESS_ADMISSION_20261009.md) |

**解读：** G05 的「零 Sandbox」指允许并优先用于无需 Shell 的任务；不禁止有权限的业务 Agent 按需申请 Sandbox。G19 不将 Pydantic、Temporal 或 Cube 的候选角色冻结成不可修改的正式选型。

## 3. 依赖关系与禁止边

~~~text
既有 PDLC UI / Portal / Enterprise API
   ↓（Legacy Facade / Responses-compatible API）
平台 Domain / Harness Control / State Machine / Verification
   ↓（稳定 SPI + 可信 ExecutionContext）
AgentRuntime SPI      → 独立 SDK Adapters（Pydantic / OpenAI / OpenCode / MAF）
Process/Durable SPI   → PG Worker / Temporal / MAF Durable（候选）
SandboxProvider SPI   → Cube/其他 Provider → 外部 Sandbox Infra
Model/Tool/Storage SPI→ 企业 Model Gateway / MCP / OSS
   ↑
真实 Result / Evidence / Event 回到平台事实与验收边界
~~~

**禁止依赖边：** Domain → 厂商 SDK；Control → 宿主 Shell；SDK/Guest → 平台 Run 最终状态；Runtime Session ID → 授权；Runtime Topology → 调度；OTel/LLM 文本 → Task Facts。平台只约束自己 Kernel/Scheduler→Executor 之间的 Lease，不接管 Temporal/Cube/框架内部 Worker Coordination。

核心工程测试应证明：**更换 AgentRuntime/Process/Sandbox 任意一个 Adapter，不需修改平台 Run/Plan/Step 领域契约**。如果某实现缺公开扩展点，优先显式 Unsupported，不修改底层 SDK 私有实现。

## 4. 变更准入流程

1. **明确 Owner。** 判断变更是否属于 Harness 的任务/协议/Adapter/执行边界；属于旧 PDLC 业务、IAM、MCP 治理、Secret、存储运维的，定义 Reference/Adapter，不提升为 Harness Domain。
2. **列出受影响 Gxx。** 逐项检查 Domain、Protocol、AgentRuntime、Process、Sandbox、Tool、Data、Security、Deployment、PDLC Migration；使用当前 Accepted Contract，而不是根据便利性推断。
3. **决定处理路径。** 语义不变的 SDK Adapter/Recipe/Policy/POC → 正常 PR + 契约测试；影响领域、授权、事件、恢复、副作用、版本的 → 架构 Review；违反 Accepted 的 → 先 ADR/Contract 后实现；默认技术选型 → Backlog/等价 POC/Decision。
4. **提供可复验证据。** 至少成功+拒绝/故障路径；非幂等操作需 UNKNOWN/Receipt/Cancel/Lease 负例；新 Runtime 必须注明 Native/Adapter、Mock/Live、Unsupported、版本冻结。
5. **检查兼容与回滚。** 原 PDLC UI/历史/API/Agent 资产、单 Writer、已有 Run 的冻结版本、OSS 引用和证据保持可追溯；迁移前后不重复外部副作用。

### 立即拒绝（Hard Stop）示例

- Domain 添加 Provider Session ID 作为 Run 唯一业务键或多个 SDK 自行更新平台任务终态。
- OpenCode Host Shell 没有全部正确远程路由却宣称与 Cube 透明隔离；Scope/Lease 无校验直接执行。
- 模型文字充当审批/验证状态；非幂等 Tool 超时直接重试；旧 Worker 绕过 Fencing 更新结果。
- 一历史 Session 强制常驻一 Worker + Sandbox 作为默认容量模型。
- 在 Harness Kernel 新建 Tenant/项目 Story/MCP 市场/计费/Backup 领域产品。
- 默认强绑 Temporal/MAF Durable/PG Worker 或某模型厂商，却没有 ADR/对照验证。

## 5. PR 评审契约

[PR Template](../.github/PULL_REQUEST_TEMPLATE.md) 要求每个改动回答：影响哪些 Gxx、谁拥有新增数据与生命周期、是否修改 Run/Step/事件/Recovery/Approval/Receipt 语义、如何隔离 SDK/Tool/Sandbox、成功/拒绝/故障证据、现有 PDLC 迁移影响与回滚方案、真实 POC 状态。

**架构 Review 触发条件：** 新增或修改 Domain Model / State Transition / SPI 公共接口 / Event Schema / Policy / Execution Scope / SideEffect / RecoveryPoint / 版本冻结 / 生产拓扑 / 平台与企业系统边界。纯文档导航不变更语义时可以注明「无需 ADR」。当前不假造 CODEOWNERS 审批人。

## 6. 机械守护与运行条件

- 执行 python -B scripts/check_architecture_guardrails.py：检验 README 八类视图与 Mermaid 围栏，避免重复文档图；确认必需契约/检查表存在；检查现有 POC 平台 SPI 合同的静态 import 不绑定厂商 SDK/存储客户端。
- 执行 python -B -m unittest discover -s tests -p test_architecture_guardrails.py：至少包含守护脚本的反向测试。
- 执行 python -B poc/runtime_spi/verify_runtime_spi.py：复验零 Sandbox、错误 Scope/Fencing 的 Fail Closed、Cancel UNKNOWN 和事件序列。
- CI Workflow：.github/workflows/architecture-guard.yml 在 PR 和 main push 执行上述离线检查，不要求任何模型 Key、真实 Cube 或外部网络。

**检查边界：** 静态脚本无法证明动态导入、Runtime side effects、真实跨 Worker 隔离、SDK 注入和生产安全；必须依靠相应 Contract Tests、集成 POC 与架构 Review。未来 Domain/SPI 代码从 POC 迁往生产目录时，新增目录的同等规则应在迁移 PR 同时扩展。**仅添加 Workflow 并不自动让 GitHub 禁止合并**；需要仓库维护者在 Branch Protection / Ruleset 将 architecture-guard 设为 Required Check。

## 7. 维护规则

架构新争议只能登记在 [ARCHITECTURE_BACKLOG.md](ARCHITECTURE_BACKLOG.md)，不另外维护第二份 TODO。确需变更 Accepted 时先通过 ADR，更新正式 Contract、实现、兼容说明、负例测试和本规则；禁止通过跳过 CI、删断言、放宽验收、删失败证据来得到「架构收口」结论。