# 分层架构视图（Architecture Views）

> 此文件是业务、逻辑、应用、技术、数据、部署、功能和运行架构的唯一 Mermaid 图源。属于已冻结的架构视图，不代表所有图中能力均已投产。参见 [架构约束](ARCHITECTURE_GUARDRAILS.md)、[正式架构](ARCHITECTURE.md)及[里程碑状态](DEVELOPMENT_MILESTONES.md)。

### 3.1 八类分层架构视图

#### 八视图索引与六层逻辑模型

| 架构视图 | 回答的问题 | 明确不表达 |
|---|---|---|
| 业务架构 | 为什么建设、迁移什么、为谁提供价值 | 具体的部署拓扑 |
| 逻辑架构 | 分几层、每层权责、关键依赖与信任边界 | 必须部署六个服务 |
| 应用架构 | 应用模块与公开接口如何协作 | 所有模块已经实现 |
| 技术架构 | SDK/执行器/数据库的候选选择与替换槽位 | 技术候选已成为生产决策 |
| 数据架构 | 领域事实、Payload、外部数据的归属与流转 | 自建完整数据治理产品 |
| 部署架构 | 工作负载、资源、隔离、网络依赖如何布置 | HA/容量已经验收 |
| 功能架构 | 平台应交付的功能能力及 P0 边界 | 重建企业治理平台 |
| 运行架构 | 一次 Run 怎样运行、分配 Sandbox、恢复失败 | 运行拓扑取代业务流程 |

**统一的六层逻辑模型：** L1 业务接入 → L2 协议交互 → L3 Harness 领域控制 → L4 能力装配/Adapter → L5 Agent/Tool 执行 → L6 基础设施与持久化。L3 的 Control Plane 拥有 Run/Step 最终状态裁决；L5 Data Plane 负责真实执行。L6 的 Cube 资源控制面不等于 Harness 控制面。IAM、MCP Governance、Secret、Cost/Quota、观测后端与存储备份均为**外部系统**，不扩张 Harness 职责。

#### 3.1.1 业务架构（Business Architecture）

**两条相互独立的业务目标：** A. 取代现有以 OpenCode 为核心的 外部业务应用 平台执行架构，兼容现有用户体验、项目、会话、Agent/Skill/Prompt/MCP 等资产；B. 新增专业 Agent 可配置串联，先验收产品 → 研发 → 测试，再扩展文档/业务场景。当前存量专业 Agent 均使用 OpenCode，并非已经运行在多套 SDK 上。

```mermaid
flowchart TB
  subgraph ACT["参与者"]
    USER["产品 / 研发 / 测试 / 文档 / 业务用户"]
    OPS["外部业务应用 运营与资产维护"]
  end
  subgraph VALUE["业务价值域"]
    MIG["原 外部业务应用 无感迁移\n界面 · 会话 · 项目 · Agent 资产"]
    FLOW["专业 Agent 协作\n需求 → 编码 → 测试"]
    REUSE["复用到其他业务\n文档 → 核对 → 业务提交"]
    AUD["可验证、审批及任务级恢复"]
  end
  subgraph OWN["系统归属"]
    OLD["现有 外部业务应用 业务 Owner\n需求 / Story / Project"]
    NEW["Harness 执行控制 Owner\nRun / Step / Verification"]
    EXT["企业既有能力\nIAM / Git / MCP / 知识库"]
  end
  USER --> MIG & FLOW & REUSE
  OPS --> AUD
  MIG --> OLD & NEW
  FLOW & REUSE & AUD --> NEW
  EXT -. "授权/资源引用" .-> NEW
```

业务价值链为：接收意图 → 保留原产品能力 → 根据 Recipe 串联专业 Agent → 结构化成果交接 → Verification/Approval → 完成或安全恢复 → 回传可追溯 Evidence。迁移采用 M0–M4 灰度、单一 Writer 和回退门禁；**旧 外部业务应用 等价回归及新 Agent 串联业务 E2E 尚未验收**。

#### 3.1.2 逻辑架构（Logical Architecture）

