# 多专业 Agent / 可选 Sandbox / 共享进程：技术选型增量评估

> 日期：2026-10-09；状态：**CANDIDATE / NOT ACCEPTED**；关联 ARCH-TODO-024。
> 用户最新范围：以各项技术目前实际能做到什么为评价基础，**当前功能性 POC
> 不以“所有 OpenCode 原生执行入口已隔离”作为前置条件**；完整隔离与审计仍是
> 生产门禁，不能因阶段降级而从正式架构契约中删除。

## 1. 需求基线（不是选某一个框架的理由）

1. 面向 PDLC、企业门户等不同场景；业务入口可通过 Jev 一类的快速决策模型
   选逻辑 Agent/Process，复杂流程走硬门禁与必要的人类审批。
2. Product / Coding / Test / Knowledge / Business 专业 Agent 不强求同一个
   Harness；OpenCode 现有 Skills、Subagents、Prompts 资产继续复用。
3. 有的 Agent 不需要 Sandbox，有的按需绑定；**Session ≠ Agent OS Process**，
   不能一个历史 Session 永久占一个进程/容器。
4. 以 CubeSandbox 自托管资源池为目标，以 E2B 兼容 API 为首选公用操作子集；
   外部 Sandbox ID、WorkspaceRef 作为绑定，不取代 PG 上的平台任务事实。
5. 平台只负责 Harness 内应负责的执行、路由、门禁、恢复、证据、SPI，
   不接管 Cube MicroVM 内核、MCP 治理、备份等外围基础设施。

## 2. 现有技术候选的实际可用能力

| 组合 | 贴合能力 | 缺口/风险 | 本仓库证据 |
|---|---|---|---|
| **Pydantic AI Harness + Temporal + Cube(E2B)** | Pydantic AI 有 Jev/TypeSafeModel 决策模型、标准 Agent/Tools；Harness 的 Coder、Skills、Subagents、E2BSandbox、WorkspaceRef 按需绑定；原生 TemporalDurability | Harness 当前 0.x，接口升级成本；E2BSandbox→Cube 真机、模型链、外部沙箱重连、安全/恢复尚未跑；不能直接替换已经成熟的 OpenCode 编码体验 | **0.54.0 离线 20 并发 Run、两种 WorkspaceRef、零 E2B 创建/连接 PASS**；Cube 未测 |
| **OpenAI Agents SDK + Temporal + Cube(E2B)** | 官方 SandboxAgent + E2BSandboxClient；Temporal 官方独立集成（含 Sandbox），能在共享应用 Worker 中调用多个 Run；丰富 handoff/tool/审批机制 | Cube 官方案例有兼容修补；单独支持 Jev 必须做决策模型 Adapter；无法无代价复用 OpenCode 的 Coding 能力 | Docker 原生 SandboxClient、FunctionTool 已实测；Cube 真机未跑 |
| **MAF + MAF Durable 或 Temporal + Cube Tool Adapter** | 强 Workflow/Executor + Checkpoint；业务型专业 Agent、SDK Runtime Pool 可行；已有 POC-A | SDK 没有可直接视作本项目全面通过的 Cube/E2B 原生 Sandbox Client；SQL Durable 许可/运行与跨 Harness 不确定窗口仍有待闭合 | MAF POC-A 相关 Gate 局部通过；Cube 路径未实测 |
| **OpenCode 2 + Cube(E2B)** | 完整 Coding Harness、Skills、Session、Plugin；共享 V2 Server/嵌入 Host 为高密度候选；既有 PDLC 资产可直接继承 | 原生 Shell/FS/PTY 等**不会**因 Session 绑定自动远程执行；不能宣称共享 Host + 每 Session Cube 完全透明可用 | V2 Docker Sandbox 内 Session + SDK 文件接力通过；原生 Shell 路由的反向实验已确认 |

