# DEV-SBX V1 · Design（冻结，不是已实现）

## 分层与事实归属

Consumer (identity + desired Cube template/commands)
→ authorized Harness versioned Sandbox API (Policy, scoped Permit, durable Operation / logical Binding)
→ Cube native Template/Sandbox SDK/API (actual create/connect/files/commands/pause/kill).

Cube 持有原生 Template、Sandbox 状态和快照/Guest；Harness 只持有控制入口的授权、操作幂等/核对事实及 Session/Execution Binding。执行期间遵守 M5 的 current ExecutionContext、Lease/Fencing 和 Native state；不将 Sandbox 或 Session 合并进 Run 领域实体。上层决定 Git/Skill/Agent 文件的内容，不需要 Harness 解释。

## Native-first 接入

- Template 创建采用官方 Cube Dockerfile/OCI + 原生 Template 管理语义；Harness 不维护独立的 Definition/version/DSL。特权 Template 管理单独授权。
- Instance Create 直接传可用且授权的 `cube` 参数；运行中保存 native sandbox_id、resolved native template_id/可用环境摘要/Scope/Operation correlation。将当前全局 `CUBE_TEMPLATE_ID` 限定为已有旧测试路径，新增公共创建链不可依赖单一全局模板。
- 本期不承诺未由实际 Cube SDK/API 验证的 CLI/HTTP 签名、热挂载 Volume、脚本精确一次执行或任意自定义环境参数。

## Create → Attach → Execute

- Create：先持久化 idempotent Operation/immutable request digest，再触发 Cube 原生 create；`onCreate` 是创建成功后的受控 guest command；Native ACK 丢失时必须对账，不再次 create。
- Attach：必须有已存在且完成就绪检查的 Sandbox；校验经 Gateway 认证的 Session + Policy + Scope；获取仅允许该 Sandbox 的短期 Initialization Permit，执行 `onAttach`；成功时才标记 active Binding。相同 Binding reconnect 只连接不重跑，显式 refresh 是新的授权 Operation；失败/UNKNOWN 不可用。
- Execute：独立的受限命令授权，`bindingId` 只表示关联，不表示可执行权限；正式 Agent 执行通过 HC-03 M5 Execution Permit/Fencing。文件与命令都运行 Cube Guest，绝不回退 Host。
- 默认一个可写 Sandbox 同时只有一个有效 Session Binding（保守 V1），同一 Session 重连；不同 Scope/Session 访问失败关闭。
- Unbind/Release：绑定解除≠Kill；活跃 Run/恢复依赖必须先检查；真实暂停/恢复、Volumes/Workspace 状态遵守 Cube/Workspace 原生语义。

## Operation / errors

持久 Operation 记录最小 ID、幂等键、Scope、请求摘要、目标、Native correlation、状态和结果引用。状态 `PENDING/RUNNING/SUCCEEDED/FAILED/UNKNOWN` 是 Harness 操作观测，**不是第二套 Cube 机器状态**。相同键+相同请求只能复用原结果；相同键+不同请求 `409`；Native 未知需 `RECONCILING`，不得盲重放 command。401/403 未授权，404 不泄漏跨 Scope 资源，409 状态冲突，422 不支持的原生参数，503 Provider 不可达（精确 HTTP 映射按实现前 API Schema 锁定）。

## Verification-first

M0 仅规范、路径导航、OpenSpec 严格校验；M1 真 Cube create/onCreate/ACK-loss；M2 Session authorization、Git clone/fetch/reconnect/cross-session 负例；M3 Command/Files 输出、timeout、unknown, cancel/release/pause & no-sandbox；M4 本机真实 Cube + PG + API E2E、最新 Head CI、OpenAPI、复盘与闭环。

原则：TDD、失败注入先行；不因本机真实 Cube PASS 宣称跨宿主、企业 IdP、生产安全或容量已验收。
