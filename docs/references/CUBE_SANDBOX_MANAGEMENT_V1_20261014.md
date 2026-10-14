# Cube Sandbox Management V1 · 范围冻结与公共接口合同

**状态：SCOPE FROZEN（2026-10-14）；IMPLEMENTATION PLANNED / Production NO-GO。** 范围由用户明确确认；不表示任何新 API 已交付或真实 Cube 集成已验收。正式工作项：[DEV-SBX OpenSpec](../../openspec/changes/dev-sbx-cube-sandbox-management-v1/)；[里程碑](../DEVELOPMENT_MILESTONES.md)。

## 1. Owner 和边界

- **CubeSandbox 是本期唯一具体 Sandbox Provider**：Template 采用 Cube 原生 Dockerfile / OCI Image / Native Template、Alias、Template ID、构建/提交、原生实例 create/connect/pause/resume/kill、Files/Commands；既不设计 Harness SandboxDefinition/Registry/DSL，也不包装一套通用镜像构建平台。
- **Harness 是服务端受控入口**：对 Cube 操作提供必要的公共 API、可信授权及 Scope、操作审计/幂等/结果查询、Session↔Sandbox 绑定；正式执行复用 M5 的 ExecutionContext/Lease/Fencing，不重新造第二套执行引擎、Scheduler 或生命周期管理器。
- **上层消费者**：决定 Template、初始化命令、资源/代码仓库、技能/子 Agent/工作方法。Harness 只执行已授权的 Shell/Files 操作，不解析“项目/技能”语义。不得引入私有消费者代码、地址、资产或内部配置。
- **已有架构继续有效**：HC-03、G01–G20、ADR-031、Workspace ≠ Sandbox、Run ≠ Session。Cube 特有 API 是 Provider 管理面入口，不改变当前通用 SandboxProvider SPI 的既有可替换边界；本期不开发第二 Provider。

## 2. 模板的定义与管理：使用 Cube 原生

- 模板在 Cube 按原生 Dockerfile / OCI Image / Native Template 工作流构建、管理；通用 apt/pip/npm/git/java/node/opencode 等工具直接在 OCI 构建层安装。Harness **不**提供另一个 packages/commands YAML 或重新解析 Dockerfile。
- 受特权保护的 Cube Template 创建、列表、详情、状态、Alias/提交/删除可以暴露对应原生操作；请求和响应尽量保留选定且锁定版本的 Cube SDK/API 字段与语义，**但不等同无鉴权的任意路径反向代理**。Provider 暂不支持的原生操作必须明确返回 UNSUPPORTED，不伪造成功。
- Cube Template Alias 属于可变定位；Create 时解析并记录实际 **Native Template ID** 以及 Provider 可获得的 immutable image/environment digest。Run 的环境版本/Workspace 基线按既有 HC-03/Registry 合同冻结；不能把 alias/latest 当成最终执行身份。
- 模板创建/删除、特权网络/Volume/Host Mount 等管理操作默认不授予普通 Session 使用者。凭证由外部可信身份/Secret 服务管理；不得写入镜像、长期环境变量、命令审计、Prompt 或公开仓库。

## 3. Create / Attach / Execute · 三阶段 API（拟定路径）

### A. Create — Sandbox Instance

`POST /api/v1/sandboxes`（要求 Idempotency-Key）

```json
{
  "cube": {
    "template": "coding-base",
    "timeout": 3600
  },
  "onCreate": {
    "commands": [
      { "command": "git --version", "cwd": "/workspace", "timeoutSeconds": 30 }
    ]
  }
}
```

- `cube` 内仅透传部署版本支持、且当前 Policy 允许的 **Cube 原生 create 参数**；上例仅展示常见字段，不代表完整字段白名单。后续字段按 Cube Native API/SDK 版本验收，不自行发明 Cube 参数。
- Cube 创建成功后通过原生 Commands 执行可选 `onCreate`；需要 Shell/Files 的模板必须具备可用 Guest Agent（如 envd），否则 fail closed。
- 202 返回 `sandboxRef`、`operationId`、状态，创建/初始化完成后才可 Ready；超时或 Native ACK 不明进入 `UNKNOWN/RECONCILING`，不得再次创建同一逻辑实例。
- 不将 Sandbox Instance 强行绑定到 Run：允许 **Session/Run 创建之前预分配**，与 M5 `harness_cube_binding` 的 active Run 约束独立。

### B. Attach — Session 逻辑绑定

`POST /api/v1/sandbox-bindings`（要求 Idempotency-Key）

```json
{
  "sandboxRef": "sbx-demo",
  "sessionRef": "session-demo",
  "onAttach": {
    "commands": [
      { "command": "git fetch origin main", "cwd": "/workspace/app", "timeoutSeconds": 120 }
    ]
  }
}
```

