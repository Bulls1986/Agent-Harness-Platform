# POC-C / C13 — 原生 OpenTelemetry 与 Harness 关联

> 2026-10-08 | **本机 C13 OTel Trace/Corr 与部署依赖计数 PASS；CI 待核查**。
> 本报告不代表已部署 OTLP Collector/APM，也没有生产 CPU/内存/延迟压测。

## 官方能力与边界

复用 `temporalio.contrib.opentelemetry.OpenTelemetryInterceptor`
在官方 `Client.connect` 和 `Worker` 上的公开扩展点，
启用 `add_temporal_spans=True`，并使用官方
`create_tracer_provider` 提供的 **ReplaySafeTracerProvider**。
初次普通 TracerProvider 被 SDK 正确拒绝，随后按官方要求修复；
没有关闭 Workflow Sandbox 或重写 Native span/tracer。

`verify_c13_otel.py` 在真实 OSS Temporal Server 1.31.0、
独立 Temporal PG 和 Harness PostgreSQL 上启动 Workflow，
使用 **两个独立 Step/Attempt/Execution** 与同一 Run ID。
Temporal 原生 instrumentation 产生 Workflow/Activity spans；
Harness 仅在自有 Execution/Finalize 边界追加关联属性：
`harness.run.id`、`harness.step.id`、
`harness.attempt.id`、`harness.execution.id`，
以及低基数 `harness.runtime.adapter`。

本地实测：

| 实际观测 | 结果 |
|---|---|
| Temporal 原生 spans | **15 个** |
| Native Operations | `StartWorkflow`、`RunWorkflow`、`StartActivity`、`RunActivity` |
| Harness Execution spans | **2 个**，Run、Attempt、Execution ID 与持久 PG 一致 |
| Harness 业务事件 | **6 个**，Run 独立到达 `COMPLETED` |
| Exporter | 仅 `InMemorySpanExporter` 收集结果 |
| 真实 OTLP Collector/企业 APM | **GAP** |

Span 属于诊断数据，PG Event 属于任务事实；不能把 OTel Trace
当作 Run/Attempt 权威状态。Prompt/模型输出/凭据不会进入此验证
的 telemetry；Metric 默认不使用 Run/Attempt 等高基数 label。

## 部署依赖：实际 Compose 计数

`python poc/temporal/measure_c13_footprint.py` 对已存在的
三个 Docker Compose 文件运行 `config --services`，实际得到：

| 分类 | 数量和名称 |
|---|---|
| 常驻核心服务 | **3**：`temporal-oss`、`temporal-db`、`harness-postgres` |
| 一次性启动 Job | **2**：`temporal-schema`、`temporal-namespace` |
| Artifact/Evidence 可选 S3 | **1**：`c11-s3`（企业环境可复用外部 OSS） |
| 其他数据面/接口进程 | Worker、受限 HTTP Adapter，独立于上述 Compose 服务 |
| APM/Collector | 未部署、未作为 Harness 核心依赖重建 |

总计 **6 个 Compose 服务定义**，包括 2 个一次性 Job、
3 个核心常驻和 1 个可选 S3。不把它误当作生产 K8s 容器、
Node 数量或者 CPU/Memory 成本。没有进行同负载 A/C TTFT、
吞吐、P95、资源利用率或 HA 运维人力对照。

生产需要额外考虑 Temporal History 数据库维护、Replay/
Worker 升级兼容、TLS/HA、OTel Collector、数据库/OSS 自身运维；
企业共用 IAM/Secret/存储备份不属于 Harness 产品建设。

## 剩余风险

- ReplaySafeTracerProvider 当前官方 API 标注 experimental，
  SDK 升级需回归测试，不算生产长期稳定兼容保证。
- 多 Worker Trace 汇聚、跨重启多 Trace 关联、Sampling、
  OTLP 网络 Export、Logs/Metrics 的全量实现未验证。
- 本次 Agent Activity 为受控 Fixture，不是真实模型 Token 指标。
- C13 只对原生 Trace + Harness ID Correlation + Compose 依赖
  计数作 scoped PASS，不替代 POC-C 最终硬门禁 G1/G2/G3/G6。
