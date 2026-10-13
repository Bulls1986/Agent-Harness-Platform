# Agent Harness Platform · 正式研发里程碑计划

**工程定位：独立的、可被多个业务系统复用的 Agent 执行平台。当前处于正式开发阶段，生产准入 NO-GO。** 本仓库只保存 Harness 的公共 API/SDK、Run/Plan/Step/Attempt、Agent Runtime、Durable/Receipt、Sandbox 与可靠性设计；**任何业务消费者的内部实现、迁移计划、源码/接口/Schema/资产资料均不属于此仓库**。

## DEV-M0～M9 里程碑

| 阶段 | 平台交付目标 | 截至 2026-10-13 |
|---|---|---|
| DEV-M0 架构基线 | Accepted ADR、HC-01/02/03、G01–G20 | 决策已冻结 |
| DEV-M1 基础可运行平台 | 真 Hatchet/PG、双 Agent SDK、Run Inspector | 开发切片 PASS |
| DEV-M2 模型及流式交互 | 真实 LiteLLM、Token SSE、持久游标/取消 | 有限开发切片 PASS |
| DEV-M3 领域内核 | Run/Plan/Step/Attempt、Replan v2、Workflow Segment | **CLOSED（原始限定范围）**：真实 Hatchet v1→v2 独立 Segment、Plan/Step/Attempt/Provider Binding、旧 Attempt 拒绝均有主干代码与实际 CI。PR #80/#81/#83 Merge；[实际 PG/Hatchet/双 SDK CI 38343878631](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38343878631) 与 [架构 CI 38343879325](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38343879325) SUCCESS。通用 Retry/恢复归 M4、可信 Worker/Cube 归 M5、Production GO 归 M9。|
| DEV-M4 一致性与恢复 | Outbox/Inbox、ACK-loss、UNKNOWN/非幂等 Receipt | **CLOSED（原始限定范围）**：平台 PG Outbox/Native Lookup + Provider Observation Inbox 去重；三独立 PG 的非幂等 Tool 在真正 SIGKILL、原生 Retry、物理 A→B 接管后 UNKNOWN→唯一外部 Receipt 对账，未盲重放。原 A.1～A.4 有官方真实 CI；本次 Inbox 集成随归档 PR 最新 Head CI 通过后生效。通用 Tool Runtime 属后续增强，Cube 跨宿主/生产级 Gate 归 M5/M9。|
| DEV-M5 Cube 可信执行 | WorkspaceRef/Scope/Lease/Fencing、跨 Worker 接管 | ACTIVE：**真实 Cube Native SDK MicroVM Create/Guest Files/Connect/Destroy 最小 Demo PASS（本机两次）**；PG Binding/Fencing + 物理 Hatchet A→B + 同 Cube Workspace 联合 Gate、Guest/OCI 仍 OPEN |
| DEV-M6 多 Agent Recipe | 跨 Runtime 交接、Verifier、Artifact、Approval | PLANNED |
| DEV-M7 公共 API/SDK | Conversation/Turn/Run、鉴权、Typed SSE、错误合同 | **CLOSED（原始平台受控交付限定范围）**：受控 PG 事实及真实 Hatchet/双 SDK Run、授权公共 API/SSE/ArtifactRef/结果页面与合成 Tool/审核/文件事件投影及 >250 Cursor，经 PR #65/#67/#86/#88/#90/#91 真实 CI/架构及本次归档验收。企业 Gateway/IdP/Policy 实际接入、真正 Tool/Approval/OSS 数据来源和旧企业 Portal **NOT VERIFIED**，归既有 M6/M8/M9/外部 Owner 独立验收；不等于整个产品集成上线，**Production NO-GO**。详见 [M7 正式限定收口](retrospectives/DEV_M7_FINAL_CLOSEOUT_20261013.md)。|
| DEV-M8 通用消费者互通 | **只用合成数据**验证独立客户端对 Harness 公共 API 的调用、身份隔离和故障语义 | PLANNED |
| DEV-M9 生产交付 | 容量/安全/可靠性/部署/回退（含 100 Active Runs 实测） | PLANNED，Production NO-GO |

**依赖方向：外部业务消费者 → 受版本管理的 Harness 公共 API/SDK → Harness Domain/AgentRuntime → Hatchet/Cube。** 业务系统独立发布和维护，不得导入 Harness 内部源码、操作 Harness PG 或挪用技术执行权威；Harness 更不包含业务系统专属实现。

## 工作波次

第一波：M3 领域事实、M5 可信执行并行；M4 故障负例可以并行准备。第二波：M4 集成与 M7 API/SDK；第三波：M6 多 Agent Recipe 与 M8 独立合成客户端联调；最终 M9 的平台生产故障与安全门禁。Owner、工期与上线日期需根据真实资源独立基线化，不虚构排期。

