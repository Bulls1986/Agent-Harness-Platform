# DEV-M5 阶段收口复核 · 2026-10-12

## 结论

**DEV-M5 ACTIVE / NOT READY TO ARCHIVE。** 本轮对 OpenSpec 原有 8 项 OPEN 进行逐项验收：0.1、0.2、1.1、1.4 可按明确的合成样本、测试与实际 Provider 证据完成；2.2 已追加根因、安全缺陷和待办复盘；1.3 完整 OpenCode Guest 以及依赖 1.3 的 2.1 阶段 Gate、2.3 合并归档依然 OPEN。

## 0.1 / 0.2：架构约束、环境与样本冻结

- 权威来源：Accepted ADR / docs/ARCHITECTURE.md / docs/references/README.md / HC-01/02/03 / docs/ARCHITECTURE_GUARDRAILS.md G01–G20。关键检查：G01/02 领域事实及控制面；G03/04 SDK 独立；G05 零 Sandbox；G06 Scope、Owner、Capability、Lease/Fencing；G07/08 UNKNOWN 与 Receipt；G09 冻结环境；G10 证据大对象 OSS；G12 不代管 IAM/MCP/备份；G14 Git 权威；G19/20 真实 Gate 与 POC 层级。
- 代表性失败机制：Worker A 真实 SIGKILL → B Retry / PG Fencing；Cube Create ACK 丢失、Native Metadata Correlation 对账；跨 Scope / Workspace、过期 Owner/Epoch；错误 Native Connect ID、Destroy ACK UNKNOWN；模型-only 0 Sandbox；OpenCode Guest 未真实路由时禁止 Host Shell 兜底。
- 全部使用合成数据，不传任何企业消费者的业务资产、客户内容或凭证。实验室环境：WSL Ubuntu、CubeSandbox SDK 0.7.0 + READY 模板、隔离 PostgreSQL 16、Hatchet SDK 1.42.1。开发机器恢复不是生产 OCI Digest/HA 的证明；Harness 不承担外部 IAM、备份等职责。

## 1.1：TDD 暴露并修复安全漏洞

此前 AgentRuntimeDispatcher 只检查调用方声明的 capabilities，未对照原始操作名。因此 shell.exec / files.write / git.status 如果伪报为 model，可能进入拥有该操作的 Adapter。新增 tests/test_m5_runtime_admission_security.py 先 RED（3 种不匹配 + 未知能力没有被拒），修复 poc/runtime_spi/contract.py：Native shell/files/git 操作名必须声明对应能力；未知/空能力在 Adapter 之前拒绝。新增 6/6 GREEN，原可信 Execution Gate 6/6 GREEN，Runtime SPI 无 Sandbox / 错 Scope / Cancel UNKNOWN 自检 PASS。

真实 PostgreSQL 16 运行 poc.sandbox.test_cube_binding_pg **15/15 PASS**：旧 Owner、Lease、Scope、Fencing、并发 B/C、Create ACK 丢失、Native Identity 验证、Destroy UNKNOWN 等合同不允许 Host 兜底或重复创建。纯 SPI 测试没有证明在途 Guest 级立即撤销，不能偷换为 Guest Fencing PASS。

## 1.4：模型-only 0 Sandbox 与资源释放

新增 poc/sandbox/verify_zero_sandbox_live.py：对真实 Cube SDK Sandbox.list 前后盘点，执行确定性的 model.run 且 sandbox=None，实际得到 PASS_REAL_PROVIDER_ZERO_SANDBOX、sandbox_allocations=0、existing_sandboxes=0、model_only_dispatches=1。单位合同 3/3 GREEN，之前真实 B03/PG+Cube Gate 还确认 Destroy ACK=RELEASED、Cube 最终 0 个 Sandbox、旧 Owner/错 Scope 不可访问。这证明特定真实 Provider 的零分配/释放，不是生产 100 Active Runs 或所有 Tool 类型的容量证明。

## 1.3：OpenCode Guest 实测及目前阻塞

新增 poc/sandbox/verify_opencode_guest_prerequisites.py 实际探测 Cube Guest，而非宿主。首次真实 MicroVM 9ecb2803143b4bafb8dc2f3b85726f87 返回 sh=true、git=true、opencode=true、node=false、npm=false，Destroy ACK 成功；最初误将 node/npm 视作必要条件，测试返回 2。后纠正：Standalone OpenCode 不需要外露 Node/npm，以 Guest 内 opencode --version 的真实退出码和输出作为启动条件；新增 4/4 探针合同通过，**修正后的真实 Guest 重跑尚无可计入 PASS**。

当前 OpenCodeV2SessionAdapter 仍只支持 session.prepare；model.run 显式 Unsupported，Shell/Files/Git 无贯通 OpenCode Native Tool → Cube Guest → PG Scope/Fencing/Workspace、物理 Worker 接管的完成证据。不能把 WSL Host 上的 OpenCode 或已完成的普通 Cube 文件读写当成 OpenCode Tool 全链。Guest 在途执行强制撤销、镜像 Digest/Worktree 冻结也需继续验收。

## 根因复盘与 Exit Gate

之前已解决 WSL 关机、Docker Compose V1/V2、Cube Native Connect Identity、Destroy ACK、Hatchet Context 注册及 Worker 日志问题；本次新增 Operation/Capability 错配安全缺陷的 Red→Green 与合成场景。不能因多个分项 PASS 就宣布整个 M5 完成。

仍 OPEN：1.3（完整 OpenCode Guest、Guest in-flight fencing、真实 Shell/Files/Git）、2.1（全部适用真实正/拒绝/故障路径，无 SKIPPED）、2.3（审查、合并与 OpenSpec 归档）。M9 的 IAM、跨宿主 HA、OCI 供应链、100 Active Runs 是另一个生产准入阶段，不属于 POC 可擅自免除的门禁。
