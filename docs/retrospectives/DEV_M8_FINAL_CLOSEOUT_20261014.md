# DEV-M8 最终限定收口证据（2026-10-14）

## 范围裁决
DEV-M8 仅验证独立合成消费者通过版本化 Harness Public API 的 Conversation/Turn/Run、授权隔离、Typed SSE 游标、取消请求及失败传播。消费者是独立 Node HTTP 代码；绝不导入 Harness 内部数据库、调度器或任何业务应用的专有材料。
DEV-M6/M7 均已在 main 以原限定范围 CLOSED，不因本次消费者集成重新开放。

## Red → Green 与真实官方证据
- Red: 独立消费者模块不存在时，Node 测试以 ERR_MODULE_NOT_FOUND 失败；Green: 合同测试 7/7 PASS、0 SKIPPED，覆盖协议版本、可信身份、Scope/Run、事件游标、SSE Last-Event-ID、取消语义及提交 ACK 不确定性。
- 正式 Native Gate: https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38502350952 SUCCESS；证据文件补齐后的 https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38502537080 SUCCESS。
- 实际 Node HTTP Consumer → FastAPI M7 Public API → Harness PostgreSQL 16 → Native Hatchet → 两个真实 Agent SDK。Platform Run run-af836b99ba7ef6108cbd0920bf65544e，Hatchet Workflow 69b958dd-df10-4269-bb3b-ad9b271dd0f0，Run COMPLETED / Outbox CONFIRMED、14 条持久 Event；同一 Idempotency-Key 重入不重复派发。
- 跨合成 USER/Project Scope 的 Run/Events/SSE 访问均 HTTP 404；SSE Last-Event-ID 能按 PG 游标继续，不重放旧事件。
- 对单独的受控合成进行中任务，API/PG 返回 CANCEL_REQUESTED，且 provider_terminated=false。该夹具使用 held synthetic provider，不宣称 Native Worker 物理终止。
- 架构门禁最初由于 OpenSpec 已打勾任务缺少证据引用而 FAIL。按既有规则新增 docs/retrospectives/DEV_M8_CONSUMER_TDD_20261014.md 并为勾选项挂证据，官方架构 https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38502537102 SUCCESS、M7 PG/HTTP https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38502537204 SUCCESS；未放松保护性规则。

## 非目标与余留门禁
企业实际 Gateway/IdP/Policy、OSS/Tool/审批的生产来源、跨宿主、生产安全及容量、OpenCode Agent 的完整实际 Loop、任何企业业务迁移仍 NOT VERIFIED。不混同合成身份与生产 IAM，也不将取消意图当作进程停止。平台 M9 Production NO-GO 保持。

## 复盘与收口条件
架构护栏及时识别证据不完整；修正的是证据可追踪性，而非新增开发范围。运行提交 ACK 不明禁止盲重试，所有 Run/事件游标必须以服务器持久归属为准。
结论限定为 M8 的合成消费公共 API 合同。最终归档 PR 必须通过最新 Head 的全部适用 CI、严格 OpenSpec 校验及合并审查后才能报告正式 merge；否则保持 OPEN。
