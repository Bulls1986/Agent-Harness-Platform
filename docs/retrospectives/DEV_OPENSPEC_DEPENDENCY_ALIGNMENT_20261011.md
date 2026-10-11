# DEV-M3～M9 OpenSpec 依赖方向与阶段状态校准（2026-10-11）

## 范围与权威

本次仅修正公开 Harness 里程碑、OpenSpec 实施阶段依赖、任务追踪及回归护栏，不改 Accepted ADR/HC、G01–G20、运行时代码或任何外部业务消费者资料。GitHub `main` 的既有证据构成状态来源；未执行的真实门禁不得被标记 PASS。

## 审计发现与修复

1. DEV-M7 已合并独立授权 Run 只读切片（PR #65，8 项单元合同测试，架构/授权 CI 成功），但里程碑总表及 Backlog 仍标 PLANNED。现统一为 ACTIVE，整阶段维持 OPEN。
2. DEV-M7 Proposal/Design 将 DEV-CONSUMER-02 写作前置，违反公共 API → 独立消费者的依赖方向。现明确 DEV-API-01 为 M7 交付，DEV-CONSUMER-01 为 M8 合成测试；M8 是 M7 下游而非阻断因素。
3. DEV-M6 使用 DEV-CONSUMER-04 追踪及特定业务应用的三 Agent 等价链路。现归属 DEV-RECIPE-01，E2E 使用合成通用任务、真实 SDK/执行/Verifier/Evidence/Approval，不纳入消费者私有数据。
4. DEV-M9 原有特定业务应用的等价与迁移作为 Production GO 退出条件。现仅以平台安全、恢复、真实容量、部署和回滚为 Gate；M8 合成消费者仅用于公开 API 合同证据，不构成私有应用迁移依赖。
5. `openspec/config.yaml` 的旧业务消费者前置描述一并修正。

## Gate 状态（没有提前勾选）

- M1/M2：有限真实开发验收成立；不代表生产 GO。
- M3：PG Plan v1/Version 保护已通过；Hatchet Replan v2/Segment 真实 Gate OPEN。
- M4：真实 ACK-loss、非幂等 Receipt UNKNOWN/SIGKILL Gate OPEN。
- M5：可信准入负例已通过；真实 Cube A→B 安全接管 Gate OPEN。
- M6：PLANNED；需 M3/M4/M5 相关真实 Gate。
- M7：ACTIVE，仅授权读取单测/CI 通过；Gateway/PG、Conversation/Turn、SSE/Artifact/UI 的完整 Gate OPEN。
- M8：PLANNED，仅独立合成消费者。
- M9：PLANNED，Production NO-GO；不依赖外部私有消费者。

## Red → Green / 检查计划

先在旧基线上执行断言“里程碑已反映 M7 ACTIVE、OpenSpec config 无旧消费者前置”得到 Red（断言 `RED: DEV-M7 status is stale`）；已修复对应文件，并在 `tests/test_development_milestone_plan.py` 新增 M7 状态一致性、公共 API 依赖方向、平台独立 Production GO 三项回归。真实 CI 验证结果以 PR 工作流为准，不用文档自证 PASS。

## PR CI 验证与修正

- PR #66 首轮 Architecture Guard 失败（run 38139299010）：新验收断言误把“特定外部应用**不**构成 Gate”的否定表述当作未剥离的正向依赖；这属于测试误报，非平台实现失败。修正 M9 公共表述并保留平台无私有依赖的负例护栏。
- [架构/里程碑回归 CI（run 38139392386）](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38139392386) **PASS**：包含新旧阶段测试、G01–G20 边界检查和文档导航。
- [DEV-M7 授权读取 CI（run 38139392429）](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38139392429) **PASS**：授权读取 8 项单测无回退。
- 本地独立 OpenSpec v1.12.0 的 M6/M7/M9 三阶段 Strict 在旧基线结构上均 PASS；此项**不是**本分支修改后全部文件的 Strict 复跑证据，不冒充真实 Gateway/PG/Cube/集成 Gate。

## 经验

状态只随有证据的开发切片更新；阶段 Gate 与子切片区分。独立通用 Harness 与下游应用依赖不逆转。测试用合成客户端/样本，私有业务系统验收由其自身工程负责。本次文档治理不解除 M3/M4/M5/M7 任何真实环境 Gate。
