# Agent Harness Platform · 正式研发里程碑计划

**工程定位：独立的、可被多个业务系统复用的 Agent 执行平台。当前处于正式开发阶段，生产准入 NO-GO。** 本仓库只保存 Harness 的公共 API/SDK、Run/Plan/Step/Attempt、Agent Runtime、Durable/Receipt、Sandbox 与可靠性设计；**任何业务消费者的内部实现、迁移计划、源码/接口/Schema/资产资料均不属于此仓库**。

## DEV-M0～M9 里程碑

| 阶段 | 平台交付目标 | 截至 2026-10-12 |
|---|---|---|
| DEV-M0 架构基线 | Accepted ADR、HC-01/02/03、G01–G20 | 决策已冻结 |
| DEV-M1 基础可运行平台 | 真 Hatchet/PG、双 Agent SDK、Run Inspector | 开发切片 PASS |
| DEV-M2 模型及流式交互 | 真实 LiteLLM、Token SSE、持久游标/取消 | 有限开发切片 PASS |
| DEV-M3 领域内核 | Run/Plan/Step/Attempt、Replan v2、Workflow Segment | ACTIVE：Plan v1 与 PURE 真实 Hatchet v1→v2 独立 Segment 子切片 PASS；非 PURE/完整 Step-Attempt Gate OPEN |
| DEV-M4 一致性与恢复 | Outbox/Inbox、ACK-loss、UNKNOWN/非幂等 Receipt | ACTIVE：实际 Worker A 进程 SIGKILL→独立 B 领取 Native Task、非幂等 Receipt/PG Fencing 子切片 PASS；通用 ToolRuntime/Inbox/跨宿主完整 Gate OPEN |
| DEV-M5 Cube 可信执行 | WorkspaceRef/Scope/Lease/Fencing、跨 Worker 接管 | **CLOSED · 受控 POC Gate**：真实 Cube/OpenCode Native Shell/Files/VCS、PG Fencing、物理 Hatchet A SIGKILL→B 同 Sandbox/Session 恢复及在途不确定工具整沙箱隔离、父 Run BLOCKED_UNKNOWN，均有真实证据；**生产安全/OCI/Git Revision/外部 Tool Receipt/容量仍 NO-GO** |
| DEV-M6 多 Agent Recipe | 跨 Runtime 交接、Verifier、Artifact、Approval | PLANNED |
| DEV-M7 公共 API/SDK | Conversation/Turn/Run、鉴权、Typed SSE、错误合同 | ACTIVE：授权只读 8 项单测、真实 PG Run 归属/不可变性 5 项测试及 CI PASS；真实 Gateway/Policy+PG E2E、SSE/Artifact/UI Gate OPEN |
| DEV-M8 通用消费者互通 | **只用合成数据**验证独立客户端对 Harness 公共 API 的调用、身份隔离和故障语义 | PLANNED |
| DEV-M9 生产交付 | 容量/安全/可靠性/部署/回退（含 100 Active Runs 实测） | PLANNED，Production NO-GO |

**依赖方向：外部业务消费者 → 受版本管理的 Harness 公共 API/SDK → Harness Domain/AgentRuntime → Hatchet/Cube。** 业务系统独立发布和维护，不得导入 Harness 内部源码、操作 Harness PG 或挪用技术执行权威；Harness 更不包含业务系统专属实现。

## 2026-10-12 阶段状态冻结与下一执行切片

**DEV-M5 受控 POC Exit 完成**：正常恢复（同一原 Cube/OpenCode Session、Hatchet 物理 A→B Native Retry、Fencing）和异常在途隔离（Destroy ACK、父 Run BLOCKED_UNKNOWN、保留外部 Effect 未知）双终态，真实 PG 24/24、M5 合同 41/41、模型-only 0 Sandbox 与 OpenSpec 正式 Spec Strict PASS；证据见 docs/retrospectives/DEV_M5_FINAL_ACCEPTANCE_MATRIX_20261012.md。已归档 OpenSpec；合并须以 PR 最新 Head CI 成功为准。**阶段关闭仅限受控 POC，不代表任何生产 GO，也不代表外部效果自动对账或原 Session 可在销毁后恢复。** 以下保留当日排障历史快照，历史 ACTIVE/BLOCKED 文字不代表本表的最新状态。

**M5 Guest 在途屏障追加验收**：真实 OpenCode v2 Shell/Files/Git 已在 Cube+PG+Hatchet 双物理 Worker A SIGKILL→B Native Retry 下通过。新增 Harness PG 持久化工具 Effect 意图与终态回执：发起前登记 DISPATCHED，未知在途操作阻止 B Takeover/Destroy，前台 Shell 终态 marker 与文件验证后才能 CONFIRMED。真实 PG 并发拒绝测试和正常 PG+OpenCode 实机重测通过，但并不证明任意 Guest 后台子进程被强制终止。DEV-M5 1.3/2.1/2.3 仍 OPEN。证据：docs/retrospectives/DEV_M5_GUEST_INFLIGHT_BARRIER_20261012.md。

