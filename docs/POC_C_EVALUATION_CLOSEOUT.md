# POC-C / Temporal + 可替换 Agent Runtime — 阶段评估收口

> 2026-10-09 | **EVALUATION CLOSED / CONDITIONAL** | **生产主架构 NO-GO**
>
> C00–C16 是已评估的证据集，不是生产 Accepted ADR；后续执行项统一登记在 [ARCH-TODO-025](ARCHITECTURE_BACKLOG.md)，不另建 POC-C 任务队列。

## 1. 决策

- **关闭 POC-C 技术评估**：C00–C16 已留下受限范围 PASS、失败注入及明确 GAP；保留历史结果，不因阶段收口将 scoped PASS 升级为完整 Gate PASS。
- **优先候选组合**：Harness 自有 Task Facts/Policy/Event + Temporal Durable Adapter + MAF/OpenAI Agents SDK Runtime Adapter。Temporal **尚未正式入选生产 Kernel**，仅作为可选长任务 Durable Adapter 的优先候选。
- **生产硬门禁**：G2 状态自主、G3 自有 Responses-compatible/Typed Event、G6 任务级恢复仍 **PARTIAL**，因此 **Production NO-GO**。G1 本地 OSS/PG 路径可行，不代表 TLS/HA/升级运维可用。
- **所有权边界**：平台拥有 Run/Plan/Step/Attempt/Execution/RecoveryPoint、审批、业务终态与 Artifact/Evidence metadata；Native ID 是 frozen binding。Temporal History/Checkpoint 仅透过 Opaque Reference 消费，不能复制到 Harness、自建 Temporal scheduler，也不建设企业 IAM、MCP Governance、APM、Sandbox/Storage 基础设施或 DB/OSS Backup/DR。
- **对照结论**：POC-A 的 A40 已真实证明 MAF Workflow 同样可以接入两个 Agent SDK；Runtime Swap 并非 Temporal 独占价值。POC-B 尚未因 C 收口而自动完成。

## 2. G1–G8 证据边界

| Gate | 已验证 | 当前结论及缺口 |
|---|---|---|
| **G1 自托管〔硬〕** | Temporal OSS + PG、独立 Harness PG、Worker/Server 重启、真实 Runtime、S3 | **本地 scoped PASS**；生产 TLS/HA/Worker rollout GAP |
| **G2 状态自主〔硬〕** | C07 Frozen Binding/UNKNOWN；C11 S3 metadata；C15 Server 已接受后 ACK 丢失的只读复核和持久 Opaque RecoveryPoint | **PARTIAL**；完整 Native Start 不确定窗口、多步恢复未证 |
| **G3 协议〔硬〕** | C15 本地真实模型→Responses Create/GET→PG Typed Token SSE、重连和 Cancel | **PARTIAL**；同一真实 Run 的 Tool/Approval/Artifact/UNKNOWN 完整事件未证；不声称官方 Responses 全量兼容 |
| G4 模型可替换 | C09 真 MAF / OpenAI Agents SDK Runtime Swap、同 LiteLLM 模型 | **PARTIAL**；第二实际 Model/Provider GAP |
| G5 Sandbox | C11 两种 Docker Adapter、真 S3 Artifact/Evidence | **PARTIAL**；CubeSandbox↔Docker SPI smoke GAP |
| **G6 任务恢复〔硬〕** | Worker/Server 故障、HITL、PURE Retry、UNKNOWN/Fencing；C15 Start ACK；C16 真非幂等工具副作用单次生效和 Receipt 反查 | **PARTIAL**；企业 Tool/MCP Receipt、独立业务 Verify/Decision、完整 Run 终态/新 Attempt 未证 |
| G7 HITL | 受控 Signal Approval/Reject 跨 Worker | **限定 PASS**；企业鉴权属外围 |
| G8 生产断层 | OSS 自托管、C13 原生 OTel/PG/Compose | **GAP**；生产版本升级、同负载性能与运维成本未量化 |

## 3. 可复核证据和限制

- [C14 同口径 A/C 对比](../poc/temporal/C14_COMPARATIVE_DECISION.md)：[PR #35](https://github.com/Bulls1986/Agent-Harness-Platform/pull/35) 合并、[Linux CI 5/5](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37780673019)；C14 不是生产 Accepted ADR。
- [C15 实际模型 Token SSE 和 Native Start ACK](../poc/temporal/C15_REAL_G3_PROTOCOL_FINDINGS.md)：企业 Gateway **本机真实模型实测**，HTTP 重启后可续播；[PR #38](https://github.com/Bulls1986/Agent-Harness-Platform/pull/38) 的 Linux CI 在真实 Temporal/PG/API/Worker 上验证，但模型使用**明确 Fake Tokens**，不能取代本机真实模型证据。ACK 注入为**已知 Server 接受后、平台 ACK 丢失**，无法断言所有网络超时。
- [C16 实际非幂等 Side Effect Receipt 对账](../poc/temporal/C16_RECEIPT_RECOVERY_FINDINGS.md)：独立受控 HTTP Tool / SQLite WAL 的外部业务 effect **仅 1 次**，Worker A 崩溃后 B 不盲重投；Receipt 查询使 Reconciliation PENDING→RESOLVED，历史 UNKNOWN 不改写，**Run 仍 RUNNING**，尚需独立业务 Verify/Decision。不是实际企业 MCP/ERP 回执或 Exactly Once 认证。
- C15/C16 的 [PR #38](https://github.com/Bulls1986/Agent-Harness-Platform/pull/38) 已合并主干，[CI #37793061991](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37793061991) **5/5 SUCCESS（限定覆盖范围）**。

## 4. 退出与移交

本次关闭的是**POC-C 的技术评估**，不是三条框架路线的全部首轮 POC DoD，也不是生产 Durable 内核选型。C00–C16 保留证据和历史缺口，停止继续以 C17/C18 扩大验证。唯一后续行动入口为 [ARCH-TODO-025](ARCHITECTURE_BACKLOG.md)，包含完整 G2/G3/G6、G4/G5 和生产成熟度审查。

生产 ADR 只有在 G1/G2/G3/G6 全部完整范围 PASS、其余风险和成本有明确决策后才能进入 Accepted；任一硬门禁未过必须保持 NO-GO。若 Temporal 额外 Service/DB/Worker 及确定性 Replay 运维负担超过收益，保留其为可选长任务 Durable Adapter 或拒绝默认内核地位。

**最终裁决：EVALUATION CLOSED / CONDITIONAL；Production NO-GO。**