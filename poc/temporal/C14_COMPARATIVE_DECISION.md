# POC-C / C14 — POC-A vs POC-C 同口径候选对比

> 2026-10-08 | **C14 是评估收口，不是生产 Accepted ADR**。
> G1/G2/G3/G6 为正式硬门禁；局部 PASS 不能升级为主架构 PASS。
> POC-A 的基线来自 [POC-A 决策型评估](../maf/POC_A_DECISION_CLOSEOUT.md)，
> 不因 POC-C 的新证据而追溯修改历史结果。
> 实证与评估已由 [PR #35](https://github.com/Bulls1986/Agent-Harness-Platform/pull/35) 合并 main，
> [Linux CI #37780673019](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37780673019) **5/5 SUCCESS**；
> 这并不改变本文的 **生产主架构硬门禁 NO-GO**。

## 1. 分层架构判断

| 责任层 | 可行候选 | 结论 |
|---|---|---|
| Harness Task Facts / Policy / Event / Artifact Lineage | Harness-owned PostgreSQL | **平台掌握，保持框架无关** |
| Agent Runtime / Agent Loop | MAF HarnessAgent 与 OpenAI Agents SDK | **C09 两套 SDK 真实 LiteLLM 调用成功，Adapter 有效** |
| Durable Workflow / Activity/History | Temporal OSS；MAF Durable+Functions/MSSQL 为对照 | **Temporal 是下一阶段优先候选，不是本轮无条件生产选型** |
| Sandbox / Object Storage | CubeSandboxProvider 生产候选；Docker fallback；外部 OSS/S3 | C11 仅 Docker 两种模式+真实 S3 成功，不证明 Cube |

应分别回答 **Runtime Fit、Durable Control Plane Fit、
Harness Domain Ownership**；不可把 MAF Runtime 的真实模型
成功当作 MAF Durable 的主控制面所有权证明。

## 2. G1–G8：证据、状态、阻断

| Gate | POC-A MAF | POC-C Temporal + Runtime SPI | 裁决 |
|---|---|---|---|
| **G1 自托管〔硬〕** | PARTIAL：Functions+MSSQL、本地 HTTP 可用 | **本地 scoped PASS**：OSS Temporal+PG、独立 Harness PG、真实 Agent SDK 和 S3，无 Temporal Cloud；TLS/HA GAP | C 的 self-host 技术路径更完整，生产部署仍待验 |
| **G2 状态自主〔硬〕** | PARTIAL：Task Facts/Native Binding 有；真实 OSS Artifact 全链缺 | **PARTIAL**：C07 PG Task Facts、C11 真 S3/Lineage/Pin/Tombstone；RecoveryPoint/Checkpoint 和 Native Start ACK 未全测 | **硬门禁不能放行** |
| **G3 客户端协议〔硬〕** | PARTIAL：受限 Responses、4 类事件与 SSE，真 Token 流缺 | **PARTIAL**：C10 PG 只读 Response/2 类事件/SSE 游标，真实 Token、Create、Cancel 和全事件缺 | **硬门禁不能放行** |
| G4 模型替换 | GAP：一个真实 LiteLLM 模型 | **PARTIAL**：两种真实 Agent SDK Runtime 替换，但同一模型/网关，Provider Swap GAP | 需要第二模型实测 |
| G5 Sandbox SPI | GAP：Cube↔Docker 未测 | **PARTIAL**：两种 Docker Adapter 执行模式、真实 S3；Cube↔Docker 未验 | 第二个生产 Sandbox 不强制，但 Cube 基线仍需 smoke |
| **G6 任务恢复〔硬〕** | PARTIAL：真实 MSSQL Worker SIGKILL/HITL/PG UNKNOWN 门禁，真实 Receipt 缺 | **PARTIAL**：真 OSS Temporal Worker/Server 重启、HITL、PURE Retry、非幂等 UNKNOWN/Fencing、Replay；真实 Receipt/Native Start ACK/升级接管缺 | **硬门禁不能放行** |
| G7 HITL | PASS（受控原生 Approval/Reject） | PASS（受控 Signal/Approval/Reject） | 企业身份与授权属于外围 |
| G8 License/Managed Cliff | GAP：MAF/Functions/MSSQL 生产许可/支持未收口 | **技术自托管 PASS，生产 GAP**：OSS Server 不需 Temporal Cloud，升级/HA/许可证合规成本未量化 | 不按 OSS 能启动推导生产 SLA |

**硬结论：C 的 G1 本地自托管可行，但 G2/G3/G6 仍
PARTIAL；因此 C14 不得宣布“选中 Temporal 为正式主架构”。**
G4/G5/G8 有明确缺口，不自动扩成 Harness 自建外部产品。

## 3. S01–S12 同一场景基线

| 场景 | POC-A | POC-C |
|---|---|---|
| S01 Streaming Chat | 真 MAF+LiteLLM 双轮流式 PASS；Gateway GAP | 双 SDK 真模型 PASS，但 Token SSE/TTFT/取消 GAP |
| S02 Multimodal | GAP | GAP；Artifact 上传不是图像输入验收 |
| S03 Plan | PARTIAL；模型自主 Plan GAP | PARTIAL；固定 Document Plan v1/v2 |
| S04 Execute | 固定 Document，真实 Coding Sandbox GAP | C11 Docker 受控命令 PASS；repo 修改/真实 Coding GAP |
| S05 Verify | 独立固定 Document Verify PASS，OSS GAP | 固定 Document + C11 S3 Digest/Evidence PASS；真实 Coding Verify GAP |
| S06 Replan | 固定失败→Plan v2 PASS | 固定失败→Plan v2 PASS；自主 Replan 未验 |
| S07 Task Recovery | Worker/UNKNOWN 有限 PASS；完整 GAP | Worker/Server/UNKNOWN/Fence 有限 PASS；完整 Receipt GAP |
| S08 HITL | 原生 Approval/Reject 跨 Worker PASS | 原生 Signal Approval/Reject 跨 Worker PASS |
| S09 Provider Swap | 第二模型 GAP | SDK A↔B PASS，不等于第二模型，模型 Swap GAP |
| S10 Sandbox Swap | Cube↔Docker GAP | Docker 一次性/Session Adapter PASS；Cube↔Docker GAP |
| S11 UI Protocol | 4 类事件/游标续播 PARTIAL | 2 类事件/游标续播 PARTIAL，真实 Token/Artifact UI GAP |
| S12 Deployment Independence | 本地 Functions MSSQL PASS，生产 GAP | OSS Temporal+独立 PG PASS，生产 TLS/HA GAP |

不得由固定 Document/受控 Sandbox Fixture 的局部 PASS
推断完整 Coding/Multi-modal/Autonomous Plan 场景已通过。

## 4. 可靠性、可观测性、运维负担

- **POC-A / Durable**：真实 Azure Functions+MSSQL TaskHub
  跨 Worker、HITL、版本拒绝和 PG Fencing 可行；但支持等级/
  许可证、真实 Tool Receipt、SDK 稳定性、综合硬门禁未完。
- **POC-C / Native**：C05–C07 真 Temporal OSS/PG、Worker
  SIGKILL、PG Task Facts/UNKNOWN；C09 真双 Runtime；
  C10 限制协议；C11 真实 S3/Artifact；C12 原生 History Replay
  阻断不兼容 Workflow；C13 官方 OTel+Harness ID。
- C13 Compose 实测为 **3 个核心常驻服务**（Temporal Server、
  Temporal PostgreSQL、Harness PostgreSQL），**2 个初始化 Job**，
  Artifact/Evidence 可选 **1 个 S3**；另需 Worker/API 进程。
  这些是单机 POC 组件数量，不是 K8s/HA 或人力成本。
- **没有同负载的 A/C TTFT、P95、CPU、Memory、吞吐、
  升级成本和运维工时对比**，因此不制造数值打分、成本倍数
  或任何虚构的选型优劣排序。
- Temporal 的 Workflow 确定性、Replay/Worker Versioning、DB
  运维属于实在约束；MAF Functions+MSSQL 的部署/许可/支持
  也应进入下一阶段真实成本门禁。
- Harness 的业务 Event/Task Facts 与 OTel 诊断严格分层；
  Trace 丢失不能改变 Run/Attempt 状态。

## 5. 决策与退出条件

**优先验证的组合：自有 Harness Kernel/Task Facts +
Temporal Durable Adapter + MAF/OpenAI Agents Runtime Adapter。**
不是 Accepted Production ADR，也不替代独立的 Agent Harness
Control Plane 设计。

要真正通过主架构门禁，最小剩余验证：

1. **G3**：同一个真实模型任务走自托管 API，完整受限范围的
   Responses Create/GET、真实 Token SSE、Plan/Tool/Verify/
   Artifact/Approval/UNKNOWN Typed Event、Cancel、断线续播；
   不支持的能力明示 UNSUPPORTED，不伪装兼容。
2. **G2/G6**：Native Start ACK 丢失/平台绑定不确定窗口、
   Worker 崩溃后的 RecoveryPoint 边界、真实非幂等 Tool Receipt
   对账、UNKNOWN 不盲重试。PASS 或可核验的安全 fail-closed；
   不要求底层 PostgreSQL/OSS/磁盘区域容灾。
3. **G4/G5**：第二个真实模型 Provider 调用、CubeSandbox↔Docker
   最小 SPI smoke；无法执行则记录业务影响和替代成本。
4. **部署成熟度**：Temporal 生产 TLS、版本发布/回滚策略、
   OSS/DB 依赖运维，以及同负载 A/C 延迟与资源开销对比；
   不扩为自建 APM、OSS、MCP Governance 或 Sandbox Platform。

**本阶段 C14 可以作为证据驱动对比收口；如果以上硬门禁
继续 GAP，则默认 Durable 内核生产选型仍为 NO-GO。**
Temporal 可先作为长任务 Durable Adapter 的优先 POC 候选，
MAF 作为独立 Runtime Adapter 继续使用。

## 证据导航

- [POC-A 决策型最终评估](../maf/POC_A_DECISION_CLOSEOUT.md)
- [C05 真 OSS Temporal/PG](C05_OSS_POSTGRES_FINDINGS.md)
- [C06/C07 UNKNOWN Fencing](C06_C07_GUARDED_FINDINGS.md)
- [C09 双 SDK 真实 LiteLLM](C09_REAL_RUNTIME_FINDINGS.md)
- [C10 限定 Responses/SSE](C10_PROTOCOL_FINDINGS.md)
- [C11 真 Sandbox/S3 Artifact](C11_SANDBOX_ARTIFACT_FINDINGS.md)
- [C12 Native Replay](C12_REPLAY_FINDINGS.md)
- [C13 Native OTel](C13_OTEL_FINDINGS.md)
