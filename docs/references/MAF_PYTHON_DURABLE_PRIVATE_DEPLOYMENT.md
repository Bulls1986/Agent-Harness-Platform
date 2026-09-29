# MAF Python Durable 私有化部署约束

> 状态：Accepted Architecture / POC Constraint  
> 日期：2026-09-29  
> 适用范围：Microsoft Agent Framework Python Durable 路线

## 1. 结论

当前 Python MAF Durable 路线必须区分两种 Hosting：

### 1.1 Standalone Durable Task

~~~text
Python MAF
→ agent-framework-durabletask
→ durabletask / TaskHub gRPC
→ Durable Task Scheduler
~~~

当前官方 Python SDK / MAF Durable Extension 的生产路径围绕 Durable Task Scheduler（DTS）。

本地 DTS Emulator 可用于开发与 POC，但不得视为生产持久化后端。

当前没有经过官方支持、可直接替换为 PostgreSQL 的 production TaskHub gRPC backend。

### 1.2 Durable Functions Hosting

完全私有化的现成路径为：

~~~text
Python MAF
→ agent-framework-azurefunctions
→ Azure Functions Runtime
→ Durable Functions
→ MSSQL Provider
→ SQL Server
~~~

业务与 Agent 代码仍然使用 Python，不要求编写 .NET 业务代码。

SQL Server 在这里属于 Durable Runtime 基础设施，不是 Harness 平台业务主库。

## 2. PostgreSQL 现状

平台主存储可以继续使用 PostgreSQL，但当前不能把 PostgreSQL 直接作为 Python MAF Durable Task 的官方生产状态后端。

因此：

~~~text
PostgreSQL
→ Harness Domain / Run / Plan / Step / Policy / Artifact Metadata

SQL Server
→ MAF Durable Runtime History / Queue / State / Coordination
~~~

二者职责必须分离。

不得为了统一数据库技术栈，自行实现 PostgreSQL Durable Task Backend。

## 3. 禁止自研 Durable Backend

冻结以下原则：

> 平台不自行实现 Durable Task Scheduler、TaskHub gRPC backend、replay engine、durable queue、worker coordination 或等价基础设施。

如果现有 Framework / Runtime 无法通过公开扩展点满足生产私有化要求：

- 降低该 Durable Runtime 的架构角色；
- 或通过 DurableRuntime Adapter 切换到其他成熟 Durable Engine；
- 不 fork MAF；
- 不复制 Durable Task 内部实现；
- 不为了 PostgreSQL 自建兼容后端。

## 4. DurableRuntime 隔离

Harness Kernel 不直接依赖 Durable Task 专有 API。

目标边界：

~~~text
Harness Kernel
      ↓
DurableRuntime SPI
      ↓
├─ MAF Durable Adapter
├─ Temporal Adapter
└─ Future Durable Adapter
~~~

平台优先只依赖 Durable Engine 的公共交集：

- start
- resume
- durable wait / external event
- timer
- retry
- cancellation
- status query
- crash recovery

避免把 Durable Entity、DTS-specific scheduling、TaskHub-specific metadata 等特殊能力扩散到平台领域模型。

## 5. 当前生产候选

### Candidate A — MAF Native Durable

~~~text
Python MAF
→ Durable Functions Runtime
→ MSSQL
~~~

优点：

- 保留 MAF / Durable Task 原生 Durable 语义；
- 不自行实现 Durable 基础设施；
- 可完全私有化部署。

代价：

- 增加 Azure Functions Runtime；
- 增加 SQL Server 运维依赖；
- 自管 Kubernetes 的支持等级和长期运维成本必须进入 POC 评估。

### Candidate B — External Durable Control Plane

~~~text
Harness Kernel
→ DurableRuntime SPI
→ Temporal
→ PostgreSQL

Activity / Runtime
→ MAF Agent Runtime
~~~

该路线允许继续使用 MAF Agent 能力，但不要求 MAF Durable 承担平台 Durable Control Plane。

## 6. POC Hard Gate

MAF Python POC 必须至少验证：

1. Python MAF + Durable Functions Runtime + MSSQL 可在完全私有网络环境运行。
2. 至少两个 Worker/Pod 并发连接同一 Durable backend。
3. Worker 中途退出后任务可由其他 Worker 恢复。
4. WAITING_APPROVAL / external event 在 Worker 全部重启后仍可恢复。
5. Durable backend 不要求平台实现自定义 Scheduler / Lease / Replay。
6. Harness Domain Model 不直接依赖 Durable Task 特有对象。
7. 将 Durable Runtime 替换为另一 Adapter 时，Run / Step / Attempt 领域模型无需变化。

若以上关键门禁不能通过，则：

> MAF 降级为 Agent Runtime / Harness Runtime，不承担平台 Durable Control Plane。

## 7. 当前风险记录

- Python MAF standalone Durable 的生产 backend 选择面较窄。
- PostgreSQL 当前不是可直接替换的官方 TaskHub production backend。
- MSSQL 是当前完全私有化 MAF Durable 路线中的额外基础设施成本。
- 不把 DTS Emulator 的本地可运行性误判为 production self-host 能力。
- Duroxide / Temporal 属于其他 Durable Runtime，不是简单替换 TaskHub connection string。

## 8. 复核要求

该领域演进较快。

进入正式生产选型前必须重新核验：

- agent-framework-durabletask 当前依赖；
- durabletask-python 可用 backend；
- Durable Functions storage provider；
- PostgreSQL-compatible TaskHub backend 是否出现；
- Azure Functions Runtime 自管部署支持状态；
- SQL Server edition / licensing / HA 能力。
