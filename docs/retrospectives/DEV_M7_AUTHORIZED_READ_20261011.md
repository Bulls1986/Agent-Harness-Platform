# DEV-M7 授权读取子切片复盘（2026-10-11）

## 目标与边界

为未来生产统一 API 形成一个可验证的只读授权入口，避免将当前无鉴权的 Local Inspector 意外当作面向用户的正式 API。

- 本次变更归属：Protocol/API Access Boundary；不修改 Harness Run 状态机、Hatchet、SDK、Sandbox、外部 IAM/OSS。
- 受影响的护栏：G01（Run 业务事实权威）、G02（控制/执行分离）、G10（事实与 Payload 分离）、G11（外部认证/授权）、G12（不重建 IAM）、G15（稳定事件协议）、G20（证据层级）。
- Accepted ADR/HC 不修改，既有 Local Inspector 调试用途不变。

## Red → Green 证据

1. Red：`python -m unittest poc.platform_access.test_authorized_reads -v`；因 `authorized_reads` 尚不存在，导入失败（符合测试先行）。
2. Green：同一命令运行 5 项成功，增加 fail-closed 反例后运行 8 项成功。
3. 测试包括合法 Run/事件游标、越项目拒绝、权限撤销重验、无身份和伪造 Header、不存在与未授权响应一致、非法游标、未显式允许不放行、Run ID 绑定不一致。

## 失败根因与措施

既有 Inspector 为本地 POC，缺少正式入口所需的可信身份和资源授权边界。如果为求复用而直接暴露 `/api/runs`，可能把调试访问范围错误放大。

本次通过独立 `create_read_app` Factory 使三项依赖在装配时强制提供：外部身份解析、平台 Run 绑定读取、当前 Policy Decision。身份不能由 HTTP Header 直接接收；项目不匹配在任何快照/事件载荷读取前返回一致 404。策略失败不降级为匿名。

## 未通过/未验证 Gate

- 这仍是 Memory Reader 的 HTTP Unit/Contract 测试；真实 PostgreSQL、Gateway 认证与现网 Policy Adapter 均 **NOT_TESTED**。
- SSE 订阅中途撤权、OSS ArtifactRef、Conversation/Turn 关系、实际 UI、真实模型/Tool/Approval 的协议映射 **OPEN**。
- 只有 GitHub Actions 运行真正完成并得到绿色证据后才可声明 CI PASS；新工作流文件本身不等于 CI PASS。
- 不对 DEV-M7 的 OpenSpec 全阶段、生产部署或与任何外部系统的迁移作关闭判断。

## 经验与下一步

可复用原则：调试 API 与正式访问入口物理分离；拒绝在读取敏感 Payload 前发生；授权由当前 Policy 决定，不以 Run 创建时历史 Claims 永久放行。下一切片优先将 `RunReader.binding` 接入真实 PG、关联受信任的 Gateway 测试主体，再实施 SSE 游标与事件访问隔离；完成后补真实故障/权限 E2E。
