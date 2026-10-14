# DEV-M6 多 Agent Recipe 与审批验证 · Tasks

> 状态：**CLOSED（2026-10-14，原始限定合成 Recipe）**。实机 Hatchet 三 SDK、双 durable wait、实际物理 Worker A→B 同 Run/Provider 接管、审批拒绝与独立外部测试账本 Receipt 均验证；正式 PR #95 原代码 [Hatchet/PG/Inspector CI #38499209969](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38499209969) 与 [架构 CI #38499209960](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38499209960) SUCCESS。最终归档 Head 仍须官方 CI 复验通过才能合并。正式限定收口：docs/retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md。企业 OSS/IAM/生产级 Cube 与 M9 Production NO-GO 不在本次关闭范围。

## 0. 前置与需求冻结
- [x] 0.1 Accepted ADR/HC 和 G01–G20，领域/引擎/Tool Receipt 权威与依赖审查，无第二套调度器；OpenSpec Strict PASS。**证据**：docs/retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md。
- [x] 0.2 冻结合成 Python 两数相加任务、三 Runtime 节点、审批拒绝、Worker 真实终止/恢复、错误 Artifact 与外部账本样本；界定企业 OSS/IAM/生产非目标。**证据**：docs/retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md。

## 1. TDD 与集成开发
- [x] 1.1 测试先行构建版本/Artifact/Approval 合同：缺失实现 Red→PG 契约 12/12、独立字节夹具 2/2 Green；错误 Scope、并发、身份和未确认 Receipt 拒绝。**证据**：docs/retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md。
- [x] 1.2 Step 类型化 ArtifactRef 交接、Verifier 字节/摘要验证、WAITING_INPUT/APPROVAL 和原 Run 恢复；实际 PG 与 Native Worker 接管证据。**证据**：docs/retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md。
- [x] 1.3 真 Hatchet/三 Agent SDK 的规划→编码→验证 E2E，真实 LiteLLM 额外独立实测、原合成任务全链路及真实 Provider/Run/Receipt。**证据**：docs/retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md。
- [x] 1.4 审批拒绝零写入；实际 Worker SIGKILL/同 Run 恢复；UNKNOWN Receipt 对账；产物来源、官方 CI 和本次复盘。**证据**：docs/retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md。

## 2. 阶段 Gate 与复盘
- [x] 2.1 实际 Hatchet 执行正常/拒绝与 Worker A→B 原 Run/Provider 恢复全部 PASS；原 M6 CI 没有使用 SKIPPED 冒充通过。**证据**：docs/retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md。
- [x] 2.2 Red/Green、故障根因与幂等修复、唯一领域事实权威、真正外部测试账本和范围边界记录到正式复盘/Backlog。**证据**：docs/retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md。
- [x] 2.3 PR #95 原代码官方 Native PG/Hatchet/3 SDK/架构 CI SUCCESS，接受原始范围限界并归档；**归档/状态文档最终 Head CI 仍为合并门禁**。**证据**：docs/retrospectives/DEV_M6_FINAL_CLOSEOUT_20261014.md。