**不存在一个已验证的“完全零适配、一次满足所有需求”的单品。**
当前比较的单位是**可组合技术栈**，不是用 Temporal 替换 Harness SDK、
也不是用 Pydantic AI Harness 替换 Cube 基础设施。

## 3. 推荐候选组合及具体边界

### 首选新能力候选（待验）：Pydantic AI Harness + Temporal + Cube

- **Intent Router**：Jev 经 `TypeSafeModel`；低置信度/不能决策交更强模型；
  组织 ACL、批准和最终 Process 选择仍由平台确定性策略校验。
- **通用专业 Agent**：Pydantic AI Harness；简单 Agent 无 Sandbox；Coding
  类 `Coder + E2BSandbox`；可通过 `WorkspaceRef` 复用既有 Sandbox ID。
- **执行可靠性**：Temporal 负责业务阶段/人工审批/故障恢复，
  避免给不相关的 OpenCode 每个 Token 都裹 Temporal Workflow。
  Pydantic `TemporalDurability` 支持 Agent 内部耐久性，
  **但是否开启应按恢复粒度决定，不能同时套两个 Durable 引擎**。
- **现有 Coding Agent**：OpenCode 2 作为独立 Runtime Adapter 保留，
  不强制迁移到 Pydantic Coder；优先沿用可用 OpenCode Session Server。
- **Sandbox**：Cube 提供 E2B 通用执行子集；Volume 需要 Cube SDK/REST
  专用薄 Adapter，因官方 E2B Python Volume Client 不兼容。

**实际推荐策略是渐进混合而不是全量替换：**
`Jev/Pydantic Router → Agent Catalog → OpenCode2 | Pydantic AI | OpenAI SDK/MAF`
`→ Process/Durable SPI(Temporal 候选) → CubeSandbox(E2B)`。

### 次选低变更候选：OpenAI Agents SDK + Temporal + Cube + OpenCode 2

已有本项目 Docker 功能链实测，Temporal 的 OpenAI Agents SDK 集成有官方
GA 组件；Cube 也有官方集成示例。若 Pydantic Harness 的 0.x 变更或
Cube 接入工作量超过其减少的胶水代码，选择 OpenAI Agents SDK 作为
通用 Agent Runtime 更稳妥。Jev Router 独立实现亦可保持同一业务语义。

### MAF 在该组合中的角色

不因发现 Pydantic AI 就废弃已有 POC-A：对于现成 Microsoft/MAF
业务型 Agent 或 MAF 特有 Workflow，MAF 可以作为并存 Runtime；
MAF Durable 与 Temporal 的平台级二选一继续依原 POC-C 比较，
不能声称新候选已经自动决定胜出。

## 4. 验收从“理想满配”改为分层事实

| Gate | 功能性 POC 需证明 | 生产上线需另行证明 |
|---|---|---|
| T1 Session 高密度 | 单 Worker / SDK Host 可以创建 10~100 Session，无一 Session 一进程的强制映射 | 容量/回收/断点安全，长期负载 |
| T2 可选 Sandbox | 无 Sandbox Agent 不申请；按需 Agent 可拿到一个 SandboxRef 并复用 | 不同授权 Scope 文件/命令无串扰 |
| T3 Cube / E2B | Cube 真机创建、`commands.run`、`files.read/write`、连接、销毁 | 数据面、TTL、暂停/恢复、Volume、故障恢复 |
| T4 多 Harness 接力 | 两种 Harness 对同一 Sandbox/Workspace 写读成功 | 非幂等 Receipt、跨框架 Session/权限以及错误处理 |
| T5 Process + Router | Jev 路由到产品/研发/知识至少三路；多 Agent 能按流程推进并等待审批 | 验证器、审计、版本升级/回滚、活跃 Run 迁移 |

所有 Gate 记 **Native / Adapter / Tested / Untested / Unsupported**；
不能用“架构理论可行”代替真机测试结果。T1-T4 当前已有不同程度的
Docker 基线，**尚无 Cube 实际运行实例**。

## 5. 推荐最短 POC（暂不改 Accepted ADR）