- Harness 基于受信任 Gateway/Policy **验证目标 Session 与 Sandbox 同 Scope**；`sessionRef` 为经服务端绑定/解析的引用，不信任用户自报权限、裸 Cube ID、HTTP Header 等。
- `onAttach` 作为**受控初始化动作**，不得以尚不存在的 Run 伪造 M5 Execution。另发短期、限定 Scope/Sandbox/Command 的 Initialization Permit；普通 Attach **本身不赋予 Shell 权限**。
- 初始化成功才确认绑定可使用。同一 `bindingId` reconnect 不重跑脚本；上层显式刷新代码或重新初始化应创建**新的、经授权的 Operation**。
- V1 默认 **一个可写 Sandbox 同时只绑定一个 Session**；同 Session 重连可复用；不同 Session 或 Scope 禁止直接复用已有可写实例。此保守策略不改变 HC-03 对未来更复杂合法复用的原则。
- 宿主目录/Volume Mount 属于 Cube 原生**创建时**配置，**Session Attach 是逻辑关联**，不等于给运行中 MicroVM 热挂载新 Volume。
- `git fetch` 只取回远端引用；切换 checkout/pull/覆盖未提交工作区必须由上层明确要求。执行 Run 前冻结确定 Revision Set。

### C. Execute — 通过授权 Binding 执行

`POST /api/v1/sandbox-bindings/{bindingId}/commands`（要求 Idempotency-Key）

```json
{
  "command": "npm test",
  "cwd": "/workspace/app",
  "timeoutSeconds": 300
}
```

- 使用 Cube 原生 `commands.run`（后续受限 Files 能力沿用 Cube Files SDK），保留 exit code、stdout/stderr、超时语义，长命令可异步返回 Operation ID；限制输出体积，长期日志通过受控引用获取。
- HTTP 调用主体必须持有当前有效、**服务端校验的命令操作授权**，不因知道 `bindingId` 即拥有任意 Shell；正式 Agent Run 仍必须通过现有 M5 Execution Permit/Lease/Fencing；预 Run 用户操作须经专用受限 Authorization/Policy 决议。
- 不能把原生命令经共享 Host Shell 执行，也不能在 Cube 不可用时回退宿主进程。

### D. 仅限必要辅助端点

- `GET /api/v1/sandboxes/{sandboxRef}`：Provider 原生状态 + Harness 受控实例引用/关联；Native pause/resume/release/kill 对应受控请求，尊重 Cube 实际支持的语义。
- `GET /api/v1/sandbox-operations/{operationId}`：创建、初始化、执行、释放的进度/结果/UNKNOWN。
- `GET /api/v1/sandbox-bindings/{bindingId}`，`DELETE /api/v1/sandbox-bindings/{bindingId}`：查询/解绑；解绑≠销毁。
- Cube Template 原生管理 API：单独管理员权限域，契约随实机能力确认并记 OpenAPI；**不构造未经证实的原生 SDK 调用签名**。

## 4. 一致性、安全、持久性硬约束

1. **Operation 最小持久事实**：operation_id / idempotency_key / caller-scope / sandbox_ref / binding_ref / native correlation / intended action / state / result ref；与 Native ACK 不确定窗口对账。UNKNOWN 命令禁止盲重放，不能保证外部任意 Shell 副作用 exactly-once。
2. **两层权限**：Template/Sandbox 管理权限与 Session/Run 命令权限分离；初始化许可短期绑定资源/Scope，普通绑定没有执行权；现有 M5 Fencing 保护受控运行期操作。
3. **隔离**：跨 Session、跨 Scope、已释放绑定、过期 owner/fencing、未完成初始化均拒绝；共享 Volume/宿主 Mount/网络权限遵守独立 Policy，不能假定不同 Sandbox ID 天然隔离全部外部资源。
4. **版本与恢复**：记录 resolved Template ID / environment digest 和对应 WorkspaceRef；重连只读已有事实，不能使用空 Workspace 冒充恢复。Pause/Resume 与 Kill 的实际数据保留语义由 Cube 原生能力和卷策略决定；Sandbox 生命周期≠Workspace 持久化。
5. **日志与凭据**：不将 Git Token、SSO Secret/环境凭据写入日志、Shell 明文响应、模板或公开源码。采用外部凭据受控注入；不扩建 Secret Manager。
6. **操作退出门禁**：所有新端点需真实鉴权/Scope 拒绝测试、Idempotency/UNKNOWN、TDD、官方 CI 与本地真实 Cube E2E。测试 SKIPPED 不算 PASS。M9 生产容量/跨宿主/部署/回滚仍 NO-GO。

## 5. 最小验收矩阵

| 场景 | 必须证明 |
|---|---|
| Cube Native Template → Sandbox | 不引入新 DSL/Registry，选定原生 Template 创建、结果追踪 |
| Create + onCreate | 真 Cube Guest 内执行命令，成功 Ready，失败不误标 Ready |
| Attach + onAttach | 同 Scope Session Git clone/fetch、成功后才绑定 |
| Reconnect | 同 Session 重连文件保留、不重复初始化 |
| Execute | 受控命令 exit code/stdout/stderr，长命令超时及结果查询 |
| Authorization | 另一 Session/Scope/未经授权 Shell/管理员 API 均拒绝 |
| ACK-loss / crash | 幂等重复与 Native 结果未知不二次创建或重放 Shell |
| Lifecycle | 解除绑定、暂停/恢复/释放与 Workspace 保留语义正确 |
| No-sandbox | 仅模型 Run 不分配 Cube（HC-03 回归） |

**延期/排除**：可视化管理台、Harness SandboxDefinition/Template Registry、DSL、工具包安装语法、Agent/Skill/项目资源管理、Pool 自建调度、热挂载 Volume 承诺、第二 Provider 实现、生产部署/100 Active Runs/跨宿主安全认证。见 [M9 OpenSpec](../../openspec/changes/dev-m9-delivery-readiness/)。
