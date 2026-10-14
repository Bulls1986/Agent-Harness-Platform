# Agent Harness Platform · 正式研发里程碑计划

**工程定位：独立的、可被多个业务系统复用的 Agent 执行平台。当前处于正式开发阶段，生产准入 NO-GO。** 本仓库只保存 Harness 的公共 API/SDK、Run/Plan/Step/Attempt、Agent Runtime、Durable/Receipt、Sandbox 与可靠性设计；**任何业务消费者的内部实现、迁移计划、源码/接口/Schema/资产资料均不属于此仓库**。

## DEV-M0～M9 里程碑

| 阶段 | 平台交付目标 | 截至 2026-10-14 |
|---|---|---|
| DEV-M0 架构基线 | Accepted ADR、HC-01/02/03、G01–G20 | 决策已冻结 |
| DEV-M1 基础可运行平台 | 真 Hatchet/PG、双 Agent SDK、Run Inspector | 开发切片 PASS |
| DEV-M2 模型及流式交互 | 真实 LiteLLM、Token SSE、持久游标/取消 | 有限开发切片 PASS |
| DEV-M3 领域内核 | Run/Plan/Step/Attempt、Replan v2、Workflow Segment | **CLOSED（原始限定范围）**：真实 Hatchet v1→v2 独立 Segment、Plan/Step/Attempt/Provider Binding、旧 Attempt 拒绝均有主干代码与实际 CI。PR #80/#81/#83 Merge；[实际 PG/Hatchet/双 SDK CI 38343878631](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38343878631) 与 [架构 CI 38343879325](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38343879325) SUCCESS。通用 Retry/恢复归 M4、可信 Worker/Cube 归 M5、Production GO 归 M9。|
| DEV-M4 一致性与恢复 | Outbox/Inbox、ACK-loss、UNKNOWN/非幂等 Receipt | **CLOSED（原始限定范围）**：平台 PG Outbox/Native Lookup + Provider Observation Inbox 去重；三独立 PG 的非幂等 Tool 在真正 SIGKILL、原生 Retry、物理 A→B 接管后 UNKNOWN→唯一外部 Receipt 对账，未盲重放。原 A.1～A.4 有官方真实 CI；本次 Inbox 集成随归档 PR 最新 Head CI 通过后生效。通用 Tool Runtime 属后续增强，Cube 跨宿主/生产级 Gate 归 M5/M9。|
| DEV-M5 Cube 可信执行 | WorkspaceRef/Scope/Lease/Fencing、跨 Worker 接管 | **CLOSED（原始有界平台/单宿主真实 Coding Guest 合同）**：PR #94 PG/Native Cube Guest Shell/Git/Fencing/Scope Fail Closed；本地真实 Cube+PG、物理 Hatchet Worker A SIGKILL→B/8，同 Cube/Guest 字节、Git Shell、Release PASS；Model-only 0 Cube。**NOT TESTED**：跨宿主、Guest in-flight Fencing、完整 OpenCode Agent loop / Production Security。GitHub-hosted 真 Cube Gate 未配置，官方 PG/SDK/Architecture CI PASS；平台 **Production NO-GO**。见 [M5 最终收口](retrospectives/DEV_M5_FINAL_CLOSEOUT_20261013.md)。|
| DEV-M6 多 Agent Recipe | 跨 Runtime 交接、Verifier、Artifact、Approval | **CLOSED（原始有界合成 Recipe）**：PR #95 真实 Hatchet/PG 三 SDK 规划→编码→验证、真实 LiteLLM 独立调用、WAITING_INPUT/APPROVAL 原生唤醒、审批拒绝零写入、Worker A SIGKILL→B 同 Run/Provider 接管、三 Step 各 1 Attempt、合成外部账本 Receipt 仅 1 次；真实 PG 12/12 与字节夹具 2/2，官方 [Native CI 38499209969](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38499209969) 和 [架构 CI 38499209960](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38499209960) SUCCESS。**NOT TESTED / 非 M6 交付**：企业 OSS/IdP、业务 Git/OSS Tool、跨宿主及生产安全；Production NO-GO。正式 [M6 限定收口](retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md)。 |
| DEV-M7 公共 API/SDK | Conversation/Turn/Run、鉴权、Typed SSE、错误合同 | **CLOSED（原始平台受控交付限定范围）**：受控 PG 事实及真实 Hatchet/双 SDK Run、授权公共 API/SSE/ArtifactRef/结果页面与合成 Tool/审核/文件事件投影及 >250 Cursor，经 PR #65/#67/#86/#88/#90/#91 真实 CI/架构及本次归档验收。企业 Gateway/IdP/Policy 实际接入、真正 Tool/Approval/OSS 数据来源和旧企业 Portal **NOT VERIFIED**，归既有 M6/M8/M9/外部 Owner 独立验收；不等于整个产品集成上线，**Production NO-GO**。详见 [M7 正式限定收口](retrospectives/DEV_M7_FINAL_CLOSEOUT_20261013.md)。|
| DEV-M8 通用消费者互通 | **只用合成数据**验证独立客户端对 Harness 公共 API 的调用、身份隔离和故障语义 | **CLOSED（原始合成消费者公共 API 合同；以归档 PR 最新 Head CI + Merge 为准）**：独立 Node HTTP Client 7/7、真实 PostgreSQL + Native Hatchet/双 SDK + 版本化 API 合成身份及权限/取消意图/游标，官方 [M8 Native CI 38502537080](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38502537080) SUCCESS，架构 [38502537102](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38502537102) SUCCESS。企业 IdP、真正 OSS/Tool、Provider 物理取消和 Production 仍 NOT VERIFIED。见 [M8 限定收口](retrospectives/DEV_M8_FINAL_CLOSEOUT_20261014.md)。 |
| DEV-M9 生产交付 | 容量/安全/可靠性/部署/回退（含 100 Active Runs 实测） | PLANNED，Production NO-GO |

