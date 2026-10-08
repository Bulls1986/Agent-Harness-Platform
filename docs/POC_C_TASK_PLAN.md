# POC-C / Temporal + 可替换 Agent Runtime — 任务计划与验收

> 2026-10-08 | 首轮框架评估第二优先 | 正式编号 **POC-C**
>
> 权威基线：docs/POC.md §9、G1–G8 / S01–S12、
> docs/references/DOMAIN_MODEL_AND_STATE_CONTRACT.md、
> FAILURE_IDEMPOTENCY_AND_RECOVERY.md、
> TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md。
> POC-A 已决策关闭；沿用同一 Document 负例/独立 Verifier 和平台 ID。
> **不因 Temporal SDK、Dev Server 的能力调整平台 Domain。**

## 责任边界（首轮冻结）

- Harness Domain：Conversation/Turn/Run/Plan/Step/Attempt/Execution、
  Approval、SideEffect 分类、Artifact/Evidence 引用、Event 与 UI Protocol。
- Temporal：持久化**确定性** Workflow 调度状态/History、Activity
  Scheduling/Retry、Signal/Update、Task Queue/Worker 分配。
  Native Workflow ID 只作为 RuntimeBinding，不冒充 Run ID。
- Agent Runtime Activity：通过 SPI 调用 MAF、OpenAI-compatible 等
  Runtime，执行非确定性模型 / 外部 Tool / Sandbox；不进入 Workflow
  Replay 逻辑，也不继承 Tempo 的应用领域所有权。
- 数据：平台 Task Facts 放 PostgreSQL；Temporal History 留 Temporal
  Backend；Artifact/Evidence Payload 留独立 OSS/S3。**不复制
  Temporal Workflow History 到 Harness，也不自建 lease/fencing scheduler**。
- 内部企业系统**不引入多租户领域模型**；按 Task Queue 对 Runtime/
  执行等级隔离，而非构建 SaaS Tenant Management。

## POC-C 分组与最小任务（先验正确性，再测故障）

| ID | 优先级 | 最小任务 / 通过标准 | 状态 |
|---|---|---|---|
| C00 | P0 | 冻结一致的 G1–G8、S01–S12 基线与 Document fixtures；Runtime/Native IDs 分层 | PASS (scoped local) |
| C01 | P0 | 官方 Temporal SDK 通过公开 API；自托管 Service 启动并保存 History | **PASS dev-server**，生产 self-host GAP |
| C02 | P0 | Temporal Workflow 只执行确定性编排；Agent A/B 和 Verify 由独立 Activity 实施；Verifier 失败才能 Replan | PASS (fixture) |
| C03 | P0 | 真实 Worker A SIGKILL，B 进程接续同一 Native Instance、审批 Signal 仍可交付、无旧 Attempt 覆写 | PASS (dev-server) |
| C04 | P0 | 真 Temporal **Server** stop/start，状态从独立持久卷恢复，同 Native Workflow/History 继续 | PASS (dev SQLite) |
| C05 | P0 | OSS Temporal Server + 独立 PostgreSQL（非 `start-dev`）复用 C02–C04 Worker/Server 故障实验 | **PASS（本地 OSS+PG）**，整体 G1/G6 仍 PARTIAL |
| C06 | P0 | PURE Activity 重试与 NON_RETRYABLE 工具派发后的崩溃隔离 | **PASS（本地+CI 双 PG）**；真实外部 Receipt GAP |
| C07 | P0 | 原生 Workflow ↔ 独立 Harness PostgreSQL Run/Step/Attempt/Execution + Frozen Binding/UNKNOWN Reconciliation | **PASS（本地+CI 双 PG）**；整体 G2/G6 仍 OPEN |
| C08 | P0 | 审批 WAITING Signal 与 REJECTED/APPROVED 均按固定 Platform Decision 继续，不合并新旧 Attempt | PASS bounded / 企业授权非范围 |
| C09 | P1 | **真实**替换两个 Agent Runtime Adapter 但平台 Run/Workflow/Events 不变；最好复用内网 LiteLLM | OPEN；固定 fixture A/B 不等于真实 Runtime Swap |
| C10 | P0 | 平台 Responses-compatible + Typed SSE/Replay Bridge，不暴露 Temporal Payload/History 作为领域事实 | **本机 PASS（受限只读桥接），CI 待核对；总体 G3 PARTIAL** |
| C11 | P1 | 可替换 SandboxProvider + OSS Artifact/Evidence 元数据/引用薄 Adapter，禁止在 Temporal History 存大 Payload | OPEN / G2/G5 |
| C12 | P0 | Worker 不兼容版本/Workflow Replay/升级负例，旧 Workflow 不得在不兼容 Activity 上产生副作用 | OPEN |
| C13 | P1 | Native OpenTelemetry / Task correlation；最小配置和依赖/运维成本计数 | OPEN |
| C14 | P0 | G1–G8/S01–S12/A vs C 比较矩阵，失败类型和退出条件逐项决策，最终 ADR 前不得冒充主架构 PASS | OPEN |

