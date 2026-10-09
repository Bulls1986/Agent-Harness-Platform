# POC-A / Microsoft Agent Framework — 决策型收口

> 2026-10-08 | **评估状态：CLOSED / 单独作为 Harness 主架构：NO-GO**
>
> 此文件是评估结论，不是生产 Accepted ADR。A34 本地 P0/P1 实验已完成；原有 G1/G2/G3/G6 四项硬门禁尚未全部通过，故不得宣布 MAF 独立构成企业 Harness 主架构。局部 PASS 均只针对所述场景。

## 1. 三个独立选型结论

| 对象 | 结论 | 关键依据 |
|---|---|---|
| MAF HarnessAgent / Agent Runtime | **CONDITIONAL YES — 可替换 Adapter 候选** | MAF 公开 Context/Session 扩展点通过；真实内网 LiteLLM 两轮流式、上下文回忆通过。必须明确客户端历史 store=False；模型自主 Plan 与 Compaction 仍未验 |
| MAF Workflow / Executor | **YES — 有限确定性编排；NO — 平台 Control Plane 所有权** | Native Workflow + 独立 Verifier、Plan v1 失败→Plan v2 成功、PostgreSQL 持久身份/事件/终态通过；Run/Plan/Step/Attempt/Policy/Verify/Replan 仍归 Harness |
| MAF Durable / Azure Functions MSSQL | **LOCAL FEASIBILITY PASS / PRODUCTION CONDITIONAL** | 真 MSSQL TaskHub、HITL、Worker SIGKILL、RUNNING reentry、PG 派发门禁、版本拒绝及跨库故障窗口通过；生产许可证/支持/HA/企业外部 Tool Receipt 尚未核实 |

**决策：不以 MAF 替代厂商无关 Harness Control Plane。**
允许在稳定 SPI 后用 MAF 承载 Runtime/Workflow/Durable Adapter。
不要 fork MAF、复制 TaskHub/Scheduler，不把 MCP 治理、IAM、Sandbox
底层和磁盘备份转成此平台的开发任务。独立的 Durable CP 生产候选
继续同 Temporal/其他既有引擎公平比较。

## 2. Gate G1–G8

| Gate | 判定 | 验证范围 / 留存 GAP |
|---|---|---|
| **G1 自托管（硬）** | **PARTIAL** | 无 Foundry 的本地 Functions+MSSQL 与 loopback Uvicorn+MAF+PG+重启可用；完整模型驱动自托管协议未验 |
| **G2 状态自主（硬）** | **PARTIAL/GAP** | PG Task Facts/Approval/Event/Native Bindings；OSS Artifact/Evidence Metadata/Lineage/Digest/Payload 完整链路未验 |
| **G3 协议桥接（硬）** | **PARTIAL/GAP** | 固定 Document 的 Responses-shaped 快照、四种 Typed Event、SSE seq 续播/跨 HTTP 进程重启；真实模型 token SSE、Tool/Artifact/Approval、多模态及完整 Response items 未验 |
| **G4 模型可替换** | **GAP** | LiteLLM 列出 14 种模型；只有 qwen3.8-flash 实际双轮验证，第二模型真实调用无验收结果 |
| **G5 Sandbox 可替换** | **GAP** | CubeSandbox↔Docker Adapter 未做实际 Smoke；Document Fixture 不执行 Shell |
| **G6 任务级恢复（硬）** | **PARTIAL/GAP** | PG Step Recovery，真实 Durable 双 Worker/HITL/RUNNING/UNKNOWN 门禁和跨库窗口通过；真实 Workspace、Sandbox、Tool Receipt 自动对账未覆盖 |
| **G7 HITL** | **PASS（有限技术验证）/ ENTERPRISE GAP** | 官方 native HITL 批准/拒绝跨 Worker，PG 身份与版本；企业 IAM/Policy 未串接，属于外围 |
| **G8 许可证/Managed Cliff** | **GAP** | Emulator 与自托管 MSSQL 的区别清楚，开发版 MSSQL+MAF prerelease 可运行；正式生产许可/微软支持/HA/SLA 未确认 |

**G1/G2/G3/G6 不能统一标 PASS；因此本候选未通过作为独立主架构的硬门禁。**

## 3. Scenario S01–S12

