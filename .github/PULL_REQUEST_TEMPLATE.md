## 范围 / Owner

改动类型：[ ] 文档 / POC [ ] Adapter / Recipe [ ] Domain / SPI [ ] 安全 / 恢复 [ ] 技术或部署选型 [ ] 存量 PDLC 迁移

业务目的与 Owner（Harness / 旧 PDLC / 企业外围平台）：

## 架构核对（必填）

- 影响的 [Architecture Guardrails Gxx](../docs/ARCHITECTURE_GUARDRAILS.md) 编号：
- [ ] Accepted Domain / State / Version / Event 语义不变；若有变化请提供 ADR/Contract 链接：
- [ ] AgentRuntime / Process / Sandbox / Model 独立；Provider 仅止于 Adapter（不适用说明）：
- [ ] 检查 Scope、Lease、Credential、Sandbox、非幂等 Tool、UNKNOWN → Reconciliation：
- [ ] 检查 Task Facts / OSS ArtifactRef / RecoveryPoint / 冻结版本与回滚：
- [ ] 检查存量 PDLC API/历史/资产与同一副作用单 Writer：

## 验证和风险（必填）

- 成功路径 + 拒绝/故障路径测试、命令及 CI 链接：
- 证据范围：[ ] Mock [ ] Offline [ ] Docker [ ] Cube/Live [ ] E2E [ ] Production
- 尚未验证、Unsupported 与已知失败：
- 迁移/回滚与不适用说明：

> Domain、公共 SPI、恢复/授权/副作用、默认技术栈或生产拓扑变更必须先进行 Architecture Review，违反 Accepted 时先修改 ADR；纯导航变更可说明无需 ADR。