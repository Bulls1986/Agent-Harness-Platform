# DEV-SBX V1 · Tasks / 里程碑计划

> **2026-10-14 范围冻结，SBX-M0 文档收口；SBX-M1 实施中，尚未验收。** 只有 M0 规划产物可按文档/Strict Gate 收口；所有 M1–M4 未经真实测试均须保持 OPEN。Owner/工期根据本机真实资源后续确定，不虚构日程。每个里程碑只按以下既定目标推进，不自动追加后续功能。

## SBX-M0 · 需求、架构与接口合同冻结
- [x] 0.1 合并正式冻结范围、Non-goals、HC-03/Identity/Workspace/Registry 兼容审查；说明 Cube 原生 Template/参数对齐策略与版本依赖。
- [x] 0.2 完成 Proposal/Design/Spec/Tasks、正例/负例验收矩阵、API Create/Attach/Execute 初稿及文档导航；OpenSpec Strict PASS。
- [x] 0.3 文档 PR 最新 Head CI/架构审核、Merge；明确 M1–M4 未验收，M9 Production NO-GO。

**SBX-M0 证据**：PR #98 已合并主干（`56e210f`），OpenSpec Strict PASS，Architecture CI 38524180142 SUCCESS。\n\n## SBX-M1 · Cube 原生管理 + Create/onCreate\n\n> 实施增量：完成限定 Create/onCreate + PG/HTTP 单元合同；Native Cube/Template Manager 尚未实测，M1 未完成。\n
- [ ] 1.1 Red：模板权限/不存在/Native 参数不支持、Create ACK-loss、相同 Key 冲突、初始化失败等测试。
- [ ] 1.2 实现受控 Cube Native Template 管理入口（只支持实证已存在原生动作）、创建及 Template ID 解析；取消创建链全局单一 `CUBE_TEMPLATE_ID` 假设。
- [ ] 1.3 实现 Create、onCreate guest command、Operation 持久化/查询/幂等/对账；实际 Cube+PG 验证（含 `envd` 可用性）。
- [ ] 1.4 OpenAPI、CI、架构 Review 与 M1 复盘，证据 PASS 后才能关闭 M1。


**M1 observed evidence (not closeout):** Cube SDK 0.7.3 native Template.list/get + actual localhost Cube MicroVM, HTTP Create -> real PG -> onCreate Guest git -> READY, idempotency replay and native Kill PASS. See [native Cube report](../../../docs/retrospectives/DEV_SBX_M1_NATIVE_CUBE_INCREMENT_20261014.md). Native build/alias/delete, real lost ACK injection, latest CI and final M1 review remain OPEN.

## SBX-M2 · Session Attach/onAttach
- [ ] 2.1 Red：未授权 Session/Scope、同一可写 Sandbox 跨 Session、未 READY、重连重复初始化、Git 不安全覆盖负例。
- [ ] 2.2 实现独立 Session Binding、Attach 受限 Initialization Permit，按顺序在真实 Cube Guest 执行 onAttach；初始化成功才变可用。
- [ ] 2.3 真 Cube Git Clone/Fetch、同 Binding reconnect、跨 Scope 拒绝、HTTP 断线/UNKNOWN 对账；回归 M5 Execution Fencing。
- [ ] 2.4 OpenAPI、CI、架构 Review 与 M2 复盘，证据 PASS 后才能关闭 M2。

## SBX-M3 · Execute + 生命周期
- [ ] 3.1 Red：无命令授权/过期 Lease/Fencing、非幂等 Command UNKNOWN、不允许 Host fallback、解绑仍活跃、Pause/Kill Workspace 丢失负例。
- [ ] 3.2 实现带许可的 Execute 和 Cube Commands/必要 Files、Operation 状态/受限输出/超时、受控的 Native inspect/pause/resume/release。
- [ ] 3.3 真 Cube 执行、故障恢复/命令对账、同 Scope 释放/重连、未授权拒绝、Model-only 0 Cube 回归。
- [ ] 3.4 OpenAPI、CI、架构 Review 与 M3 复盘，证据 PASS 后才能关闭 M3。

## SBX-M4 · 集成验收与正式收口
- [ ] 4.1 真实本机 Cube + PostgreSQL + 版本化 HTTP API Create→onCreate→Attach→Git→Execute→Reconnect/Release E2E，记录真实 ID/Exit Code/Outcome；不能用 Mock/Skipped 代替。
- [ ] 4.2 复验 ACK-loss、Scope/Session/Permit、UNKNOWN/Receipt、泄密、Workspace≠Sandbox 等正反例。
- [ ] 4.3 完整用户/API/本地部署使用手册 + OpenAPI、持续 CI/Architecture/Strict Validate，全量回归通过。
- [ ] 4.4 PR Merge、最终复盘/遗留风险和 OpenSpec Archive；只将 DEV-SBX V1 原冻结范围标 CLOSED，M9 继续 NO-GO。