**DEV-M5 当日 Exit 审计增量**：8 项 OPEN 经独立证据复核后，0.1/0.2/1.1/1.4 和阶段故障复盘 2.2 完成，余 **1.3 OpenCode Native Shell/Files/Git Guest 全链及在途 Fencing、2.1 全量真实阶段 Gate、2.3 审查合并归档**仍 OPEN。真实 Cube SDK 提供模型-only Native Inventory 0→0 的资源证明；新增 TDD 发现并封堵 Runtime 操作名与 Capability 不符的授权绕过，实际 PG Cube Binding 15/15。真实 Guest 首次探针发现 OpenCode 文件但修正后可运行性未获得 PASS，不能标记 1.3 完成。详见 docs/retrospectives/DEV_M5_PHASE_EXIT_AUDIT_20261012.md。完整 M5 仍 ACTIVE，生产 NO-GO。

**B.3a/B.3b Inspector Worker Takeover 可信场景执行（当日增量）**：原双 Tab Inspector 的固定授权 Runner、默认关闭、单活锁、原生证据校验、脱敏落盘及查询完成。新 HTTP API 真实触发的 Hatchet Worker A SIGKILL→独立 B Retry→原生 Cube Guest/PG Fencing 同 Run 实机 **PASS_REAL_INSPECTOR_TRUSTED_B03_API**；新 Evidence proof-c7b82a4c3c6d4a4d963e5aee8fbf52e5，Run m5-joint-8b90c55281864cfe8f055cb1de6fbb8d，Sandbox 73d702e69a374e778bcae3ed79d1625a；PG Epoch 8/RELEASED，Cube 0 Sandbox、重建 Inspector 后可查询证据。**只关闭 Worker Takeover 受控路径，不包含 Cube-only、非幂等 Receipt 的独立执行、完整 Guest/安全/容量或 M5 整体 Gate。** 详见 docs/retrospectives/DEV_M5_INSPECTOR_TRUSTED_SCENARIO_20261012.md。

**2026-10-12 当日后续实机增量（覆盖以下历史 BLOCKED 状态，但不覆盖整个 M5）**：本地 WSL 服务反复中断的主要可复现条件已定位并解决：WSL distro 在 Windows 不维持前台任务时进入正常 poweroff，旧 Python docker-compose 1.29.2 与 Docker 29 的事件监听还有 `KeyError: 'id'`。安装 Ubuntu Compose V2 2.40.3 并从 Windows Task Scheduler 启动**无自动触发的按需 WSL Keeper** 后，Cube MySQL/Redis/MinIO/CubeMaster/API 持续健康，`/health` HTTP 200；原生 SDK 真 MicroVM Create/Guest 新连接/Destroy 再次 PASS，Harness PG+Cube Live Gate PASS，**同一 Run/原生 Hatchet Worker A SIGKILL→独立 B Retry→原 Cube Guest 接管 B03 PASS**。Run、Workflow、PID、Native Retry、PG Fencing、原 Provider Sandbox、Guest 校验及 Destroy ACK 见 `docs/retrospectives/DEV_M5_JOINT_WORKER_CUBE_IMPLEMENTATION_20261012.md`。**M5 B.1/B.2 和 1.2 子项可据证据计 PASS，但 B.3、OpenCode 完整 Guest、in-flight fencing、2.x 退出门禁及整个 M5 保持 OPEN；Production NO-GO**。本地复现运维入口：`scripts/dev_cube_wsl_keepalive.ps1`，仅限受控 Windows/WSL 开发环境。

当前事实必须按 **独立切片** 与 **联合门禁** 分开统计：M0 冻结；M1 基础闭环与 M2 部分真实 SSE/模型切片 PASS；M3/M4/M5/M7 均为 ACTIVE / 完整退出 Gate OPEN；M6/M8/M9 尚未完成正式验收。**Production NO-GO**。Inspector 8765 的原「需求分析→独立审核」可发起 Demo（确定性模型为默认配置）；「能力验证」Tab 展示四场景的用途与只读证据，不能把 PG 证据、旧 Worker 独立实验或 Cube 独立实验标作同一 Run 的真实联合 PASS。

**已完成 P0 / DEV-M5-B03**：同一 Harness Run / Execution 与原生 Hatchet Workflow 的独立 Worker A SIGKILL→B Native Retry、PG Fencing 7→8、原 Cube Sandbox ID/Guest 字节恢复、旧 Epoch 与错误 Scope 拒绝和 Destroy ACK 已获得本机实机 PASS；范围只使用合成数据，未证明生产 IAM、跨宿主 HA、OpenCode 完整 Guest 或 in-flight Guest Fencing。**下一优先级改为 DEV-M5 尚未满足的完整 Guest/资源门禁及 Inspector B.3 的可信场景执行与证据 API**。

