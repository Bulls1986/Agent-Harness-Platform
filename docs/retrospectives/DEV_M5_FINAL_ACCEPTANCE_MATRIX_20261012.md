# DEV-M5 · 真实执行门禁与阶段边界核验（2026-10-12）

## 验收定义

本阶段是企业内部 Harness 的 **Cube Sandbox + OpenCode Coding Guest 集成阶段**，不是生产 100 Active Runs、企业 IAM、OCI 供应链证明或远端业务系统 Receipt 治理。任何 PASS 仅覆盖下列明确的真实场景和权限边界；不存在“OpenCode 任意 Tool 无条件安全执行”的声明。

### 正常路径：保留原 Guest 的任务级恢复

真实 Hatchet Worker A 在同一 Run/Workflow 操作 Native Cube Guest 和 OpenCode Session；操作完结并取得 Guest 终态回执后 A 被 OS SIGKILL，独立 B 通过原生 Hatchet Retry、PG Fencing Epoch 7→8 重连**同一 Native Sandbox、Native OpenCode Session、原文件和 Git/VCS 数据**。旧 Owner 与错误 Scope 拒绝；B 后续 Native Shell/Files/Git 操作结束后，两笔 PG Effect Receipt 全部 CONFIRMED、零笔 DISPATCHED，Destroy ACK RELEASED。实测 Run m5-joint-02d6561f68064dadb46555eeb486756c、Sandbox e5427b7efa6e4ec09f8663f82390a234、OS A -9/B Retry=1，脚本退出 0。更早的独立 Inspector HTTP → 真实 Hatchet/PG/Cube 执行和重启 Evidence GET 另有 B.3b 实测。

### 不确定路径：没有安全续跑资格的隔离恢复

OpenCode Guest Shell 已实际开始执行，Native HTTP ACK 超时/未知且 PG Effect 为 DISPATCHED；Lease 过期后 B **不得**接管原 Guest、重复 Shell 或错误宣称完成。可信恢复器验证原 Scope/Workspace/Environment 与原生 Provider 身份，销毁**整个原 MicroVM**（包括其中的在途进程），只有 Destroy ACK 才将 Binding 标为 RELEASED，并在同一 PG 事务把父 Run 标为 **BLOCKED_UNKNOWN**、保留外部工具 Effect 为 UNKNOWN，永远不能恢复已销毁的 Native Session。新 Run m5-containment-0fffcad2d54c4b678b8e2c89ee222ace、Sandbox 5234d0fc62a748e9af9a5e15704391c1，真实 Provider List 中原 Sandbox 不存在，/health sandboxes=0，退出 0。

这是一条明确的**失败终态与资源隔离**，不是幂等重放、外部副作用回滚、非纯业务完成，也不代表 Operator 可绕过 MCP 治理。生产业务层如何对账外部副作用必须由已授权 Tool Receipt Owner 完成；没有可信回执不得进入下一阶段继续执行。

### 合同/回归

- 真实 PostgreSQL 24/24：Lease、Owner、Epoch、Scope/Environment/Workspace、Create ACK-loss、Native ID/Metadata 复核、Pending Effect 接管阻断、Destroy ACK UNKNOWN、已销毁父 Run 终态、Non-PURE 完成保护。所有 PG 测试都在实际连接的 PostgreSQL 环境执行，**无 SKIPPED**。
- M5 单测 41/41：OpenCode v2 public API 路由、Native Session Envelope、跨路径/命令拒绝、未完成 Guest 文件/终态标记不算已确认、模型-only 零 Sandbox 合同。
- 真实 Cube SDK model-only Run 前后 Provider Inventory 0→0；OpenCode Guest Native public HTTP Shell/Files/VCS 在真实 MicroVM 内验证，无 Host Shell 兜底。
- OpenSpec Strict、Architecture Guard 与 GitHub PR Head 的架构/PG/Inspector 三条常规 CI 作为工程合入门禁；真实 Cube Workflow 在独立获授权 Linux 环境执行，不能用没有 Cube 的普通 CI 冒充。

## 架构审查与不扩大承诺

保持 Harness PG Domain Facts、Hatchet Native History、Cube MicroVM 生命周期与 OpenCode Session 的 Owner 分离；一个 Session 绑定原 Native Sandbox，冻结模板和 PG Scope/Workspace/Environment 标识，不用新 Cube 冒充旧 Workspace，也不保留每会话常驻 Agent 进程。模型-only 不分配 Sandbox，权限在 SDK 调用之前校验。Provider 增补字段允许存在，但必需的 Harness Metadata 与原 PG 绑定逐字段相等；错误原生身份一律 UNKNOWN。

本阶段未实现正式企业身份治理、任意 Git Revision 的 OCI 级内容可复现、外部系统非幂等 Receipt 的自动对账、销毁后原 Native Session 无损恢复或跨宿主高可用。**这些能力不得被本阶段验收报告写成 PASS**，不阻止在当前受控 POC 范围内把“正常接管”和“异常隔离/终态阻断”分别验收；生产准入仍为 NO-GO。

工程合并前须复核 PR Head 三条标准 CI 和 Git 变更内容；合并后才能将 OpenSpec 正式归档。任何检查失败都应回到 OPEN，而不是只改 Markdown 勾选状态。