**依赖方向：外部业务消费者 → 受版本管理的 Harness 公共 API/SDK → Harness Domain/AgentRuntime → Hatchet/Cube。** 业务系统独立发布和维护，不得导入 Harness 内部源码、操作 Harness PG 或挪用技术执行权威；Harness 更不包含业务系统专属实现。

## DEV-SBX · M9 之前的独立沙箱管理补齐（2026-10-14 Scope FROZEN）

**新增独立交付线 DEV-SBX，不重新打开已经限定收口的 DEV-M5 / DEV-M7，也不改变 M9 的生产门禁与环境前置。** 开发范围由 [Cube Sandbox Management V1 冻结合同](references/CUBE_SANDBOX_MANAGEMENT_V1_20261014.md) 确定，四份 OpenSpec 规划材料见 [dev-sbx-cube-sandbox-management-v1](../openspec/changes/dev-sbx-cube-sandbox-management-v1/)。

| 子里程碑 | 冻结交付 | 状态 / 退出 Gate |
|---|---|---|
| **SBX-M0** 合同冻结 | Cube Native Template/参数原则；Create/Attach/Execute、授权/UNKNOWN、正反例与 Non-goals、OpenSpec | **CLOSED（文档范围）：PR #98 Merge + Architecture CI 38524180142 SUCCESS + OpenSpec Strict PASS**；不算功能实现 |
| **SBX-M1** Cube Native + Create | Cube Template 管理受控透传、实例 Create、可选 onCreate、持久 Operation/幂等 | **IN PROGRESS**：Create/onCreate PG/HTTP 测试切片；真 Cube Template 管理/原生 SDK/CI 尚未验收 |
| **SBX-M2** Session Attach | 独立 Session↔Sandbox Binding、短期 Initialization Permit、onAttach、同 Binding reconnect | PLANNED：真 Cube Git、跨 Session/Scope 拒绝、重连不重跑、M5 Fencing 回归 |
| **SBX-M3** Execute + 生命周期 | 授权命令/Files、结果/超时、查询、解绑、Native Pause/Resume/Release | PLANNED：真 Guest Command/UNKNOWN/Host fallback 拒绝、Workspace 生命周期正确 |
| **SBX-M4** 整体验收 | 版本化公共 API/OpenAPI、Cube+PG Create→Attach→Execute E2E、操作手册、复盘/归档 | PLANNED：官方 CI/架构/Strict + 真实负例、PR Merge，限原范围 CLOSED |

**排除：** Harness 自定义 Template DSL/Registry、二次包装 apt/pip/npm、项目/技能/子 Agent 管理、第二 Provider、Pool/调度引擎、生产集群部署/100 Active Runs。Cube 原生定义与 SDK 为唯一实施来源；上层决定初始化命令，Harness 验权限和状态。运行期仍采用 M5 HC-03；不以业务消费者私有迁移为前置。**M9 在真实生产部署/负载环境具备前继续 PLANNED / Production NO-GO。**

## 工作波次

第一波：M3 领域事实、M5 可信执行并行；M4 故障负例可以并行准备。第二波：M4 集成与 M7 API/SDK；第三波：M6 多 Agent Recipe 与 M8 独立合成客户端联调；最终 M9 的平台生产故障与安全门禁。Owner、工期与上线日期需根据真实资源独立基线化，不虚构排期。

## 前置依赖与当前阻断（2026-10-13）