```mermaid
flowchart TB
  subgraph L1["L1 业务接入层"]
    PORT["外部业务应用 UI / Portal / Enterprise API"]
    FACADE["Legacy API Facade / 路由"]
  end
  subgraph L2["L2 交互协议层"]
    API["Responses-compatible API\nConversation / Turn / Typed SSE"]
  end
  subgraph L3["L3 Harness 领域控制层"]
    CORE["Run / Plan / Step / Attempt\nRecipe / Verify / Replan"]
    CTRL["Policy / Approval / Retry / Cancel\nRecovery / Receipt Reconciliation"]
  end
  subgraph L4["L4 Adapter 装配层"]
    AR["AgentRuntime SPI"]
    DU["Process / Durable SPI\nHatchet Adapter / ID Binding"]
    SB["SandboxProvider SPI\nLease / Scope / WorkspaceRef"]
    OTHER["Model / Tool / Storage Adapter"]
  end
  subgraph L5["L5 Data Plane"]
    WORK["共享 Runtime Worker Pool"]
    CODE["隔离 OpenCode 2 Coding Guest"]
    TOOL["Model / MCP / Shell / Git / Browser"]
  end
  subgraph L6["L6 基础设施与数据"]
    PG["PostgreSQL\nHarness Task Facts Schema"]
    HATP["PostgreSQL\nHatchet Engine History / Queue Schema"]
    HATE["Hatchet Engine / Durable DAG\n持久队列 · Retry · 故障接管"]
    OSS["OSS / S3 Payload"]
    CUBE["Cube MicroVM（按需）"]
  end
  PORT --> FACADE --> API --> CORE --> CTRL
  CORE --> DU --> HATE --> WORK --> AR
  HATE --> HATP
  CTRL --> SB --> CUBE
  AR --> OTHER --> TOOL
  WORK --> TOOL & CODE
  CODE --> CUBE
  CORE --> PG & OSS
  GOV["外部 IAM / Credential / MCP 治理"] -. "Policy 输入" .-> CTRL
```

**不变式：** Session ≠ Run ≠ OS Process ≠ Workspace ≠ Sandbox；Runtime Session ID 与 Sandbox ID 是绑定引用而不是权限凭据。AgentRuntime SPI（如何运行 Agent）和 Process/Durable SPI（任务怎样耐久执行）分开；不重写 SDK 内核，不让 Cube 决定 Run 终态。Version/Capability Directory 是逻辑能力，不必建独立注册中心。

#### 3.1.3 应用架构（Application Architecture）

以下是模块/接口图，**不是强制的微服务拆分**。兼容入口和核心 API 可以合部署，Worker 可单独弹性扩容。

```mermaid
flowchart LR
  subgraph LEG["既有 外部业务应用 与兼容层"]
    UI["既有 外部业务应用 UI"]
    F["Legacy Facade\n历史 ID / 路由所有权"]
    OLD["旧 OpenCode 执行端\n未迁移会话"]
  end
  subgraph APP["Harness 应用层"]
    API["Chat/Run API + SSE"]
    RUN["Recipe / Plan / Step Controller"]
    SAFE["Policy / Approval\n领域恢复与 Receipt 核对"]
    EVT["Event / Artifact Reference API"]
  end
  subgraph AD["Runtime / Provider Adapter"]
    DISP["Runtime Dispatcher + Shared Worker"]
    SDK["Pydantic / OpenAI / MAF Adapters"]
    OC["OpenCode 2 Coding Adapter"]
    PVD["Sandbox / Model / Tool Adapters"]
    DUR["Process/Durable SPI → Hatchet Engine\nDurable DAG / Queue / Retry（当前首选）"]
  end
  subgraph INF["外部设施"]
    CUBE["Cube API + Guest"]
    PG["PostgreSQL\nHarness Task Facts / Hatchet History 独立 Schema"]
    OSS["OSS / S3"]
    MODEL["Model Gateway"]
    IAM["IAM / Credential / MCP Governance"]
  end
  UI --> F
  F -->|"旧会话"| OLD
  F -->|"新 Run 单一 Writer"| API
  API --> RUN --> SAFE
  RUN --> EVT
  SAFE --> DUR --> DISP
  DISP --> SDK & OC
  SDK & OC --> PVD
  PVD --> CUBE & MODEL
  RUN --> PG
  EVT --> PG & OSS
  IAM -. "授权输入" .-> SAFE
```