## 第一批 C00–C04 本地证据

- SDK `temporalio==1.34.0`；本地服务镜像固定 digest
  `sha256:ad4c82c97bd12b417d1ea942610dbcd511afb250c4d5ed26c694009533df447e`，
  其中 Temporal Server 显示 1.32.0。Docker named volume 存
  `/data/temporal.db`。固定版本不是生产 license/upgrade 支持保证。
- `verify_local_handoff.py`：真实 1 次 Worker A kill，
  Worker B 在同一 Queue 接续；同 Native Workflow 的 v1 Verified
  FAIL，Signal APPROVED 后 v2 PASS；4 个 Activity Completed、
  33 个 Native History Events；另一路 REJECTED 在 v1 结束。
- `verify_server_restart.py`：真停止并启动隔离 Server 容器，
  同一持久 SQLite 卷 + 新 Worker 继续，History 仍 33，
  4 次 Activity Completed，2 个 Plan/Attempt 不改变。
- Two fixture adapters are allowlisted only; **不是真实 Agent Provider Swap**。
  此时仅证明 Temporal 原生机制，而**不证明生产 Server、
  外部工具防重/Exactly Once、OSS/Sandbox、Responses Protocol G3**。

## 下一批退出条件（不扩为生产服务建设）

1. C05 已有 [Temporal OSS Server+PostgreSQL 真实实证](../poc/temporal/C05_OSS_POSTGRES_FINDINGS.md)：同一 Workflow 通过 Worker/Server 重启，SQL History 在 Server 关闭期间仍保留。生产 TLS/HA 未因此验收。
2. C06+C07 的 [真实 Temporal Activity 重试 + 独立 Harness PG 门禁](../poc/temporal/C06_C07_GUARDED_FINDINGS.md) 已完成本机验证：PURE 自动重试、非幂等派发后真实 Worker 退出、恢复拒绝重复、原 Attempt/Execution UNKNOWN + Pending 对账；真实企业 Tool Receipt 不在本轮通过范围。
3. C10 [受限只读 Responses/Typed SSE 真实链路](../poc/temporal/C10_PROTOCOL_FINDINGS.md)：读取 Harness PG、UNKNOWN 不误报完成、HTTP 进程重启后 `Last-Event-ID` 续播。完整 Responses/模型 Token SSE/Tool/Approval/Artifact 事件仍 GAP。
4. C12：Native Workflow 代码升级/Replay API 负例，避免“架构能跑”
   掩盖 nondeterminism 与 Activity side effect 事故。
5. 最终比较时记录真实部署依赖、SDK/Worker 特殊代码规模、配置、
   模型 TTFT/Artifact 大小边界，而不是只按 Happy Path 打分。

**评估退出规则（原 POC.md §9.5）：** 如果 Temporal Service
与 Worker 系统的组合/运维负担明显大于长任务故障安全收益，
或 Workflow 确定性/Replay 约束无法持续维护，则不选 Temporal
作为默认 Harness Kernel；可以保留为长任务 Durable Adapter。
