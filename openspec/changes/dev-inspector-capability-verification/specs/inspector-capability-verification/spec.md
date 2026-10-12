# Inspector · 能力验证 Tab

## ADDED Requirements

### Requirement: Inspector SHALL add exactly one capability tab

保留既有「双 Agent 演示」的真实 Run、节点、历史、SSE 与最终结果，在同一页面另加一个「能力验证」Tab。新的 Tab SHALL 逐项说明使用场景、证明能力、实际执行步骤、必需验收证据和无法证明的范围。

#### Scenario: 查看四种 Harness 能力
- **WHEN** 评审者切换到能力验证 Tab
- **THEN** 看到双 Agent 跨 SDK 接力、Cube Workspace 恢复、Worker 物理故障接管和非幂等 Tool Receipt 四种独立场景的用途、证明标准、执行步骤与限制，不需理解原始 JSON 才能解释场景

### Requirement: Persisted evidence MUST NOT be represented as actual external proof

证据查询仅从 Harness PostgreSQL 读取白名单事件、Bound Provider 和可选 Cube/Tool 领域事实。模型输入、Token、外部操作和业务秘密 SHALL NOT 在新接口返回；缺失事实 MUST NOT 被补造为通过。未经独立真实执行验证，`verified` MUST be `false`，Status 保持只读事实。

#### Scenario: PG 已持久化 Cube Binding，但没有原生 Guest 证明
- **WHEN** 某 Run 拥有 Sandbox ID、WorkspaceRef、Owner Epoch 与 Binding Confirmed 事件
- **THEN** Inspector 可显示这些观察证据，但不能宣称 Cube Guest 内容一致、物理 Worker SIGKILL/Retry 或完整 M5 Gate PASS

#### Scenario: 不存在 Run 或 PG 查询不可用
- **WHEN** 查询未知 Run、不合法 ID 或持久化服务异常
- **THEN** 返回明确 404/422/503，而不是返回模拟事实或空 PASS

### Requirement: No privileged demo execution from an unauthenticated inspector

Cube/物理故障/外部非幂等场景在未接入明确授权的可信 Runner 前 SHALL remain read-only。原本双 Agent 演示创建 Run 的 HTTP 合同 SHALL remain unchanged。

#### Scenario: 试图通过新 Tab 触发物理故障
- **WHEN** 评审者打开尚未完成整合的物理 Worker 场景
- **THEN** 页面解释所需证据和当前限制，不提供无认证的 Host SIGKILL 或假运行结果

### Requirement: Trusted physical demonstration MUST be opt-in, authenticated and independently evidenced

在本地受控 Linux 环境中，经服务端显式启用的 worker-takeover 固定场景 MAY 接受操作员认证的请求。此入口 MUST NOT 接受任意 Shell 命令、沙箱参数或未经授权的跨来源请求；未启用时仍为只读。响应 MUST 首先是未验证的执行标识，终态 MUST 来自可信运行器的真实 OS、Hatchet、PG、Cube Guest/Destroy 关联证据。执行中断或回执不明时 MUST BLOCK UNKNOWN，不得盲目重发。服务端 Token 与日志 MUST NOT 返回客户端。

#### Scenario: 缺失授权或运行器未启用
- **WHEN** 浏览器试图无凭证、错误凭证或跨来源启动特权场景
- **THEN** 可信后端拒绝执行，默认 Inspector 继续只读，Catalog 不泄露任何凭证

#### Scenario: 真实联合执行尚无完整证明
- **WHEN** 受控运行器启动但 Native B03 失败、证据缺失或服务中断
- **THEN** 不设置 Verified/PASS，保留证据 ID 与失败或 UNKNOWN，要求运维对账；PG Binding 不能替代真实 Guest/物理故障证据