关键公开合同：旧 API 兼容、Responses-compatible + Harness Events、AgentRuntime SPI、Process/Durable SPI、SandboxProvider SPI、Model/Tool Adapter、Artifact/Evidence Reference。旧的 OpenCode Session 不自动等价于已发生的平台 Run，存量消息与执行事实必须分别迁移/核对。

#### 3.1.4 技术架构（Technology Architecture）

这里展示的是**可替换技术槽位**而不是要同时安装全部候选。Python 侧为平台优先，Java 原生不作首轮评分项。

```mermaid
flowchart TB
  HTTP["HTTP / Responses-compatible / Typed SSE"]
  K["Harness Domain + Deterministic State Machine"]
  POLICY["Policy / Lease / Fencing / Receipt\nVerification / RecoveryPoint"]
  subgraph AG["AgentRuntime SPI 实现"]
    PY["Pydantic AI Harness\n通用首选候选"]
    OAI["OpenAI Agents SDK\n可选"]
    OC["OpenCode 2\nCoding 保留"]
    MAF["MAF\n兼容可选"]
  end
  subgraph PROC["Process/Durable SPI · 当前首选（非生产 Accepted）"]
    HA["Hatchet Adapter\nPlatform IDs / Provider IDs Binding"]
    HE["Hatchet Embedded / 自托管 Engine\nDAG / Queue / Retry / Cross-Worker Failover"]
    HWRK["共享 Worker / Runtime Dispatcher\n固定并发 / 空闲 Session 不占进程"]
  end
  subgraph EXEC["独立执行技术维度"]
    CUBE["Cube / E2B-compatible API\nLocal baseline / Remote burst 候选"]
    LLM["ModelProvider / LiteLLM"]
    TOOL["MCP / Tool / Git / Browser"]
  end
  subgraph PERSIST["存储与观测"]
    PG["PostgreSQL Harness Task Facts / Events"]
    HPG["PostgreSQL Hatchet Workflow / Queue\n独立 Schema / Migration Ownership"]
    S3["S3 / OSS Artifact & Evidence"]
    OT["OpenTelemetry → 外部 Backend"]
  end
  HTTP --> K --> POLICY
  POLICY --> HA --> HE --> HWRK --> PY & OAI & OC & MAF
  HE --> HPG
  PY -. "按需 Sandbox" .-> CUBE
  OAI -. "按需 Sandbox" .-> CUBE
  MAF -. "按需 Sandbox" .-> CUBE
  OC --> CUBE
  PY & OAI & OC & MAF --> LLM & TOOL
  POLICY --> PG & S3
  K -. "Correlation" .-> OT
```

**已知证据与限制：** Hatchet v0.110.5（Python SDK 1.42.1）在真实 Engine、PostgreSQL、双 SDK DAG 与双 Engine 跨 Worker 安全步骤接管均获得**分项 LIVE PASS**，但不是同一 Run 全链 PASS。Cube v0.7.2 + E2B Python 2.40.0 在指定 DNS/TLS 条件下有真实功能 PASS；E2B 2.53.1 创建接口仍 405。平台任务级 Approval / SideEffectReceipt UNKNOWN、真实 Token SSE、可信 Lease/Cube 跨 Worker 重绑和容量仍 OPEN；**DBOS REJECTED，Hatchet 仅为当前实施首选，尚非生产 Accepted**。详见 [Hatchet 架构决议](docs/references/HATCHET_PROCESS_DURABLE_ARCHITECTURE_20261010.md)及[版本矩阵](docs/references/VERIFIED_STACK_BASELINE_20261010.md)。

#### 3.1.5 数据架构（Data Architecture）

平台拥有 Task Facts 与 Metadata，OSS/S3 承载大 Payload；**Hatchet Engine 使用独立 Workflow/Queue History Schema**，平台只存 Provider Workflow/Task ID Binding 与状态核对事实；旧 外部业务应用 业务数据、Git Revision 和 SDK 原生 Checkpoint 归各自 Owner。

