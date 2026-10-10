# Development Backlog · Agent Harness Platform（2026-10-10）

> **状态：实施任务清单，不是新的架构选型或生产准入。** 以 [架构待办](ARCHITECTURE_BACKLOG.md) 的 Accepted/Decided Contract 为开发依据；实施完成度需按真实环境/CI 验收，不能因文档 DECIDED 直接宣称功能 PASS。
>
> 本文件尤其承接此前架构收口中的 **第 4 项：旧 PDLC 现网 API/会话/数据与无感迁移实码盘点**，用户明确要求**留在后续开发工作中**，不再阻挡 HC-01/02/03 的架构收口。

**首个实施变更（OpenSpec）**：[minimal-run-closed-loop](../openspec/changes/minimal-run-closed-loop/)：Proposal、三项 Specs、Design、Tasks 已建立，`openspec validate --strict` 通过；目标为 Docker PG 双库 + Hatchet + Pydantic/OpenAI 两 SDK 的一条真实业务 Run。**仅已建立规格与本地 PG，真正一体化端到端仍是 TODO；不得记入 ARCH-TODO-028 生产门禁通过。**

## 开发主线与依赖

| ID | 阶段 | 交付及验收定义 | 所依赖的冻结合同 | 状态 |
|---|---|---|---|---|
| DEV-HC-01 | P0 平台内核集成 | 将 Platform Run/Plan/Step/Attempt + Workflow Segment/Binding 接入真实 Hatchet；失败阻断、可核对 A→B、Replan 新 Plan 与 Segment | [HC-01](references/HATCHET_WORKFLOW_MAPPING_CONTRACT_20261010.md) | TODO |
| DEV-HC-02 | P0 持久事实与安全性 | PG Task Facts + Outbox/Inbox + Provider Binding 查询 + Receipt UNKNOWN 对账；SIGKILL/ACK 丢失/乱序与并发重投负例通过 | [HC-02](references/HARNESS_HATCHET_CONSISTENCY_CONTRACT_20261010.md) | TODO |
| DEV-HC-03 | P0 隔离执行集成 | Hatchet Worker→ExecutionContext→AgentRuntime/Cube：Scope/Lease/Fencing/WorkspaceRef 重连，跨 Scope Fail Closed | [HC-03](references/HATCHET_WORKER_SANDBOX_BINDING_CONTRACT_20261010.md) | TODO |
| DEV-PDLC-01 | **P0 / 迁移开发 M0** | **旧 PDLC 仓库与实际部署只读盘点**：现用 UI/URL/API、OpenCode Session/Message、业务 DB/OSS/Git、Agent/Skill/MCP/Hook、SSO/Policy、SSE、活动 Session；逐项产出 Owner/Legacy ID/数据引用/现网版本/回归样本/迁移映射 | [PDLC 迁移 M0](references/PDLC_REPLACEMENT_MIGRATION_20261010.md) | **DEFERRED TO DEVELOPMENT** |
| DEV-PDLC-02 | P0 / M1 | 旧 UI/URL/SSO/历史会话/项目资产兼容 Facade、稳定 ID Mapping、授权拒绝和只读数据等价回归；按 DEV-PDLC-01 实码确认边界 | DEV-PDLC-01、[Domain](references/DOMAIN_MODEL_AND_STATE_CONTRACT.md) | BLOCKED BY M0 |
| DEV-PDLC-03 | P0 / M2 | 白名单路由、单 Writer 灰度、影子只读比较/副作用禁止双写与可回退演练 | DEV-PDLC-02、[HC-02](references/HARNESS_HATCHET_CONSISTENCY_CONTRACT_20261010.md) | BLOCKED BY M1 |
| DEV-PDLC-04 | P0 / M3 | 一条真实既有 PDLC 产品→开发→验证业务 Recipe；至少两种 Agent SDK、Artifact/Evidence 交接、审批/验证阻断与任务级恢复 | DEV-HC-01/02/03、DEV-PDLC-01 | BLOCKED BY INTEGRATION |
| DEV-PDLC-05 | P0 / M4 | 按用户/项目灰度；真实历史和活动会话各自验收、生产隔离/审计/授权/回退与数据核对 | DEV-PDLC-02/03/04 | BLOCKED BY M1–M3 |

## DEV-PDLC-01 的边界和启动条件

- **只读事实输入**：旧 OpenCode PDLC 的 Repo/版本、运行容器、OpenAPI、真实 DB Schema、OSS 存储 Reference、活动会话恢复协议，须从旧系统原始代码或部署提取；**不可根据本文推测现网 Schema、已有功能或兼容率**。
- **输出形式**：`Legacy Feature/API/Data/Session → New Owner/Adapter/Mapping → Test/Backout` 对照矩阵；历史只读与**活动执行连续性**分开，不承诺历史 Chat 直接具有可恢复的新 Run。
- **实施后才能冻结的事项**：实际兼容 API Shape、后续 UI/Facade 代码模块、迁移工具是否需要写数据、用户切流颗粒度、服务回退窗口；不在当前架构评审中虚构。
- **工程依赖**：DEV-PDLC-01 可以与 HC-01/02/03 的平台集成并行开展，但不得阻止架构合同被标记 DECIDED；真实迁移上线仍严格以 M0→M4 及生产 Gate 为准。

## 可继续延后（非当前主线）

- 深度递归 SubAgent/A2A/动态协商、完整 BPMN、自建 MCP Marketplace/企业 IAM/计费/Secret/APM/数据库备份平台、跨地域 Remote Cube burst 产品化。
- Hatchet Engine 多节点部署密度、所有 Cube Provider 原生 SDK 版本兼容以及 100 并发资源实测归集成/部署验收，不反向拉回框架选型。