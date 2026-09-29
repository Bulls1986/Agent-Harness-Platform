# Observability Contract

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-012

## 1. 核心定位

本契约定义 Harness Platform 的最小可观测性语义与跨组件关联规则。

核心原则：

> Runtime / Framework 原生 OpenTelemetry instrumentation 优先复用；Harness 只补平台自有边界和统一 Correlation，不重复建设同等粒度埋点。

OpenTelemetry 是 vendor-neutral telemetry baseline / export protocol，不拥有 Harness Domain Model。

## 2. 四类信号必须分离

必须保持：

~~~text
Business Event
≠ Trace / Span
≠ Log
≠ Metric
~~~

- Business Event：平台业务状态与审计事实，可参与状态解释、恢复和 UI replay。
- Trace / Span：一次调用链、依赖关系与耗时。
- Log：诊断信息与结构化运行记录。
- Metric：聚合运行指标。

Observability signals 不得反向成为 Run / Step 最终业务状态的事实源。

Telemetry 丢失不应改变任务正确性；业务 State / Event 丢失才属于任务正确性问题。

## 3. Runtime 原生观测优先

对于支持公开 OpenTelemetry instrumentation 的 Runtime / Framework：

~~~text
Runtime native telemetry
        ↓
OpenTelemetry
        ↓
Collector / Enterprise Observability Backend
~~~

平台必须优先直接接入其原生 telemetry，而不是重新包一套同等粒度的 span / metric / log。

MAF Python 当前原生基于 OpenTelemetry，可产生 traces / logs / metrics，并覆盖 agent/model invocation、tool execution、workflow spans 与 token usage；Harness 直接消费这些原生信号。

Harness 只补 Runtime 不拥有的平台边界，例如：

- Control Plane；
- ExecutionScheduler；
- Policy / Approval；
- Recovery / Reconciliation；
- Verification；
- Sandbox orchestration；
- Artifact / Evidence orchestration。

其他 Runtime 采用相同原则：有原生 OTel/public instrumentation 就复用，没有才在 Adapter 边界补齐必要 telemetry。

## 4. Correlation Contract

平台自有业务 ID 是跨 Runtime、跨 Trace、跨进程稳定的关联键。

至少包括：

~~~text
harness.conversation.id?
harness.turn.id?
harness.run.id
harness.plan.id?
harness.step.id?
harness.attempt.id?
harness.execution.id?
harness.participant.id?
~~~

规则：

- Trace / Log 在具备上下文时应携带相应 Harness correlation attributes。
- Provider / Runtime 原生 trace_id、span_id、session_id、response_id、workflow_id 只作为 telemetry/native metadata，不替代 Harness ID。
- 如果 Runtime 公开扩展点只能通过 parent span、Context、Baggage 或 equivalent mechanism 传播，则 Adapter 使用公开机制注入，不修改 Runtime 内部实现。
- 最低跨执行关联要求是 run_id；进入具体 Execution 时应尽可能同时携带 execution_id。

## 5. Run 与 Trace

Run 与 Trace 不要求 1:1。

长任务、人工等待、进程重启、故障恢复或跨 Runtime handoff 后可以形成新的 Trace：

~~~text
Run R1
├─ Trace T1 initial execution
├─ Trace T2 resume after approval
├─ Trace T3 recovery
└─ Trace T4 final verification
~~~

因此冻结：

> Run : Trace = 1 : N。

跨 Trace 的稳定业务关联依赖 harness.run.id，而不是要求复用同一个 trace_id。

## 6. Span 覆盖

平台不强制所有 Runtime 使用完全相同的内部 Span 树。

只要求可观测的关键边界能够被关联，例如：

- Agent / Runtime invocation；
- Model invocation；
- Tool / MCP invocation；
- Workflow / executor operation；
- Sandbox command / execution；
- Verification；
- Scheduler queue / dispatch；
- Recovery / Reconciliation。

Runtime 原生 operation/span naming 尽量保留；Harness 不为了表面统一而删除 Provider 原生可用信息。

GenAI 或 Provider-specific semantic conventions 由 Adapter 映射。平台核心领域模型不依赖某一版 GenAI semantic convention 的稳定性。

## 7. Structured Log 最小字段

结构化日志在适用时至少应能够关联：

~~~text
timestamp
severity
service.name
operation
trace_id?
span_id?
harness.run.id?
harness.step.id?
harness.attempt.id?
harness.execution.id?
harness.participant.id?
failure_type?
message
~~~

日志只用于诊断，不覆盖业务 Event 或 Evidence。

## 8. Metrics 与高基数约束

Metric 必须以聚合分析为目标。

禁止把以下高基数值作为默认 Metric label / dimension：

