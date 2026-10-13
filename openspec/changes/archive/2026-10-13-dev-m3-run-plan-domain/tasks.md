# DEV-M3 领域内核与 Workflow 映射 · Tasks

> 状态：**CLOSED · 2026-10-13，原始 DEV-HC-01 限定交付验收完成；Production NO-GO 保持不变。** 验收不扩展到 M4/M5/M9。

## 0. 前置与需求冻结
- [x] 0.1 审阅原有 Accepted ADR/HC 与 G01–G20，识别事实 Owner、安全边界和阻断依赖；OpenSpec 四类规划材料 Strict PASS。
- [x] 0.2 确认代表性真实业务/失败样本、环境及测试数据，记录本阶段交付与不做范围。

## 已完成的可独立验收切片（不替代后续任务）
- [x] A.1 真实 PostgreSQL Plan v1/Recipe Digest/Provider 冻结、重复 Intent 幂等、拒绝过期 Version 及 Replan 意图 BLOCKED_PROVIDER_QUIESCENCE；**证据**：docs/retrospectives/DEV_M3_M5_FIRST_SLICE_20261011.md（TDD Red→Green、PR #61，CI 38132324088 / 38132324099）。后续必须实测 Hatchet 停机 ACK/Receipt 后才能创建 Plan v2。

- [x] A.2 在真实 PostgreSQL 上原子冻结 PURE Plan v2/独立 Segment Outbox，Provider Native COMPLETED 后才允许新版本、旧 Plan/Attempt 的写入保护、新 Worker 按确认的 PG Provider ID 准入；真实 Hatchet 双 Workflow 和 26 项 PG/API/Model/SSE 回归；**证据**：docs/retrospectives/DEV_M3_REPLAN_V2_PURE_20261011.md（Red CI 38141097324、Green CI 38141333840、独立 Provider IDs）。旧 Worker 运行中 Cancel/TERMINATED、非 PURE Tool Receipt/UNKNOWN、完整多版本 Step/Attempt/业务终态和 Cube Worker 接管 **仍 OPEN**。

- [x] A.3 2026-10-13 Step 准入与迟到完成的**局部安全门禁**：真实 PG 先 RED 证明 CREATED/Provider 未绑定时 SDK Step 可错误启动，及 CANCEL_REQUESTED/CANCELLED 后迟到 Worker 可写 Step/Event；加锁重新校验 Run RUNNING + Plan v1，修复后 M3 三组 PG 测试 15/15 PASS。**证据**：docs/retrospectives/DEV_M3_STEP_TERMINAL_GUARD_20261013.md。仍缺完整版本化 Step/Attempt、实际 Hatchet Cancel/TERMINATED/非 PURE 联合验收，故 1.1～2.3 和 M3 阶段保持 OPEN。

- [x] A.4 2026-10-13 模型-only Plan v1 单次 Attempt 身份与并发重复派发拒绝：新增真实 PG `harness_step_attempt` 持久事实，SDK 传入独立 Attempt ID，完成必须同事务匹配当前 Attempt；重复启动、跨 Step、错误/缺失 ID、迟到结果均 Fail Closed。真实 PG 24/24、架构 8/8、OpenSpec 3/3 PASS；本地单独 E2E 因 Sidecar 下载 TLS 故障未完成，但 PR #81 官方最新 Head 真实 Hatchet/PG/双 SDK/Inspector CI 38341410835、M4 Receipt/物理 Worker CI 38341410826、M5 Cube PG CI 38341410883 与架构 CI 38341410872 均 SUCCESS；PR #81 已 squash merge main（e0fee11）。证据：docs/retrospectives/DEV_M3_ATTEMPT_FENCING_20261013.md。**属于 1.1/1.2/1.4 局部切片，不勾选完整 M3 Task/Gate。**

- [x] A.5 2026-10-13 DEV-M3 **组合收口候选**：v2 Run/Plan/Step/Attempt/Segment 业务终态、外部已确认非 PURE Receipt 的 opt-in 安全 Replan、Provider COMPLETED 下丢失 PURE 完成回调的旧 Attempt SUPERSEDED、Run Cancel/Binding 竞态保护。真实 PG 43/43、架构 8/8、Strict OpenSpec PASS。证据：docs/retrospectives/DEV_M3_INTEGRATED_REPLAN_GATES_20261013.md。**PR #83 已合并（f6fb667），最新 Head 真实 Hatchet/PG/双 SDK/Inspector、四项 Replan 与架构 CI SUCCESS；M4/M5 独立完整 Gate 不属于 M3 原定退出范围。**

## 正式阶段验收证据（依据最初 Proposal/Spec，而非后续理想能力）
- **原承诺**：真实 Hatchet Run 经批准 Replan 生成同平台 Run 的 Plan v2 和独立 Workflow Segment；旧 Attempt 不得继续完成或污染业务终态。
- **0.1/0.2**：Accepted HC-01/02/03、G01–G20 原则未修改；合成数据、实际 PG/Embedded Hatchet、独立账本，禁止企业私有代码。
- **1.1/1.2**：PR #61/#80/#81/#83 的先 Red 后 Green、PG Run/Plan/Step/Attempt/Segment 冻结、Provider Binding 和重入/迟到写保护。
- **1.3/1.4/2.1**：PR #83 Head ce8cfaa 的真实 PG/Hatchet/双 SDK/Inspector [CI 38343878631](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38343878631) SUCCESS；[Architecture CI 38343879325](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38343879325) SUCCESS。包含 v1→v2 独立 Native Workflow、旧 Attempt/Provider 错误写回拒绝、重复派发、ACK-loss、非 PURE UNKNOWN 拦截；不能以 SKIPPED 代替 PASS。
- **2.2/2.3**：现有根因复盘和 [正式阶段验收](../../../../docs/retrospectives/DEV_M3_FINAL_CLOSEOUT_20261013.md) 保留可追溯证据；归档 PR 最新 Head CI 验收并合并后原子关闭。
- **后续归属**：M4 通用 Task/Tool Receipt/Retry；M5 Cube/Worker Fencing；M6 Approval/Recipe；M7 API；M9 Production GO。未合并的增强（如 A.6）不构成 M3 新门禁。

## 1. TDD 与集成开发
- [x] 1.1 先按 HC-01 写状态机/版本/过期 Attempt 失败测试并记录 Red；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [x] 1.2 实现 Run/Plan/Step/Attempt/Segment 领域事实和独立 Provider Binding；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [x] 1.3 真实 PG+Hatchet 的 v1→v2 Replan、重复投递、失败阻断；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。
- [x] 1.4 完成跨 Version/Owner 负例、CI/回归与复盘；**证据**：失败/通过测试、实际 Run/Provider/Receipt/Workspace 等 ID（适用时）、CI 链接。

## 2. 阶段 Gate 与复盘
- [x] 2.1 复验 拒绝过期执行者 的拒绝/故障合同，正例、负例和真实集成全部 PASS；无 SKIPPED 冒充通过。
- [x] 2.2 记录故障根因、设计修正、测试覆盖、可复用护栏及风险，完成复盘与 Backlog 状态更新。
- [x] 2.3 代码 PR/CI、架构审查通过，确认无后续生产门禁被错误关闭后，勾选 Tasks 并归档该 OpenSpec。