```mermaid
flowchart TB
  subgraph DOMAIN["平台权威任务事实"]
    C["Conversation"] -->|"1:N"| T["Turn"]
    T -->|"1:N"| R["Run"]
    R -->|"Plan 版本化"| P["Plan v1..N"]
    P -->|"1:N"| S["Step"]
    S -->|"1:N"| A["Attempt"]
    A --> E["Execution\nOutcome / Lease / Fencing / ReceiptRef"]
    R --> RP["RecoveryPoint\nOpaque CheckpointRef"]
    R --> EV["Business Event / Sequence"]
    R --> AR["Artifact / Evidence\nMetadata · Digest · Lineage"]
  end
  PG["PostgreSQL\n任务状态 / Event / 版本 / Bindings"]
  OSS["OSS / S3\n文件 / Patch / 测试报告 / Evidence"]
  GIT["Git Server / Repository Workspace\nRevision Set"]
  EXT["旧 外部业务应用 业务库 / 历史会话"]
  NATIVE["Runtime Checkpoint / SandboxRef\nOpaque Provider Reference"]
  HP["Provider Workflow / Task ID\nOpaque Binding（非业务 ID）"]
  HPG["PostgreSQL Hatchet 独立 Schema\nQueue / Engine History"]
  C & T & R & P & S & A & E & RP & EV & AR --> PG
  AR -->|"StorageRef + Digest"| OSS
  E -. "Workspace Binding" .-> GIT
  R -. "Legacy ID 映射" .-> EXT
  RP -. "仅引用/能力声明" .-> NATIVE
  E -. "Provider Task / Workflow ID 绑定" .-> HP
  HP --> HPG
```

**交接数据合同：** Agent A 的结构化输出通过 Verification，附 ArtifactRef/Digest/Scope/版本信息后才交给 Agent B；不能将整段原生 Chat History 或 Sandbox ID 直接当成可复用可信授权。Run 创建冻结 Recipe/Runtime/Model/Tool/Policy/Environment 版本；UNKNOWN 必须查询 Receipt 或人工对账，不盲重试。业务 Event 是事实；Trace/Log/Metric 是诊断。Harness 只做任务恢复，不做数据库/存储备份和灾备。

#### 3.1.6 部署架构（Deployment Architecture）

私有化**候选拓扑**，不预设 K8s/容器具体节点数与 HA；Local Cube baseline + Remote Cube burst 是目标策略，后者尚未按生产门禁完成验证。

```mermaid
flowchart TB
  U["浏览器 / 外部业务应用 / API Client"]
  subgraph EDGE["企业接入区"]
    LB["Internal Gateway / Legacy Route / TLS"]
  end
  subgraph PLATFORM["平台计算区（容器或主机）"]
    API["Harness API / SSE"]
    K["Harness Kernel / 领域控制\n不重复实现 Hatchet 调度器"]
    HE["Hatchet Engine Fleet\n自托管 / Embedded · 持久队列"]
    W["共享 Hatchet Worker + AgentRuntime Dispatcher\nPydantic / OpenAI / MAF"]
    O["OpenCode 2 Adapter\n经公开协议访问 Guest"]
  end
  subgraph STORE["企业数据区"]
    PG["PostgreSQL"]
    S3["MinIO / S3-compatible OSS"]
  end
  subgraph LOCAL["隔离执行区（Local Cube）"]
    CM["Cube API / Master / Cubelet\nSandbox Infra Control Plane"]
    VM["按需 MicroVM\nOpenCode 2 / FS / Shell / Git"]
  end
  RC["Remote Cube Cluster\nburst 候选"]
  EXT["已有 IAM / Credential / Git / MCP\nLiteLLM / OTel Backend"]
  U --> LB --> API --> K
  K --> HE --> W
  K --> PG & S3
  HE -->|"Workflow / Queue Schema"| PG
  W --> O
  W -->|"授权 Scope / Lease"| CM
  O --> VM
  CM --> VM
  K -. "资源与 Policy" .-> RC
  K & W -. "外围接口" .-> EXT
```

**节省资源和隔离：** 轻量 Agent 可以零 Sandbox；一个共享 Worker 服务多个逻辑 Session，不要求一个历史 Session 永久一个 Agent OS 进程或 Cube。需要 FS/Shell/Git 的 Coding 执行优先 Harness-in-Cube；同 Scope 的多个逻辑 Session 是否复用同 Sandbox 需显式授权，不能跨用户/项目/秘密边界共享。OpenCode 在共享 Host 的原生 Shell **不会**自动随 Session ID 转发到 Cube，这条替代拓扑不能当作生产隔离已通过。环境采用 immutable OCI digest 与版本对照，生产一致性、Burst、容量仍需单独 Gate。

#### 3.1.7 功能架构（Functional Architecture）