| 场景 | 判定 | 证据 / 限制 |
|---|---|---|
| S01 Streaming Chat | **PASS（真实 MAF+LiteLLM 两轮）/ UI GAP** | stream=True 两轮文本，store=False 客户端 History 后准确回忆；自托管网关未转发模型 Token |
| S02 Multimodal | GAP | 文本+图像+文件+OSS 未验证 |
| S03 Plan | PARTIAL | Native Todo/Mode Hook 与平台 Plan v1/v2 事实；模型自主 Plan 未验 |
| S04 Execute | GAP | Document Native Executor 通过，但真实 Coding/Sandbox 未验 |
| S05 Verify | PASS（固定样例）/ OSS GAP | 独立 Verifier 识别好坏文档，Evidence 仍是本地 Fixture Ref |
| S06 Replan | PASS（确定性样例） | 同一 Run，MAF v1 Verify 失败→PG 原子新 Plan/Attempt→MAF v2 Verify 成功 |
| S07 Task Recovery | PASS（有限场景）/ FULL GAP | Worker kill、HITL、PG Safe Retry/UNKNOWN，未测 Workspace/真实 Receipt |
| S08 HITL | PASS（有限场景） | 原生 HITL + 审批持久化，IAM 仍是 fixture |
| S09 Provider Swap | GAP | 可列多模型但第二模型未实际验收 |
| S10 Sandbox Swap | GAP | 未做 CubeSandbox→Docker |
| S11 UI Protocol | PARTIAL/GAP | 四类事件、SSE cursor/reconnect、HTTP 进程重启，缺完整协议事件和 live token |
| S12 Deployment Independence | PASS（本地）/ PRODUCTION GAP | 官方 Functions MSSQL + 无 Foundry 的本地 HTTP 服务，未测正式跨节点生产 |

## 4. A00–A39 任务状态归档

| ID | 状态 | 边界 |
|---|---|---|
| A00 | PASS offline | MAF 安装/基本 Smoke |
| A01 | PARTIAL | SDK 固定/API Probe，升级兼容尚缺 |
| A02 | PASS fixture | Coding/Document 样例与验收 |
| A03 | PARTIAL | PG/OTLP/镜像通过，OSS 接入缺 |
| A04 | PASS | Gate/Evidence 模板 |
| A05 | PASS live | LiteLLM MAF 两轮流式且 Client History 回忆 |
| A06 | PARTIAL | Native Todo/Mode Provider，模型规划缺 |
| A07 | PARTIAL | Context/Session Hook，Compaction 缺 |
| A08 | GAP | max iterations/replans/runtime 限制独立实验缺 |
| A09 | PARTIAL | HITL/Tool Admission 边界，真实 Model Tool Approval 缺 |
| A10 | GAP | 第二模型真实 Provider Swap 缺 |
| A11 | PASS bounded | WorkflowBuilder/Executor/平台 ID |
| A12 | PASS fixture/GAP | Document Verify，Coding Sandbox 缺 |
| A13 | PASS bounded | Failure→Plan v2 确定性 Replan |
| A14 | GAP | CubeSandbox SPI 验证缺 |
| A15 | GAP | OSS Artifact/Evidence 真实链路缺 |
| A16 | PARTIAL | Fenced Tool HTTP Fixture，实际企业 MCP Receipt 缺 |
| A17 | PARTIAL | 完整 Document Replan；Coding E2E 缺 |
| A18 | PASS restricted | 自托管 loopback HTTP 与进程重启 |
| A19 | PARTIAL | Responses-shaped 受限子集 |
| A20 | PARTIAL | run.started、verification.failed、plan.replanned、run.terminal |
| A21 | PARTIAL | PG 事件 seq/SSE 按游标重读；真实 Token SSE 与 Cancel 缺 |
| A22 | GAP | Multimodal/OSS 未验 |
| A23 | PARTIAL | Task Facts 原子性/PG，Artifact Metadata 缺 |
| A24 | PARTIAL | Native Session 跨进程，真实 History Compaction 缺 |
| A25 | PASS local | 原生 File Checkpoint 血缘恢复 |
| A26 | PASS bounded | 原生 HITL/PG 决策关联 |
| A27 | PASS bounded | PURE Step 新 Attempt 跨进程恢复 |
| A28 | PASS safe-fail | 非幂等 UNKNOWN/PENDING，真实对账缺 |
| A29 | PARTIAL | PG Claim/Fencing/Cancel 合约，真实 Provider Cancel 缺 |
| A30 | PASS matrix | 恢复证据和 GAP 分类 |
| A31 | PASS matrix | Durable Emulator/Functions/MSSQL 可行性 |
| A32 | PASS local | 本地私有 Functions MSSQL |
| A33 | PASS local | 同 TaskHub 双 Worker 接管 |
| A34 | PASS scoped P0/P1 | 故障安全、版本门禁、跨数据库对账 |
| A35 | DECIDED candidate | 本文件独立 Runtime/Workflow/Durable 决策 |
| A36 | GAP | 真实原生 OTel/平台 correlation 端到端缺 |
| A37 | PARTIAL | Worker/Approval/UNKNOWN/Gaps；Model/Sandbox/UI crash 全矩阵缺 |
| A38 | GAP | 模型与 Sandbox 真实替换/TTFT/生产许可对比缺 |
| A39 | CLOSED evaluation | 本文件以 GAP/NO-GO 封存；不是生产 Accepted ADR |