**并行 P1 / Inspector**：复用同一可信 Scenario Runner / Evidence API 合同作为未来统一入口，不开放无认证的浏览器特权 SIGKILL/Cube 启动路径；正式运行器和真实证据交付之前，相关三个场景维持只读。后续顺序：M3/M4 正式领域与恢复合同 → M7 公共 API → M6 Recipe → M8 合成消费者 → M9 生产准入。

## 工作波次

第一波：M3 领域事实、M5 可信执行并行；M4 故障负例可以并行准备。第二波：M4 集成与 M7 API/SDK；第三波：M6 多 Agent Recipe 与 M8 独立合成客户端联调；最终 M9 的平台生产故障与安全门禁。Owner、工期与上线日期需根据真实资源独立基线化，不虚构排期。

## 前置依赖与当前阻断（2026-10-11）

| 阶段 | 真正前置与并行边界 | 未满足的完整阶段退出 Gate |
|---|---|---|
| M3 | M1 Run/PG/Hatchet 已有有限实测；M3 内核开发可独立推进 | PURE PG+Hatchet v1→v2 子切片 PASS；运行中旧 Worker 结束确认、非 PURE/完整 Step-Attempt/业务终态仍 OPEN |
| M4 | M3 Domain/Segment 事实是完整恢复对账的前置；故障负例可先并行 TDD | 物理 Worker A SIGKILL→B、Receipt Fencing 限定场景 PASS；通用 Inbox/多 Attempt、跨宿主与生产 Tool Runtime Gate OPEN |
| M5 | HC-03 是约束；正式生产准入仍需 M3/M4 适用的领域与外部 Receipt 治理 | 受控 POC 的真 Cube/OpenCode 与 Worker A→B/UNKNOWN 隔离门禁 CLOSED；正式 OCI/Git Revision 可复现、跨宿主生产可靠性/容量/IAM 仍在 M9 NO-GO |
| M6 | 依赖 M3/M4/M5 相关真实执行、安全和恢复 Gate | 通用合成 Recipe 的跨 Runtime、Approval、Artifact/Evidence、Verifier 实测 |
| M7 | 依赖 M2 Typed SSE 和 M3 的 Run 归属领域事实；外部可信身份是适配输入，可并行开发授权边界 | PG Run Binding 子切片 PASS；真实 Gateway/Policy+PG 联调、Conversation/Turn、授权 SSE/Artifact/UI 仍 OPEN |
| M8 | 依赖 M7 版本化公共 API/SDK 与相关 M3～M6 合同；只使用独立合成客户端 | 身份隔离、取消、游标和失败传播的真实公共 API 联调 |
| M9 | 依赖 M3～M7 适用的平台真实 Gate 与本阶段安全/容量/恢复/回滚门禁；公开 API 可纳入 M8 合成合同证明 | 100 Active Runs、故障注入、平台 IAM/Scope/Receipt/回退实测，Production NO-GO |

**依赖方向不得颠倒：**M7 公共 API 是 M8 合成消费者测试的前置；任何特定业务消费者的开发、迁移或上线均不是 M6/M7/M9 的前置。各阶段 Tasks 的 `0.1/0.2` 只有对应全范围证据齐备后方可勾选；子切片 PASS 不等于阶段完成。

## OpenSpec 阶段计划

| 阶段 | Change |
|---|---|
| DEV-M3 | [dev-m3-run-plan-domain](../openspec/changes/dev-m3-run-plan-domain/) |
| DEV-M4 | [dev-m4-reliable-task-facts](../openspec/changes/dev-m4-reliable-task-facts/) |
| DEV-M5 | [已归档：dev-m5-sandbox-worker-binding](../openspec/changes/archive/2026-10-12-dev-m5-sandbox-worker-binding/) · [正式 Spec](../openspec/specs/sandbox-worker-binding/spec.md) |
| DEV-M6 | [dev-m6-agent-recipe-execution](../openspec/changes/dev-m6-agent-recipe-execution/) |
| DEV-M7 | [dev-m7-platform-access-contract](../openspec/changes/dev-m7-platform-access-contract/) |
| DEV-M8 | [dev-m8-external-consumer-integration](../openspec/changes/dev-m8-external-consumer-integration/) |
| DEV-M9 | [dev-m9-delivery-readiness](../openspec/changes/dev-m9-delivery-readiness/) |

## 阶段退出 Gate

1. Accepted HC/ADR 与 G01–G20 不被修改；所有业务事实与 Hatchet 技术事实边界可审查。
2. Red→Green→Refactor；失败、越权、ACK 丢失、过期执行与 UNKNOWN 样本先行。
3. 真实 PostgreSQL、Hatchet、Cube、模型/Tool（阶段适用时）端到端 Gate 必须 PASS；SKIPPED、模拟成功不构成验收。
4. CI/架构/信息安全审查、复盘、Tasks 证据、PR Merge 和 OpenSpec 归档全部完成后才能关闭阶段。
5. Production GO 只取决于 Harness 平台自身的安全、容量、恢复、部署和回滚验收，**不依赖任何特定业务消费者的上线与迁移**。