业务 Agent 按能力和 Recipe 装配，不为产品/研发/测试/文档/业务分别复制一套 Harness。

```mermaid
flowchart TB
  ROOT["Agent Harness Platform"]
  ROOT --> A["存量兼容"]
  ROOT --> B["多 Agent 业务协作"]
  ROOT --> C["能力装配与执行"]
  ROOT --> D["执行安全"]
  ROOT --> E["任务事实与恢复"]
  ROOT --> F["交互与诊断"]
  A --> A1["旧 UI/API/历史 / 资产引用\n灰度路由 / 单 Writer 回退"]
  B --> B1["Agent Catalog / Recipe / Step 依赖\n产物交接 / Verification / Replan"]
  C --> C1["AgentRuntime / Tool / Model SPI\nSkills / Subagents / 可选 Sandbox"]
  D --> D1["Policy / Approval / Credential\nScope / Lease / Fencing / Cancel"]
  E --> E1["Run / Attempt / Event / RecoveryPoint\nSideEffect Receipt / Reconciliation / Evidence"]
  E --> E2["Hatchet Durable Adapter\nQueue / DAG / Retry / Worker 接管\n平台决定安全恢复边界"]
  F --> F1["Typed Event / Token SSE / Replay\nTopology Participant / OTel Correlation"]
```

第一期 P0 必须独立通过：① 原 外部业务应用 真实功能、资产、历史、API、权限回归；② 一个 Run 内至少两个不同 Runtime 按 Recipe 交接 Artifact/Evidence，验证失败阻断下游、审批等待和任务级恢复安全。功能图**不**包含企业 IAM、MCP Marketplace、计费、镜像安全或运维监控产品的自建任务。

#### 3.1.8 运行架构（Runtime Architecture）

运行架构展示**动态时序和恢复决策**；[Runtime Topology Contract](docs/references/RUNTIME_TOPOLOGY.md) 只记录 Participant 身份/生命周期和 OWNS、SPAWNS、RUNS_ON、HANDOFF_TO 等稳定关系，不能取代 Plan/Workflow/Scheduler。

##### 3.1.8.1 正常执行：轻量 Agent → Coding → 测试 Agent

```mermaid
sequenceDiagram
  autonumber
  actor U as 用户
  participant G as API / Legacy Facade
  participant H as Harness Kernel / Domain
  participant D as PG Harness Task Facts
  participant P as Process/Durable SPI (Hatchet Adapter)
  participant E as Hatchet Engine / Durable Queue
  participant W as Hatchet Worker / AgentRuntime SPI
  participant S as SandboxProvider / Cube
  participant O as OSS Artifact/Evidence
  U->>G: 提交意图
  G->>H: 通过旧入口路由到新 Run（单 Writer）
  H->>D: 创建 Run / Plan / Steps / 版本冻结
  H->>P: 入队可执行 Step + Provider Binding
  P->>E: enqueue Workflow / DAG
  E->>W: dispatch Step A（Pydantic Agent）
  Note over W,S: 纯模型/结构化任务：零 Sandbox
  W->>H: 真实 Step A Outcome / Typed Events
  H->>O: Artifact Payload + Digest
  H->>D: Verification PASS / EvidenceRef / Step Fact
  opt 需要人工批准（目标契约，尚未端到端验收）
    H->>D: WAITING_APPROVAL + RecoveryPoint
    H->>P: 持久等待原 Workflow（释放活动 Worker）
    H-->>G: approval.required
    G-->>U: 展示审批
    U->>G: 已授权 Principal 审批
    G->>H: 校验 Approval(Principal/Resource/Action)
    H->>D: 审批事实与恢复裁决
    H->>P: 恢复同一个业务 Run 的等待
  end
  P->>E: 下一个可执行 Step
  E->>W: dispatch Step B（OpenCode Coding）
  W->>S: 授权 Scope / Lease / Fencing / WorkspaceRef
  S-->>W: Cube SandboxRef（同 Scope 方可复用）
  W->>S: Guest FS / Shell / Git（禁止回退 Host）
  S-->>W: Tool Result / ReceiptRef
  W->>H: Patch / Typed Events / Outcome
  H->>D: Attempt / Execution / Verification / Receipt
  P->>E: Step B 通过后才放行 Step C
  E->>W: dispatch Step C（测试 Agent）
  W->>H: Test Result / Evidence
  H->>O: 测试报告 Payload
  H->>D: Run Terminal / Event Sequence
  H-->>G: SSE Event Cursor + ArtifactRef
  G-->>U: 可回放的执行结果
  H->>S: 按 Lease Policy 释放/保留 Sandbox
```

