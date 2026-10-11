# DEV-M8 · 外部消费者集成边界

> 状态：**EXTERNAL OWNER / NOT IMPLEMENTED IN HARNESS**。业务消费者拥有独立、受控的私有工程；本开源 Harness 仓库只维护通用服务合同。

## 分工与禁止事项

- 私有应用源码、内部接口、数据结构、业务迁移映射、企业仓库地址、系统运行态及本地工作路径不得纳入 Agent Harness Platform 仓库。
- 应用通过正式版本化 Harness Public Application API/SDK 单向依赖 Harness；Harness 不导入业务消费者代码或业务数据库表。
- 外部应用实施/灰度/兼容/验收任务在独立私有项目中管理，不与 Harness 领域内核混合。

## 本仓库仅追踪通用接入合同
- [ ] 1.1 按 DEV-M7 明确公共 Conversation/Turn/Run/Event API 的版本化边界及鉴权条件。
- [ ] 1.2 对消费者协议进行抽象契约测试：隔离、幂等、SSE 续传、取消、ArtifactRef，不引入任何私有业务数据。
- [ ] 1.3 公共服务支持通用外部消费者后，完成架构 CI 与合同测试复盘；外部消费者的实际迁移在其私有仓库另行验收。
