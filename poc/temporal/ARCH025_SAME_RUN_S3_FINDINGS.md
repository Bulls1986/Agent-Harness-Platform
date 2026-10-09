# ARCH-TODO-025 / G3 同一 Native Run — Token SSE → S3 Artifact → Verify

> 2026-10-09 | **本地真实 OSS Temporal + Harness PostgreSQL + SeaweedFS S3 scoped PASS**；
> 完整 G2/G3/G6 Gate 仍 **PARTIAL / Production NO-GO**。
>
> 此次所有 Token/Artifact/Verify/UNKNOWN 事件都来自**同一个冻结 Run/Workflow**；
> **模型阶段使用明确 Fake Tokens**，不冒充本轮再次完成真实模型验证；
> 真正企业 MCP Tool、Approval、真实完整业务恢复仍未覆盖。

## 证明链与边界

- 自托管 `POST /v1/responses` 的新 POC 可选参数 `save_artifact:true` 在 PG 的 immutable `run.started` 事件上冻结选择；默认 false 与 C15 既有流程兼容。
- 为保存 S3 Artifact 的 Run 将 Execution 的 SideEffectClass 标为 **IDEMPOTENT**（确定性的 OSS object key），不是错误标记为 PURE。由于当前非 PURE Cancel/Receipt 语义尚未全面验证，Cancel 安全返回 409、不伪装 `CANCELLED`。
- 官方 Temporal Workflow 的 Data Plane Activity 从**同一 Run 已持久化的 Token Delta** 重建输出，按 SHA-256 检验后向复用的 `S3PayloadStore` 真实写入。仅传摘要/opaque S3 ref/Artifact ID 到 Native History；不传模型回答正文。
- Harness PG 仅写 Artifact 的 ID、原 Run/Step/Attempt/Execution 血缘、`s3://` 引用、digest 与 size 到不可改写 `artifact.created` 事件；另一个独立 Activity **重新读取实际 S3 字节** 核对 SHA256/size/ref 才写 `artifact.verified`；独立业务 `verification.passed` 和 `run.terminal COMPLETED` 必须等待以上 proof。
- `GET /v1/responses/{run_id}/events` 与 `GET /v1/runs/{run_id}/events` 走既有统一持久 Typed Event SSE，HTTP 进程重启、Last-Event-ID 游标续播一致；原 Native History 不含完整模型回答。

## 本地正负验收

- 源码 `compileall` 和 Git diff check PASS。
- 全新隔离 PostgreSQL 16（随机临时凭据）、实际 OSS Temporal Server + 独立 Worker、真实 SeaweedFS S3，PG 合约 **10/10 PASS**：Frozen save_artifact、纯模型旧路径兼容、ID/Ref/Digest 不匹配、重复 Artifact idempotence、缺独立验证禁止完成、非 PURE Cancel fail-closed、UNKNOWN 历史不可覆盖。
- `POC_C15_TEST_ARTIFACT=1` 成功路径：一个实际 Native Workflow/Run 完成 Token SSE → `artifact.created` → `artifact.verified` → `verification.passed` → `run.terminal`；S3 对象字节精确等于 SSE 重建文本、SHA 一致，终态 `COMPLETED`；独立 API HTTP 重启/游标重播 PASS。模型 Token 明确为 CI Fake。
- `POC_C15_INJECT_S3_WRITE_UNKNOWN=1`：**真实物理 S3 PUT 已成功**，在将 Artifact metadata 写 PG 之前模拟 ACK 丢失；该 Run 的 immutable Attempt/Execution 进入 `UNKNOWN`、`poc_reconciliations=PENDING`，平台 Run 仍 `RUNNING` 且 `attention_required=true`，SSE 中保留 `execution.unknown`，无虚假 `artifact.created/verification.passed/run.terminal`；独立读回对象确认物理副作用发生，且无盲重试。
- CI 引入上述同一 Run 的成功与 ACK 丢失负例，并继续执行原 C15/C16/OSS/S3 回归；CI 结果单独核查记录，不把本地 PASS 冒充 CI PASS。

## 仍未解决

1. 受控 Fake Tokens 不等于本轮的实模型流验证；C15 有此前真 LiteLLM 局部证据，但**同一真实模型 + S3 + Tool/Approval 未联合验**。
2. 此次没有真实 Tool 或 Approval，同一 Run 的全事件 G3 仍 PARTIAL。
3. S3 ACK UNKNOWN → `PENDING` 后尚未建立可信独立 Receipt 查询和自动业务恢复/终态裁决；仍属 G6 下一项，不能简单认定“幂等 S3 能重 PUT”就自动重试。
4. 未实现生产对象存储的 retention/GC、权限治理、跨地域 Backup/DR；都属于外围边界或后续准入，不在本次 POC 增量内。