| 阶段 | 真正前置与并行边界 | 未满足的完整阶段退出 Gate |
|---|---|---|
| M3 | M1 PG/Hatchet Run 基础已就绪，原限定 Replan 交付已完成 | **CLOSED**：v1→v2 独立 Segment 与过期 Attempt 隔离，后续 M4/M5/M9 Gate 不重复列为 M3 门禁 |
| M4 | M3 原始领域/Segment CLOSED，可复用事务 Outbox、Inbox、真实 Native Lookup/Receipt | **CLOSED（限定交付）**：真实 ACK-loss、非幂等外部账本 SIGKILL、Native A→B/并发恢复、一条持久观察 Inbox 去重；通用 ToolRuntime、M5 Cube、M9 Production 另行验收 |
| M5 | HC-03 不变；真实 Cube/PG/Native Worker 接管必须可溯源；不新增宿主 Shell 或第二引擎 | **CLOSED（单宿主原始有界交付）**：Cube Allocate/Bind/Release、Guest Shell/Files/Git、物理 A→B、PG Fencing 和模型-only 零沙箱实机/合同 PASS；跨宿主/进行中 Guest Fence/完整 OpenCode Agent loop **NOT TESTED**，按既有 M6/M9/基础设施 Gate；Production NO-GO |
| M6 | 依赖 M3/M4/M5 相关真实执行、安全和恢复 Gate | **CLOSED（原始合成 Recipe）**：跨 Runtime/Approval/Artifact byte+digest/Verifier/真实 A→B 与原 CI PASS；企业 OSS/生产交付仍独立 NO-GO |
| M7 | 原 M2 Typed SSE、M3 Run Owner；企业 IAM/OSS/审批提供方始终外部，不新增平台责任 | **CLOSED（原始 Harness API 受控范围）**：公共 API/PG/双 SDK/授权 SSE/ArtifactRef/只读 UI 技术合同实机验收与 OpenSpec 归档；真实企业 IdP、OSS/Tool/Approval 来源、现有 Portal **NOT VERIFIED**，仍为原 M6/M8/M9 以及外部平台的联合验收和生产 **NO-GO**，不得作为 M7 的新增功能任务 |
| M8 | 依赖 M7 版本化公共 API/SDK 与相关 M3～M6 合同；只使用独立合成客户端 | 身份隔离、取消、游标和失败传播的真实公共 API 联调 |
| M9 | 依赖 M3～M7 适用的平台真实 Gate 与本阶段安全/容量/恢复/回滚门禁；公开 API 可纳入 M8 合成合同证明 | 100 Active Runs、故障注入、平台 IAM/Scope/Receipt/回退实测，Production NO-GO |

**依赖方向不得颠倒：**M7 公共 API 是 M8 合成消费者测试的前置；任何特定业务消费者的开发、迁移或上线均不是 M6/M7/M9 的前置。各阶段 Tasks 的 `0.1/0.2` 只有对应**冻结的原始交付范围**证据齐备后方可勾选；子切片 PASS 不等于阶段完成，跨阶段的通用能力不得自动追加为前一阶段门禁。

## OpenSpec 阶段计划

| 阶段 | Change |
|---|---|
| DEV-M3 | [dev-m3-run-plan-domain（已归档）](../openspec/changes/archive/2026-10-13-dev-m3-run-plan-domain/) |
| DEV-M4 | [dev-m4-reliable-task-facts（已归档）](../openspec/changes/archive/2026-10-13-dev-m4-reliable-task-facts/) |
| DEV-M5 | [CLOSED · dev-m5-sandbox-worker-binding](../openspec/changes/archive/2026-10-13-dev-m5-sandbox-worker-binding/) |
| DEV-M6 | [CLOSED · dev-m6-agent-recipe-execution](../openspec/changes/archive/2026-10-14-dev-m6-agent-recipe-execution/) |
| DEV-M7 | [CLOSED · dev-m7-platform-access-contract](../openspec/changes/archive/2026-10-13-dev-m7-platform-access-contract/) |
| DEV-M8 | [CLOSED · dev-m8-external-consumer-integration](../openspec/changes/archive/2026-10-14-dev-m8-external-consumer-integration/) |
| DEV-M9 | [dev-m9-delivery-readiness](../openspec/changes/dev-m9-delivery-readiness/) |

## 阶段退出 Gate

1. Accepted HC/ADR 与 G01–G20 不被修改；所有业务事实与 Hatchet 技术事实边界可审查。
2. Red→Green→Refactor；失败、越权、ACK 丢失、过期执行与 UNKNOWN 样本先行。
3. 真实 PostgreSQL、Hatchet、Cube、模型/Tool（阶段适用时）端到端 Gate 必须 PASS；SKIPPED、模拟成功不构成验收。
4. CI/架构/信息安全审查、复盘、Tasks 证据、PR Merge 和 OpenSpec 归档全部完成后才能关闭阶段。
5. Production GO 只取决于 Harness 平台自身的安全、容量、恢复、部署和回滚验收，**不依赖任何特定业务消费者的上线与迁移**。