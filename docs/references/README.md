# 参考资料 / Discussion References

本目录用于记录 Agent Harness Platform 架构形成过程中的技术讨论、候选方案分析与背景资料。

> 这些文件是 **讨论记录 / 设计参考**，不是最终架构规范。正式决策以 `docs/ARCHITECTURE.md`、`docs/POC.md` 和后续 ADR 为准。

## 分类

1. [OpenAI Agent / Harness 能力梳理](OPENAI_AGENT_STACK.md)
2. [Harness Kernel 与可插拔组件抽象](HARNESS_COMPONENT_MODEL.md)
3. [Conversation / UI Protocol 讨论](CONVERSATION_PROTOCOL.md)
4. [框架与 Runtime 首轮技术比较](FRAMEWORK_LANDSCAPE.md)
5. [部署独立性与平台绑定风险](DEPLOYMENT_INDEPENDENCE.md)
6. [Control Plane / Data Plane 边界说明](CONTROL_DATA_PLANE.md)
7. [MAF Memory / Context 设计](MAF_MEMORY_MODEL.md)
8. [MAF 扩展性评估](MAF_EXTENSIBILITY.md)
9. [首轮方案架构匹配度估算](FIRST_ROUND_MATCH_ASSESSMENT.md)

## 使用原则

- 参考资料允许保留探索过程、候选方案和被否决思路。
- 正式架构文档只保留当前有效决策和接口边界。
- 任何引用到具体框架当前能力、许可证或托管方式的内容，在正式选型前必须重新核验。
- 当参考资料中的结论被 ADR 正式接受后，应在 ADR 中建立反向链接。
