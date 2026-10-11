# Agent Harness Platform · 正式研发里程碑计划

**工程定位：独立的、可被多个业务系统复用的 Agent 执行平台。当前处于正式开发阶段，生产准入 NO-GO。** 本仓库只保存 Harness 的公共 API/SDK、Run/Plan/Step/Attempt、Agent Runtime、Durable/Receipt、Sandbox 与可靠性设计；**任何业务消费者的内部实现、迁移计划、源码/接口/Schema/资产资料均不属于此仓库**。

## DEV-M0～M9 里程碑

| 阶段 | 平台交付目标 | 截至 2026-10-11 |
|---|---|---|
| DEV-M0 架构基线 | Accepted ADR、HC-01/02/03、G01–G20 | 决策已冻结 |
| DEV-M1 基础可运行平台 | 真 Hatchet/PG、双 Agent SDK、Run Inspector | 开发切片 PASS |
| DEV-M2 模型及流式交互 | 真实 LiteLLM、Token SSE、持久游标/取消 | 有限开发切片 PASS |
| DEV-M3 领域内核 | Run/Plan/Step/Attempt、Replan v2、Workflow Segment | ACTIVE：Plan v1 保护通过，完整 Gate OPEN |
| DEV-M4 一致性与恢复 | Outbox/Inbox、ACK-loss、UNKNOWN/非幂等 Receipt | 部分实现，真实故障 Gate OPEN |
| DEV-M5 Cube 可信执行 | WorkspaceRef/Scope/Lease/Fencing、跨 Worker 接管 | ACTIVE：可信准入测试通过，真 Cube Gate OPEN |
| DEV-M6 多 Agent Recipe | 跨 Runtime 交接、Verifier、Artifact、Approval | PLANNED |
| DEV-M7 公共 API/SDK | Conversation/Turn/Run、鉴权、Typed SSE、错误合同 | PLANNED |
| DEV-M8 通用消费者互通 | **只用合成数据**验证独立客户端对 Harness 公共 API 的调用、身份隔离和故障语义 | PLANNED |
| DEV-M9 生产交付 | 容量/安全/可靠性/部署/回退（含 100 Active Runs 实测） | PLANNED，Production NO-GO |

**依赖方向：外部业务消费者 → 受版本管理的 Harness 公共 API/SDK → Harness Domain/AgentRuntime → Hatchet/Cube。** 业务系统独立发布和维护，不得导入 Harness 内部源码、操作 Harness PG 或挪用技术执行权威；Harness 更不包含业务系统专属实现。

## 工作波次

第一波：M3 领域事实、M5 可信执行并行；M4 故障负例可以并行准备。第二波：M4 集成与 M7 API/SDK；第三波：M6 和 M8 独立合成客户端联调；最终 M9 的生产故障与安全门禁。Owner、工期与上线日期需根据真实资源独立基线化，不虚构排期。

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