## 5. 实际证据与复现

- **A05**：poc/maf/litellm_live_probe.py，内网 LiteLLM/OpenAI-compatible
  qwen3.8-flash 真实双轮 stream 文本且第二轮回忆成功。最初默认
  server-side History 时回忆失败；设 MAF public default_options
  的 store=False 改用客户端历史后通过。模型 Key/内网地址不落仓库。
- **A11–A17**：poc/maf/bounded_replan.py 和 test_bounded_replan_pg.py。
  一个 PG Run、两个 Plan/Attempt、四条不可变 typed events。
- **A18–A21**：poc/maf/protocol_service.py、
  test_protocol_service_pg.py、verify_selfhost_protocol.py。
  实际 HTTP POST/GET + SSE，独立进程重启后恢复同一 Run。
- **A23–A34**：docs/POC_A_STAGE_FINDINGS.md、
  docs/POC_A_RECOVERY_MATRIX.md、
  poc/maf/A34_STAGE_ARCHITECTURE_REVIEW.md；
  最后 A34 真实 PostgreSQL CI #37755452466。
- 所有实证均按原生 Runtime 状态与平台 Run/Attempt/Effect 分层；
  文档固定样例不等于 LLM 规划或真实 Coding Sandbox。

## 6. 退出决策

1. **A34 CLOSED，POC-A 候选评估 CLOSED，但硬门禁未全过（NO-GO 作为完整主 Harness）。**
2. MAF 可通过 Adapter 继续用于 Runtime/Workflow/Durable，
   平台 Control Plane 仍独立；不复制框架调度器或扩大外围职责。
3. 真实 OSS/Sandbox/UI Protocol/Provider Swap/License/OTel 缺口保留
   为后续独立工程/架构门禁，不追溯伪造当前 PASS。
4. 后续 Temporal/ADK 候选应按完全相同 G1–G8/S01–S12 门禁对比；
   若新证据出现，建立新的 ADR 评审，不修改本次历史结论。

**这是一个可封存的架构评估结论，不是生产系统已交付。**
## 2026-10-09 后续验收增量（不改写 2026-10-08 历史决策）

基于后续实施，G3 **真实内网 LiteLLM → 官方 MAF SDK → 平台 PostgreSQL Typed Event → HTTP Token SSE → 独立进程重启 → Last-Event-ID 精确回放**已在本机通过：4 个真实 Delta、6 条持久事件、随机验证码核验、第二 HTTP 进程无需模型密钥即可读取历史，验收脚本退出 0。详见 [G3 真实模型增量](G3_LIVE_PROTOCOL_FINDINGS.md)。

G2/G6 后续在受控范围还新增了 [真实 MAF Durable Worker SIGKILL + 平台 RecoveryCoordinator + 非幂等外部回执同链](G6_NATIVE_RECEIPT_SINGLE_CHAIN_FINDINGS.md)，以及 [真实 MAF FileCheckpointStorage/PG RecoveryPoint](G2_G6_RECOVERY_POINT_FINDINGS.md)、[独立 OSS Workspace 单文件恢复](G2_G6_OSS_FINDINGS.md)。

这些增量缩小了原来 Gate 中的技术 GAP，**没有**证明完整 Responses Tool/Approval/Artifact 协议、真实企业 MCP/业务系统副作用对账、正式生产 MSSQL HA/许可或所有 Coding Sandbox/Provider Swap Gate，故 2026-10-08 封存的「MAF 不单独担任 Harness Control Plane」结论**保持不变**。不得将多个局部 PASS 合并宣称整套生产 Gate PASS。