**2026-10-09 执行增量：** 已运行
[`poc/pydantic_harness/verify_offline_density.py`](../../poc/pydantic_harness/README.md)：
Pydantic AI Harness 0.54.0 + pydantic-ai-slim 2.54.0，
20 个并发模拟 Run 使用同一个 Agent 实例，
同一个 Coding Agent 可在不同 Run 接收独立 `WorkspaceRef`，
并在不用工具时零次调用 E2B SDK create/connect。
这些是**离线公开接口行为**，并未验证 Cube E2B 通信、工具执行和
跨 Scope 隔离。Jev 只验证 `TypeSafeModel` 可导入。
另在 Windows 本机实测 `LocalWorkspace` 创建抛 `NotImplementedError`
（`LocalWorkspaceBackend` 只支持 POSIX），这是本地执行环境限制，
不等于 Linux Worker 或 E2B/Cube 后端不支持。

**2026-10-09 真实工具增量：** Linux CI 中共享 1 个 Pydantic Agent
分别给两个并发 Run 传入独立 `LocalWorkspaceBackend`，通过
确定性 FunctionModel 真实触发各自的 `write_file`、`read_file`
和 `shell`；文件最终分别为 `alpha` 和 `beta`，没有发生
跨 Workspace 串写。这证明 Pydantic **公开的 Run-scoped Tool
执行路由**符合当前功能性 POC，但并未涉及 Cube/E2B 协议、
MicroVM、暂停恢复或多框架完整 Agent Loop。
Cube 真机 Pydantic `E2BSandbox + WorkspaceRef` 复用脚本已加入
[`verify_cube_live.py`](../../poc/pydantic_harness/verify_cube_live.py)，
只在 `--live` 和 `CUBE_E2B_LIVE_CONFIRM=1` 同时满足时允许创建 Sandbox；
未配置的环境保持 BLOCKED。

1. 对新候选 Pydantic AI Harness 先做公开接口无模型 smoke：
   `Agent + Coder/Tools`、`E2BSandbox` 是否接受既有 Workspace/Sandbox 引用，
   Jev 的 `TypeSafeModel` 是否能在单独 Router 测试中工作；
   确认使用相同 Worker 不强制一 Session 一个 Agent OS Process。
2. 用同一套真实 Cube E2B 合约测试对照 Pydantic AI Harness
   与 OpenAI Agents SDK；必需 CubeAPI/Template/数据面，不用 Docker 代替。
3. 如果 Pydantic 的 0.x 稳定性/接口差异或 Cube 兼容代价明显高于 OpenAI SDK，
   将 OpenAI SDK 升为通用 Agent 首选；OpenCode 继续 Coding 专业执行。
4. 仅在等价运行/恢复负载后比较 Temporal vs MAF Durable 开发维护总量，
   保留原本 Non-idempotent Receipt 和版本部署的未完成 Gate。

## 6. 公开依据（2026-10-09 查证）

- Pydantic AI Harness：[能力组合](https://pydantic.dev/docs/ai/harness/)
  · [E2B Sandbox / WorkspaceRef](https://pydantic.dev/docs/ai/harness/e2b-sandbox/)
  · [Coder](https://pydantic.dev/docs/ai/harness/coder/)
  · [TemporalDurability](https://pydantic.dev/docs/ai/capabilities/durable_execution/temporal/)
  · [TypeSafe/Jev](https://pydantic.dev/docs/ai/models/typesafe/)
- OpenAI Agents SDK：[Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes)
  · [Temporal integration](https://docs.temporal.io/develop/python/integrations/openai-agents)
- OpenCode 2：[Embedded SDK](https://opencode.ai/v2/docs/build/sdk)。
- Cube：[E2B/Agents SDK](https://docs.cubesandbox.com/zh/guide/integrations/openai-agents-sdk)
  · [Volume 兼容边界](https://docs.cubesandbox.com/zh/guide/volume-plugin.html)。