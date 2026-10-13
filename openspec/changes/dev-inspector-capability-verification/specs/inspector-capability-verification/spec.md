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