## 前置依赖与当前阻断（2026-10-13）

| 阶段 | 真正前置与并行边界 | 未满足的完整阶段退出 Gate |
|---|---|---|
| M3 | M1 PG/Hatchet Run 基础已就绪，原限定 Replan 交付已完成 | **CLOSED**：v1→v2 独立 Segment 与过期 Attempt 隔离，后续 M4/M5/M9 Gate 不重复列为 M3 门禁 |
| M4 | M3 原始领域/Segment CLOSED，可复用事务 Outbox、Inbox、真实 Native Lookup/Receipt | **CLOSED（限定交付）**：真实 ACK-loss、非幂等外部账本 SIGKILL、Native A→B/并发恢复、一条持久观察 Inbox 去重；通用 ToolRuntime、M5 Cube、M9 Production 另行验收 |
| M5 | HC-03 是约束；Cube Allocate/Bind/Release 可与 M3/M4 并行；A→B 恢复需要相关执行事实 | 真 Cube MicroVM 原生创建、Guest 文件读写、同 ID 重连与销毁最小 Demo PASS；Harness PG/Worker B 联合 Fencing/Guest OCI/生产资源回收仍 OPEN |
| M6 | 依赖 M3/M4/M5 相关真实执行、安全和恢复 Gate | 通用合成 Recipe 的跨 Runtime、Approval、Artifact/Evidence、Verifier 实测 |
| M7 | 原 M2 Typed SSE、M3 Run Owner；企业 IAM/OSS/审批提供方始终外部，不新增平台责任 | **CLOSED（原始 Harness API 受控范围）**：公共 API/PG/双 SDK/授权 SSE/ArtifactRef/只读 UI 技术合同实机验收与 OpenSpec 归档；真实企业 IdP、OSS/Tool/Approval 来源、现有 Portal **NOT VERIFIED**，仍为原 M6/M8/M9 以及外部平台的联合验收和生产 **NO-GO**，不得作为 M7 的新增功能任务 |
| M8 | 依赖 M7 版本化公共 API/SDK 与相关 M3～M6 合同；只使用独立合成客户端 | 身份隔离、取消、游标和失败传播的真实公共 API 联调 |
| M9 | 依赖 M3～M7 适用的平台真实 Gate 与本阶段安全/容量/恢复/回滚门禁；公开 API 可纳入 M8 合成合同证明 | 100 Active Runs、故障注入、平台 IAM/Scope/Receipt/回退实测，Production NO-GO |

**依赖方向不得颠倒：**M7 公共 API 是 M8 合成消费者测试的前置；任何特定业务消费者的开发、迁移或上线均不是 M6/M7/M9 的前置。各阶段 Tasks 的 `0.1/0.2` 只有对应**冻结的原始交付范围**证据齐备后方可勾选；子切片 PASS 不等于阶段完成，跨阶段的通用能力不得自动追加为前一阶段门禁。

## OpenSpec 阶段计划

| 阶段 | Change |
|---|---|
| DEV-M3 | [dev-m3-run-plan-domain（已归档）](../openspec/changes/archive/2026-10-13-dev-m3-run-plan-domain/) |
| DEV-M4 | [dev-m4-reliable-task-facts（已归档）](../openspec/changes/archive/2026-10-13-dev-m4-reliable-task-facts/) |
| DEV-M5 | [dev-m5-sandbox-worker-binding](../openspec/changes/dev-m5-sandbox-worker-binding/) |
| DEV-M6 | [dev-m6-agent-recipe-execution](../openspec/changes/dev-m6-agent-recipe-execution/) |
| DEV-M7 | [CLOSED · dev-m7-platform-access-contract](../openspec/changes/archive/2026-10-13-dev-m7-platform-access-contract/) |
| DEV-M8 | [dev-m8-external-consumer-integration](../openspec/changes/dev-m8-external-consumer-integration/) |
| DEV-M9 | [dev-m9-delivery-readiness](../openspec/changes/dev-m9-delivery-readiness/) |

## 阶段退出 Gate

1. Accepted HC/ADR 与 G01–G20 不被修改；所有业务事实与 Hatchet 技术事实边界可审查。
2. Red→Green→Refactor；失败、越权、ACK 丢失、过期执行与 UNKNOWN 样本先行。
3. 真实 PostgreSQL、Hatchet、Cube、模型/Tool（阶段适用时）端到端 Gate 必须 PASS；SKIPPED、模拟成功不构成验收。
4. CI/架构/信息安全审查、复盘、Tasks 证据、PR Merge 和 OpenSpec 归档全部完成后才能关闭阶段。
5. Production GO 只取决于 Harness 平台自身的安全、容量、恢复、部署和回滚验收，**不依赖任何特定业务消费者的上线与迁移**。