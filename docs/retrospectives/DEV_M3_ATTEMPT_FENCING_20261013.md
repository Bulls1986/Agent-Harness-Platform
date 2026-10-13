# DEV-M3 · PostgreSQL Step Attempt 身份与重复派发保护（2026-10-13）

## 归属
仅推进原 DEV-HC-01/DEV-M3 1.1～1.4 的局部切片，不新建里程碑或调度器。Hatchet 仍是技术执行状态权威；Harness 保留 Run/Step/Attempt 业务事实。G01/G02/G03/G08/G20 与 HC-01/02/03 不改变。

## TDD：Red
先创建真实 PostgreSQL 合同 `poc.closed_loop.test_step_attempt_pg` 五个正反用例，原实现 5/5 ERROR（start_step 不接受 attempt_id）。原有 `start_step` 对 RUNNING Step 的重复调用会增加 attempts 并导致再次启动 SDK；`finish_step` 仅靠 Step RUNNING/Plan Version 判断可写，没有独立 Attempt 身份。

## 最小实现
- 新增 PG `harness_step_attempt`：独立 Attempt ID（唯一）、`run_id/step_id/ordinal/plan_version/state`，完全由平台持久化。
- `start_step` 显式携带限定长度 ASCII Attempt ID，当前 Step 必须 PENDING 且无旧 Attempt；同一 RUNNING Step 的并发投递、同 ID Replay、存在旧 Attempt 而未对账的重启均 Fail Closed；COMPLETED 的 PURE Step 只返回冻结输入对应的缓存结果。
- `finish_step` 事务内校验当前 Run/Plan、Step 状态及最新 Attempt ID/Version/State；不匹配时在任何 Domain Event/Step Commit 前拒绝。
- Pydantic/OpenAI Worker 每次执行产生唯一 UUID Attempt ID，并贯穿开始与完成；不把 Hatchet Native Retry 默认为允许业务重新执行。

## 证据
- RED：5/5 ERROR，缺失独立 Attempt API；真实 PG。
- GREEN：Docker Desktop PostgreSQL `harness_poc` 上，Step Attempt、Facts、PlanGuard、ReplanV2、SSE 合同 **24/24 PASS，0 SKIPPED**。
- Architecture Guards **8/8 PASS**；OpenSpec Strict **3/3 PASS**。
- 本地 Docker Hatchet 联合 E2E 第一轮 Sidecar 下载遭遇 TLS `UNEXPECTED_EOF_WHILE_READING`；第二轮因执行工具安全检查未启动，**本地 E2E 非 PASS**。将新 PG 测试纳入原 GitHub Actions，并以新 PR 最新 Head 的真实 Hatchet/Dual-SDK/Inspector CI 决定联测结论。

### 官方 CI / Merge 最终验收（补记）

PR [#81](https://github.com/Bulls1986/Agent-Harness-Platform/pull/81) 的最新 Head `d6776e7` 通过四条官方 CI：真实 PG/Hatchet 双 SDK/Inspector [38341410835](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38341410835) SUCCESS；M4 非幂等 Receipt/真实 Worker A SIGKILL→B [38341410826](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38341410826) SUCCESS；M5 Cube Binding [38341410883](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38341410883) SUCCESS；Architecture [38341410872](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38341410872) SUCCESS。无 PR Review Thread，已 squash merge main，合并提交 `e0fee11116ea4fc1387d551c82bee24802c01579`。**仅 A.4 模型-only 单次 Attempt 合同完成，整阶段 M3 仍 ACTIVE / OPEN；生产 NO-GO。**

## 根因、改进与遗留风险
根因是 `harness_step.attempts` 只当计数器，不是能识别执行来源的不可变业务 Attempt ID。当前 Attempt ID 是审计/关联键，**不是授权 Token**；真实 Tool 仍须 HC-03 Lease/Fencing/Scope、HC-02 Receipt 的独立认证授权。老数据中已 RUNNING 但无 Attempt row 的步骤采用 Fail Closed，禁止静默补绑伪造资格。

本切片只覆盖单次模型-only Plan v1；多个真正执行的 Attempt/安全 Retry、Version v2 Step 执行、跨 Worker Epoch、非 PURE Effect UNKNOWN、真实取消停机、审批和最终 M3 退出 Gate 均保持 OPEN，不将局部 PG PASS 记成 M3 完成或生产 GO。