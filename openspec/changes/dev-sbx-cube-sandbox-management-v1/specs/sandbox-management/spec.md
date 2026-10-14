# DEV-SBX Sandbox Management V1 · Requirements

## ADDED Requirements

### Requirement: 原生 Cube 模板定义和管理

Harness SHALL retain Cube native Dockerfile/OCI/Template semantics and SHALL NOT introduce an alternative SandboxDefinition/Template Registry/DSL. Administrative Template operations MUST use independently authorized native-supported capabilities, preserving immutable template binding at instance creation.

#### Scenario: 已发布 Template 创建 Sandbox
- **WHEN** an authorized caller selects a valid Cube Template and requests a sandbox
- **THEN** actual Cube creates it with the selected resolved native Template ID and native-supported parameters; Harness records an immutable correlation and does not fabricate a separate template lifecycle.

#### Scenario: 未授权或不支持的管理请求
- **WHEN** a session user requests privileged Template management or unsupported Cube parameters
- **THEN** the system rejects before Cube mutation without falling back to host execution or silently ignoring parameters.

### Requirement: Create 允许可选初始化且幂等

Harness SHALL expose a versioned Create API using native Cube creation parameters and optional onCreate guest commands. Persistent operation identity and idempotency MUST precede native effects; ambiguous provider outcomes MUST be reconciled before any retry.

#### Scenario: 真 Cube 创建并准备
- **WHEN** an authorized create request with onCreate is accepted
- **THEN** Cube creates an isolated instance, runs commands inside the guest, and the API exposes actual completion or failure via Operation lookup.

#### Scenario: Create ACK 丢失
- **WHEN** Cube may have committed create but the response was lost
- **THEN** the operation becomes UNKNOWN/RECONCILING; the same logical request MUST NOT allocate a second Cube sandbox without proof of absence.

### Requirement: Attach 是授权 Session 绑定，不是 Shell 授权

Harness SHALL support separate pre-Run Session binding and optional onAttach guest commands with scoped short-lived initialization permits; it MUST NOT fabricate a Run to satisfy the existing HC-03 execution contract. The same binding reconnect MUST NOT repeat initialization.

#### Scenario: 绑定且拉取代码
- **WHEN** an authorized Session attaches a READY sandbox and supplies a permitted Git command
- **THEN** the command executes in the Cube guest, completion is recorded, and Binding becomes usable only on successful initialization.

#### Scenario: 重连 / 跨 Session 越权
- **WHEN** the same Session reconnects an existing active Binding
- **THEN** no onAttach command is re-executed; when another Session/Scope attempts access, attachment and command execution are refused.

### Requirement: Execute 依赖实际执行资格

Harness SHALL support a versioned Execute command API with command result and operation tracking, but a Binding reference alone MUST NOT grant shell authority. Agent Run operations MUST continue to validate existing M5 Execution Lease/Fencing; all commands/files effects MUST occur inside Cube, never host fallback.

#### Scenario: 正确执行与输出
- **WHEN** a properly permitted command is issued for an active Binding
- **THEN** Cube executes it and the caller can query exit code, stdout/stderr within output limits and execution status.

#### Scenario: 过期 Owner 或不明副作用
- **WHEN** execution authorization is stale or a non-idempotent command outcome is UNKNOWN
- **THEN** the system rejects stale execution and does not blindly repeat the command; reconciliation or explicit failure is required.

### Requirement: Native 生命周期和 Workspace 分离

Harness SHALL expose only Cube-supported inspect/pause/resume/release functionality while preserving Session binding, valid active execution, and Workspace recovery semantics. It MUST NOT treat binding deletion or Sandbox kill as durable Workspace recovery.

#### Scenario: 安全解绑和资源释放
- **WHEN** a Session unbinds a Sandbox with no remaining active use or recovery obligation
- **THEN** it can be released according to provider policy; an active or protected Sandbox MUST NOT be silently destroyed.

#### Scenario: Sandbox 已销毁
- **WHEN** a Session later reconnects after the native Sandbox was killed
- **THEN** Harness returns a truthful unavailable/recovery result, not an empty Sandbox presented as the original Workspace.

### Requirement: 只有有证据的里程碑才能 CLOSED

The V1 milestone SHALL NOT be marked CLOSED without actual local Cube+PostgreSQL Create→Attach→Execute E2E, authorization negative tests, idempotency/UNKNOWN reconciliation tests, documented native capabilities and OpenAPI, latest-head CI and retrospective. DEV-M9 production approval remains separately PLANNED / NO-GO.

#### Scenario: 规划完成但真实验证缺失
- **WHEN** OpenSpec planning artifacts pass but real provider integration/negative tests are absent or SKIPPED
- **THEN** implementation tasks remain unchecked and the milestone cannot be represented as delivered.