##### 3.1.8.2 故障路径：UNKNOWN 不能直接重试

```mermaid
flowchart TB
  RUN["活动 Run / Step / Attempt"] --> FAIL{"Worker Crash / Timeout / Cancel?"}
  FAIL -->|"否"| DONE["持久真实 Outcome / Event"]
  FAIL -->|"是"| ENGINE["Hatchet Durable History\nQueue / DAG / Worker B 可接手"]
  ENGINE --> CHECK["Harness 核对 PG Task Facts\nExecution Owner / Lease / Fencing / RecoveryPoint"]
  CHECK --> KNOW{"外部副作用是否可证明安全?"}
  KNOW -->|"PURE 或幂等已验证"| SAFE["选最深可信恢复边界\n授权 B 的新 Owner / Fencing"]
  KNOW -->|"可能已产生但 ACK 未收到"| REC["UNKNOWN → Reconciliation\n查询 Receipt / 外部系统 / 人工核对"]
  REC -->|"核对成功且允许继续"| SAFE
  REC -->|"仍 UNKNOWN"| HOLD["禁止 Hatchet 自动重放非幂等 Tool"]
  SAFE --> CAP{"Runtime 原生 Same Attempt Resume?"}
  CAP -->|"支持且有可信 Checkpoint"| RES["Same Run / Step / Attempt Resume"]
  CAP -->|"不支持但可安全重试"| RET["Same Run / Step / New Attempt"]
  RES --> DONE
  RET --> DONE
```

Runtime State、Workspace State、Sandbox State 彼此独立；**Hatchet 的引擎恢复和平台领域恢复分别由 Engine 与 Harness Domain 负责**，不能把两个 Owner 合并。平台只拥有任务级 RecoveryPoint 与 SDK 原生 checkpoint 的 Opaque Reference，不重写框架恢复引擎，不引入跨组件 2PC。Cancel Request 不等于下游已终止。SSE 只能反映真实执行事件。此时序是**目标一体化链路**，现有多个局部 POC 不能拼成一个已经完成的 E2E 生产证据。

#### 3.1.9 跨视图一致性门禁

| 不变式 | 核心视图 | 当前状态 |
|---|---|---|
| 原 外部业务应用 无感兼容和跨 Agent 串联分别验收 | 业务/应用/功能 | 业务目标已确认，真实 E2E OPEN |
| Conversation → Turn → Run → Plan(vN) → Step → Attempt，Run 终态不重开 | 逻辑/数据/运行 | Accepted Contract |
| AgentRuntime、Process/Durable、SandboxProvider 三个 SPI 相互独立 | 逻辑/应用/技术 | Accepted 边界；Process/Durable 当前首选 Hatchet Adapter（未生产 Accepted） |
| Control Plane 才能最终裁决 Run 状态 | 逻辑/应用/运行 | Accepted Contract |
| 轻量 Agent 零 Sandbox；Coding 默认隔离 | 技术/部署/运行 | 局部 Cube/OpenCode 功能 POC PASS，生产隔离 OPEN |
| Session ID 非授权；Binding 要校验 Scope / Lease / Fencing | 数据/部署/运行 | Accepted 合同；Hatchet 跨 Engine 安全任务接管已 LIVE PASS，平台可信 Lease/Cube 接管仍 OPEN |
| PG 保存任务事实，OSS 保存大 Payload，Native Checkpoint 是 Opaque 引用 | 数据/部署 | Accepted Contract，全链集成 OPEN |
| UNKNOWN → Reconciliation；禁止非幂等盲重试 | 数据/功能/运行 | Accepted Contract，真实回执全链 OPEN |
| IAM / MCP 治理 / Secret / 观测后端 / Backup 不由 Harness 自建 | 全视图 | 明确 Ownership Boundary |

**维护原则：** 新的局部验证结果先更新专项 Findings、Admission、Architecture Backlog；修改 Accepted Contract 须走 ADR，不能仅通过修改本视图产生新决策。