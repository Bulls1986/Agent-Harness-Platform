# DEV-SBX · Cube Sandbox Management V1（M9 前独立功能补齐）

## Why

M5 已完成原范围内真实 Cube Worker/Execution 可信绑定，但 `NativeCubeTransport` 使用全局 `CUBE_TEMPLATE_ID`，且原 M5 `harness_cube_binding` 只能绑定已运行的 Run；M7 版本化公共 API 未提供 Template 管理、预分配、Session Attach/初始化与命令执行操作合同。上层消费者无法在 Session 进入 Agent Run 前独立创建并初始化不同 Cube 沙箱。

## What changes（冻结）

1. 使用 **Cube 原生 Dockerfile/OCI/Template/Native 创建参数**；透传允许的 Cube 管理能力，不新增 Harness Template DSL/Registry。
2. **Create**：受控创建 Cube Sandbox、可选 `onCreate` 原生命令、独立 Operation/幂等/结果核对。
3. **Attach**：将既有 Cube 实例安全绑定 Session、可选 `onAttach` 原生命令、重连不重复初始化；与 M5 的执行期绑定分离。
4. **Execute**：已有 Binding 下受控调用 Cube Commands/必要 Files、结果状态/超时/输出；保留现有 M5 Execution Lease/Fencing。
5. 受控查询、解绑、暂停/恢复/释放；API/OpenAPI、实际本机 Cube + PostgreSQL 集成验证，负例/复盘。

## Non-goals

不引入项目/Skills/子 Agent 定义或资源解释；不构建 OCI/SBOM/镜像发布平台、模板 DSL、Harness Template Registry、第二 Provider、Sandbox Pool/调度器、任意身份直通 CubeMaster、完整 Web 管理台；不开展 M9 生产容量/跨宿主/真机部署/回退。业务消费者不成为交付前置，不进入公开仓库。

## Contract & dependencies

[正式冻结合同](../../../docs/references/CUBE_SANDBOX_MANAGEMENT_V1_20261014.md)；Accepted G01–G20、ADR-031、HC-03、Workspace/Git、Registry/Version、Identity/Policy 保持不变。用真实 Cube SDK/CLI 支持的操作、字段及版本为依据，不能臆造 Provider 接口。M5/M7 保留原有 CLOSED，M9 PLANNED/Production NO-GO。

## Status

**Scope FROZEN / implementation NOT STARTED。** 只有 M0 文档冻结可验收；M1–M4 的代码、原生实测、CI 和 OpenSpec closeout 尚未开始，不能记为 PASS。
