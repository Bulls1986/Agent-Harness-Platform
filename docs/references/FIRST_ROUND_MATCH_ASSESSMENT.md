# 首轮方案架构匹配度估算

> 状态：POC 前架构估算，不是实测结论  
> 时间基线：2026-09-29  
> 前提：**不考虑 Java 原生支持作为评分项**

## 1. 评分口径

匹配度拆成两个指标：

### 原生覆盖率

不做明显自研的情况下，候选方案本身能覆盖目标架构多少能力。

### 架构适配率

允许通过公开扩展点补齐后，与目标 Agent Harness Platform 的架构原则有多吻合。

这两个指标必须分开，否则会把“可以扩展”误算成“已经内置”。

## 2. POC 前估算

| 方案 | 原生覆盖率 | 架构适配率 | 主要缺口 | 当前定位 |
|---|---:|---:|---|---|
| Microsoft Agent Framework | ~80% | ~89% | 企业治理、生产 Store、Sandbox SPI、Artifact/Event 平台化 | 第一优先一体化方案 |
| Google ADK | ~68% | ~75% | Harness 深度、显式 Plan/Verify/Replan、Durable、UI 扩展 | 第三优先 Runtime/Orchestration 方案 |
| Temporal + Agent Runtime | ~72% | ~92% | Agent Harness 另选、集成量、基础设施复杂度 | 第二优先解耦 Control Plane 方案 |
| Temporal 单独 | ~45% | ~71% | 本身不是 Agent Harness | 不单独作为完整方案 |

> 上述比例建议按 ±5 个百分点理解，最终以 POC 实测为准。

## 3. 为什么 MAF 原生覆盖率最高

MAF 已覆盖大量目标能力：

- Agent / Harness
- Plan / Todo
- Context / Memory
- Compaction
- Tool / Approval
- Workflow
- HITL
- Checkpoint
- Session
- Streaming
- Responses-compatible
- A2A
- AG-UI
- Self-host

因此当前判断更接近：

~~~text
约 80%：MAF 直接提供
约 10%：通过公开扩展点补
约 10%：企业 Platform Layer 自己建设
~~~

最后约 10% 主要包括：

- Tenant / IAM
- Policy Engine
- Capability Registry
- Recipe Registry
- Budget
- Secret
- Enterprise Audit
- Artifact Lineage
- Unified Event Store
- Sandbox Governance

这些本来就属于企业差异化平台能力。

## 4. 为什么 ADK 下降

此前 ADK 的一个重要优势是 Java Native。

在不考虑 Java 原生后，比较重点回到 Harness 完整度：

~~~text
ADK
= 很好的 Agent Runtime / Session / Event / Tool / A2A 基础

但
= 显式 Harness、Plan/Verify/Replan、Durable Control 需要补更多
~~~

因此当前优先级下降。

## 5. 为什么 Temporal 架构适配率最高

Temporal 不提供完整 Agent Harness，但它天然符合：

> Control Plane 不执行副作用操作；Data Plane 不拥有业务 Workflow 最终控制权。

Temporal 可负责：

- Run / Workflow
- Durable state
- Retry / Timeout
- Queue / Worker
- Recovery
- HITL
- Scheduling

Agent Runtime / Sandbox 通过 Adapter 接入。

它的缺点不是架构不匹配，而是组合和运维复杂度更高。

## 6. 三种路线的本质

### MAF

~~~text
目标平台
██████████

MAF 原生
████████░░
~~~

主要工作：补缺口。

### ADK

~~~text
目标平台
██████████

ADK 原生
███████░░░
~~~

主要工作：在优秀 Agent Runtime 上继续建设 Harness。

### Temporal + Runtime

~~~text
Control Plane
██████████  Temporal 强

Harness
████░░░░░░  另选 Runtime

Data Plane
████░░░░░░  另选 Runtime/Sandbox
~~~

主要工作：组合组件，但控制平面边界最纯粹。

## 7. 当前 POC 优先级

在“不考虑 Java Native”前提下：

1. **MAF**：第一优先，验证一体化完成度和 public extension point 是否真的足够。
2. **Temporal + Runtime**：第二优先，验证更纯粹的 Durable Control Plane 是否值得额外复杂度。
3. **Google ADK**：第三优先，验证 Runtime/Event/A2A 能力与部署独立性。

## 8. POC 决胜点

### MAF

验证：

> 剩余缺口是否可以通过 public API 补齐，不 fork、不 monkey patch、不依赖 Foundry。

### Temporal

验证：

> 更高的组合和运维复杂度，是否值得换取彻底独立的 Durable Control Plane。

### ADK

验证：

> 在失去 Java-native 加分项后，其 Runtime/Session/Event/A2A 能力是否仍有足够差异化价值。
