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
| DEV-M5 Cube 可信执行 | WorkspaceRef/Scope/Lease/Fencing、跨 Worker 接管 | ACTIVE：**真实 Cube Native SDK MicroVM Create/Guest Files/Connect/Destroy 最小 Demo PASS（本机两次）**；PG Binding/Fencing + 物理 Hatchet A→B + 同 Cube Workspace 联合 Gate、Guest/OCI 仍 OPEN |
| DEV-M6 多 Agent Recipe | 跨 Runtime 交接、Verifier、Artifact、Approval | PLANNED |
| DEV-M7 公共 API/SDK | Conversation/Turn/Run、鉴权、Typed SSE、错误合同 | ACTIVE：授权只读 8 项单测、真实 PG Run 归属/不可变性 5 项测试及 CI PASS；真实 Gateway/Policy+PG E2E、SSE/Artifact/UI Gate OPEN |
| DEV-M8 通用消费者互通 | **只用合成数据**验证独立客户端对 Harness 公共 API 的调用、身份隔离和故障语义 | PLANNED |
| DEV-M9 生产交付 | 容量/安全/可靠性/部署/回退（含 100 Active Runs 实测） | PLANNED，Production NO-GO |

**依赖方向：外部业务消费者 → 受版本管理的 Harness 公共 API/SDK → Harness Domain/AgentRuntime → Hatchet/Cube。** 业务系统独立发布和维护，不得导入 Harness 内部源码、操作 Harness PG 或挪用技术执行权威；Harness 更不包含业务系统专属实现。

## 2026-10-12 阶段状态冻结与下一执行切片

当前事实必须按 **独立切片** 与 **联合门禁** 分开统计：M0 冻结；M1 基础闭环与 M2 部分真实 SSE/模型切片 PASS；M3/M4/M5/M7 均为 ACTIVE / 完整退出 Gate OPEN；M6/M8/M9 尚未完成正式验收。**Production NO-GO**。Inspector 8765 的原「需求分析→独立审核」可发起 Demo（确定性模型为默认配置）；「能力验证」Tab 展示四场景的用途与只读证据，不能把 PG 证据、旧 Worker 独立实验或 Cube 独立实验标作同一 Run 的真实联合 PASS。

**下一优先级 P0 / DEV-M5-B03**：首先验证真 `NativeCubeTransport` 使用冻结的模板配置；以同一个 Harness Run / Execution 和原生 Hatchet Workflow ID 证明：独立 A Worker 获授权后创建**真实** Cube MicroVM、写入 Guest Workspace→操作系统真实 SIGKILL A→原生 Hatchet Retry 由独立 B 领取→Harness PG 按服务器时间授予 B 新 Fencing Epoch→B 以原 Sandbox ID 重连，读取原始 Guest 字节→拒绝 A 旧 Epoch 与错误 Scope→B 销毁 Sandbox 并确认 ACK。缺任一真实证据即 **BLOCKED / OPEN**，不以两个单独脚本拼接为 PASS。范围只使用合成数据；不包括生产 IAM、跨宿主 HA、OpenCode 完整 Guest、in-flight Guest Fencing。

**并行 P1 / Inspector**：复用同一可信 Scenario Runner / Evidence API 合同作为未来统一入口，不开放无认证的浏览器特权 SIGKILL/Cube 启动路径；正式运行器和真实证据交付之前，相关三个场景维持只读。后续顺序：M3/M4 正式领域与恢复合同 → M7 公共 API → M6 Recipe → M8 合成消费者 → M9 生产准入。

## 工作波次

第一波：M3 领域事实、M5 可信执行并行；M4 故障负例可以并行准备。第二波：M4 集成与 M7 API/SDK；第三波：M6 多 Agent Recipe 与 M8 独立合成客户端联调；最终 M9 的平台生产故障与安全门禁。Owner、工期与上线日期需根据真实资源独立基线化，不虚构排期。

## 前置依赖与当前阻断（2026-10-11）

| 阶段 | 真正前置与并行边界 | 未满足的完整阶段退出 Gate |
|---|---|---|
| M3 | M1 Run/PG/Hatchet 已有有限实测；M3 内核开发可独立推进 | PURE PG+Hatchet v1→v2 子切片 PASS；运行中旧 Worker 结束确认、非 PURE/完整 Step-Attempt/业务终态仍 OPEN |
| M4 | M3 Domain/Segment 事实是完整恢复对账的前置；故障负例可先并行 TDD | 物理 Worker A SIGKILL→B、Receipt Fencing 限定场景 PASS；通用 Inbox/多 Attempt、跨宿主与生产 Tool Runtime Gate OPEN |
| M5 | HC-03 是约束；Cube Allocate/Bind/Release 可与 M3/M4 并行；A→B 恢复需要相关执行事实 | 真 Cube MicroVM 原生创建、Guest 文件读写、同 ID 重连与销毁最小 Demo PASS；Harness PG/Worker B 联合 Fencing/Guest OCI/生产资源回收仍 OPEN |
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
| DEV-M5 | [dev-m5-sandbox-worker-binding](../openspec/changes/dev-m5-sandbox-worker-binding/) |
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