- run_id；
- conversation_id；
- step_id；
- attempt_id；
- execution_id；
- participant_id；
- user_id；
- artifact_id / evidence_id。

这些字段属于 Trace / Log correlation。

Metric label 应优先使用低基数字段，例如：

- runtime_type；
- provider；
- operation_type；
- outcome；
- failure_type；
- resource_class；
- model family / model identifier（在基数可控时）。

## 9. 最小指标范围

V1 只要求覆盖平台诊断所需的最小运行指标，例如：

- Run duration / active / waiting / outcome；
- Scheduler queue wait / queue depth / active execution / rejection；
- Execution duration / outcome / failure / retry；
- Model duration / TTFT / token usage / rate-limit / error；
- Tool / MCP duration / error / timeout；
- Sandbox create / execute / crash / restore latency；
- Recovery attempt / resume result / reconciliation count。

具体 cost、quota、chargeback 语义由 ARCH-TODO-013 定义。

## 10. Sampling

Trace / Log 允许采样，但 Business Event 不得因为 observability sampling 丢失。

默认规则：

- 普通成功链路允许采样；
- ERROR / UNKNOWN / Recovery / Reconciliation / Approval / Verification Failure 等关键诊断路径应优先保留；
- sampling 决策不得改变业务执行结果；
- 被采样丢弃的 Trace 不得导致业务 Event、Evidence 或 SideEffectReceipt 丢失。

具体采样比例属于部署配置，不在 Harness Kernel 写死。

## 11. Sensitive Telemetry

Prompt / Response / Tool Arguments / Tool Results / Repository Content 默认不进入普通 telemetry payload。

默认允许采集非敏感 metadata，例如：

- model/provider；
- operation；
- duration / TTFT；
- token counts；
- tool name；
- outcome / failure type。

若 Runtime 支持 sensitive telemetry opt-in，只有经过明确 Policy 允许后才可启用，并继续服从 Security 与 Retention Contract。

如果某段模型输入/输出、工具结果或日志内容需要作为正式 Evidence，应进入 Artifact / Evidence 流程，并按 ARTIFACT_EVIDENCE_LOG_RETENTION.md 保存，而不是依赖 Trace 长期存在。

## 12. Runtime Topology 关联

Runtime Topology 与 Observability 分工：

~~~text
Runtime Topology
→ participant identity / lifecycle / stable relationship

Trace / Span
→ invocation / latency / dependency

Log
→ detailed diagnostics
~~~

通过 participant_id、execution_id、sandbox/provider binding 等字段关联，不把每次 Span 复制进 Runtime Topology。

## 13. Export 与 Backend 边界

推荐：

~~~text
Harness / Runtime
→ OpenTelemetry
→ OTel Collector
→ Enterprise Observability Backend
~~~

Harness 不绑定 Prometheus、Grafana、Tempo、Loki、Jaeger、Elastic、Datadog 或其他具体产品。

Collector、存储、Dashboard、Alerting、APM 后端属于部署/运维层。

## 14. 不在本契约范围

- 自建 Prometheus / Grafana / Loki / Elasticsearch / APM；
- 告警平台实现；
- 具体 SLO / alert threshold；
- Artifact / Evidence payload retention；
- Cost / Quota / Chargeback domain；
- SIEM / Security Analytics；
- 全量 Prompt / Response 内容采集；
- Framework 内部私有 instrumentation。

## 15. Accepted Rules

1. Event、Trace/Span、Log、Metric 严格分离；Observability 不成为第二套业务事实源。
2. Runtime / Framework 原生 OpenTelemetry instrumentation 优先复用；Harness 只补平台自有边界和 correlation。
3. Run : Trace = 1:N；跨 Trace 稳定关联依赖 harness.run.id。
4. run_id / step_id / attempt_id / execution_id / participant_id 用于 Trace/Log correlation；Provider 原生 ID 只作为 metadata。
5. 高基数业务 ID 不进入默认 Metric labels。
6. 普通成功 Trace 可以采样；ERROR / UNKNOWN / Recovery / Reconciliation / Approval / Verification Failure 等关键路径优先保留；Business Event 不受 sampling 影响。
7. Prompt / Response / Tool Payload / Repository Content 默认不进入普通 telemetry；敏感 telemetry 必须显式 Policy opt-in。
8. Runtime 原生 telemetry 能观测到的能力尽量完整保留，不为了统一而丢弃；Provider-specific semantic conventions 留在 Adapter/telemetry boundary。
9. Observability Backend 是外部部署能力，Harness 不自建 APM/日志/指标产品。
10. Cost / Quota / Chargeback 由 ARCH-TODO-013 单独定义。