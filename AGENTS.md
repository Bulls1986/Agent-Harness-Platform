# AGENTS.md

本文件定义 Agent、Coding Assistant、自动化工具以及人工协作者在本仓库中的统一工作原则。  
适用于仓库根目录及全部子目录；若未来某个子目录存在更具体的 `AGENTS.md`，则以更深层文件的补充约束为准，但不得违反本文件的核心架构原则。

# 1. 项目目标

本仓库建设的是企业级、厂商无关的 **Agent Harness Platform**。

任何工作都必须优先保护以下目标：

- 厂商无关（Vendor Neutral）。
- 控制平面 / 执行平面分离（Control Plane / Data Plane Separation）。
- 领域模型由平台拥有，不由具体 Framework / Provider 定义。
- 状态可持久化、可恢复、可审计。
- Runtime / Model / Sandbox / Tool / Storage 可替换。
- Coding Execution 生产默认隔离执行。
- 架构结论必须有清晰边界、证据和可验证的 POC。

# 2. 开始任何工作前必须阅读

涉及架构、POC、接口、实现或测试前，至少阅读：

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `docs/ARCHITECTURE_BACKLOG.md`
4. `docs/POC.md`
5. 与当前任务直接相关的 `docs/references/*.md`

如果任务涉及已经关闭的架构待办，必须先读取其 Accepted Contract。

禁止在不了解现有 Decision / ADR 的情况下重新发明同类模型。

# 3. 架构优先级

发生冲突时，按以下顺序处理：

~~~text
Accepted ADR / 正式架构
        ↓
Accepted Architecture Contract
        ↓
POC 门禁 / Contract
        ↓
当前 Backlog Decision
        ↓
框架或 Provider 的默认实现
        ↓
实现便利性
~~~

**不能因为某个 Framework 当前更容易实现，就反向改变平台领域模型。**

MAF、Temporal、ADK、CubeSandbox、Codex、OpenAI Agents SDK 等都属于实现候选或 Adapter，不拥有平台核心语义。

# 4. 架构讨论工作流

架构问题统一进入：

`docs/ARCHITECTURE_BACKLOG.md`

状态流转：

~~~text
TODO
→ DISCUSSING
→ DECIDED / POC
→ CLOSED
~~~

当一个架构待办形成明确结论后，必须同时完成：

1. 新增或更新对应专题 Contract / Reference。
2. 更新 `docs/ARCHITECTURE.md`。
3. 必要时更新 `docs/POC.md`。
4. 新增或更新 ADR 摘要。
5. 将 Backlog 条目更新为 CLOSED。
6. 更新 `docs/references/README.md` 索引。

未完成以上动作，不得口头宣称“架构已收口”。

# 4.1 架构边界控制

所有架构讨论、POC 和实现都必须控制职责边界，避免“顺手设计”导致平台膨胀。

必须遵守：

- 一个架构待办只解决自己的核心问题。
- 发现相邻问题时，先记录到 `docs/ARCHITECTURE_BACKLOG.md`，不要直接并入当前 Contract。
- 除非当前问题无法成立，否则不要为了未来可能性提前新增领域对象、控制平面职责或分布式协调机制。
- 能作为 Metadata 的，不先升级为强领域模型。
- 能由 Project Skill / Policy / Adapter 解决的，不写死进 Harness Kernel。
- 能由 Runtime / Provider 自己承担且不破坏平台契约的，不重复建设平台能力。
- 不把 Workspace、E2E Environment、Runtime Topology、Multi-Agent、Deployment、Release 等不同职责混成一个模型。
- 新增抽象前必须回答：它是否有稳定生命周期、独立状态、独立行为、跨实现价值；如果没有，优先保持轻量。
- 架构设计优先保证边界清晰、可替换、可验证，而不是追求“一次设计覆盖所有场景”。

当讨论出现明显发散时：

~~~text
当前议题继续收敛
+
新问题登记 Backlog
+
后续单独讨论
~~~

禁止因为当前讨论方便而跨边界提前实现后续待办。

# 5. 术语规范

架构文档优先采用：

> **中文术语在前，英文标识括号保留。**

例如：

- 执行实例（Run）
- 计划步骤（Step）
- 执行尝试（Attempt）
- 执行动作（Execution）
- 工作空间（Workspace）
- 恢复点（RecoveryPoint）
- 执行结果（Execution Outcome）
- 失败分类（Failure Classification）
- 副作用语义（Side Effect Semantics）
- 状态核对（Reconciliation）
- 幂等键（Idempotency Key）
- 栅栏令牌（Fencing Token）
- 副作用回执（Side Effect Receipt）

代码、Schema、API 字段保持稳定英文命名；设计说明和评审文本使用中英双语术语。

禁止同一个概念在不同文档中随意换名。

# 6. 领域模型原则

当前已接受的 V1 领域关系：

~~~text
Conversation
  └─ Turn [1..N]
       └─ Run [1..N]
            ├─ Plan [v1..N]
            │    └─ Step [1..N]
            │         └─ Attempt [1..N]
            ├─ RecoveryPoint [0..N]
            ├─ Artifact / Evidence
            └─ Terminal Result
~~~

必须遵守：

- Turn : Run = 1 : N。
- Plan 必须版本化，Replan 不覆盖历史。
- Step 与 Attempt 严格分离。
- terminal Run 永不 reopen。
- Workspace、Sandbox、Runtime Session 均不等同于 Run。
- 平台核心 ID 由平台生成。
- Provider / Framework 原生 ID 只能作为 binding / metadata。

详见：

`docs/references/DOMAIN_MODEL_AND_STATE_CONTRACT.md`

# 7. 失败、重试与副作用原则

必须遵守：

~~~text
执行结果（Outcome）
≠
失败分类（Failure Type）
≠
副作用类型（Side Effect Class）
~~~

硬规则：

- UNKNOWN（执行结果未知）禁止盲目重试。
- UNKNOWN 必须先进入状态核对（Reconciliation）。
- Retry = 同一个 Step 意图下的新 Attempt。
- Replan = 当前方案需要改变。
- 所有非 PURE 执行必须声明 Side Effect Contract。
- 所有非 PURE 执行应形成 Side Effect Receipt。
- 高风险副作用无法确认结果时，进入人工介入或 Fail Safe。
- 不承诺任意外部副作用 Exactly Once Execution。

详见：

`docs/references/FAILURE_IDEMPOTENCY_AND_RECOVERY.md`

# 8. Control Plane / Data Plane 原则

Control Plane 负责：

- Run / Plan / Step 状态机
- Retry / Replan / Abort / Complete
- Policy / Approval / Budget
- Recovery / Checkpoint
- 调度决策

Data Plane 负责：

- Model 调用
- Agent Runtime
- Shell
- Git
- Filesystem
- Browser
- MCP
- Sandbox
- Code Execution

禁止：

- Harness Kernel 直接运行 shell/git/browser 副作用。
- Sandbox/Executor 自行决定整个 Run 的最终业务状态。
- Agent 绕过 Policy / Approval 修改业务目标或扩大权限。

# 9. Coding Execution 与 Sandbox

生产 Coding Execution 默认进入隔离 Sandbox。

当前架构方向：

~~~text
ExecutionScheduler
        ↓
CubeSandboxProvider
      /               \
Local Cube Cluster   Remote Cube Cluster
~~~

约束：

- Local Cube = baseline capacity。
- Remote Cube = burst capacity。
- Docker = dev / compatibility / fallback。
- Hyperlight = specialized untrusted function/WASM execution。
- E2B 不作为独立生产 Provider；只保留 CubeSandbox 的 E2B-compatible API/SDK 兼容价值。
- 裸 LocalShell 不作为生产默认路径。

Sandbox Infrastructure Control Plane 不拥有 Harness Workflow。

# 10. 执行环境一致性

Local / Remote CubeSandbox 必须遵守统一 Execution Environment Contract。

环境版本必须通过：

- Environment Profile
- immutable OCI digest
- Environment Registry
- conformance test
- execution environment fingerprint

建立可追踪关系。

禁止生产 Run 使用不可追踪的 `latest` 环境漂移。

基础工具进入 Environment Image；项目依赖进入 Workspace。

# 10.1 运行时拓扑边界

必须遵守：

- Runtime Topology 是运行时事实记录，不是 Plan / Workflow / Scheduler。
- Sandbox、MCP Server 等基础设施对象可以作为 Participant。
- Topology 只记录参与者身份、生命周期和稳定关系。
- 高频 Tool / Shell / MCP 调用进入 Trace / Log，不进入 Topology。
- 不在 Topology 中重建业务状态机、调度器或 Multi-Agent 协商机制。
- Retention 周期由独立待办统一定义。

详见：

`docs/references/RUNTIME_TOPOLOGY.md`

# 11. POC 原则

POC 必须：

- 使用相同业务任务和 Acceptance Criteria。
- Measure First。
- 通过故障注入验证恢复能力。
- 明确 PASS / FAIL / Gap。
- 区分厂商官方事实、讨论估算、实测数据。
- 不把 README benchmark 当生产 SLA。
- 不通过放宽门禁、skip、retry、降低 coverage 获得“通过”。

POC 结论必须给出可重复证据。

# 12. 外部事实核验

涉及以下内容时，必须使用最新官方资料或源码核验，不能仅依赖模型记忆：

- Framework 当前 API
- prerelease / stable 状态
- License
- self-host / cloud 边界
- 扩展点
- Sandbox 能力
- Provider 限制
- 性能数字
- 商业功能断层

优先级：

~~~text
官方源码 / 官方文档
> 官方 changelog / release
> 官方 issue / ADR
> 第三方资料
~~~

讨论估算必须明确标识“估算”，不得伪装成 benchmark。

# 13. 文档与代码变更纪律

修改前：

1. 阅读相关 AGENTS 与现有 Contract。
2. 查找已有实现/文档，禁止重复造概念。
3. 明确本次变更属于 Decision、POC、实现还是修复。

修改中：

- 保持改动聚焦。
- 不顺手重构无关模块。
- 不删除历史 Decision / Evidence 来让新设计“看起来一致”。
- 发现架构冲突时先记录 Backlog，不偷偷绕开。
- Provider-specific 逻辑必须留在 Adapter 边界。

修改后：

- 更新相关文档。
- 补 Contract / Unit / Integration / E2E 测试。
- 运行与变更范围匹配的验证。
- 输出已验证内容和未验证风险。

# 14. 测试与 Correctness

优先级：

~~~text
Correctness
> Recoverability
> Security
> Compatibility
> Performance
> Convenience
~~~

禁止通过以下方式掩盖失败：

- skip 关键测试
- 无依据增加 retry
- 单纯延长 timeout
- 删除断言
- 减少关键平台覆盖
- 忽略 flaky 根因
- 用 Agent 自我声明替代真实 Evidence

所有副作用、恢复、重试相关逻辑必须优先测试异常路径，而不只测试 happy path。

# 15. Git 与提交原则

- 不覆盖已经接受的历史架构决策，应通过新 Decision/ADR 修订。
- 文档与实现提交信息应说明真实意图。
- 不把无关格式化、大规模重排与架构改动混在同一提交。
- 任何 Provider 替换必须证明上层 Domain Model / Workflow 不需要修改。
- 高风险 git.push / merge 等动作必须遵守 Policy / Approval。
- Git Server 是权威主干事实源；Repository Mirror / Cache 只能作为可重建缓存。
- Project Repository 通过静态 Project Manifest 定义项目仓库边界，并承载项目级 AGENTS.md / Skills / 公共规范。
- Project Workspace 可跨 Turn / Run 复用，但 Run 必须冻结自己的 Repository Revision Set。
- Worktree 按 Git Repository 粒度隔离；并发可写 Run / 子 Agent 默认不得共享同一 Worktree。
- 执行过程中不得隐式 rebase/merge 追主干；集成前显式同步 upstream 并重新 Verify。
- 本地 commit 可按 Recipe/Policy 自动执行；push/merge/tag/delete branch/force-push 按外部副作用治理，force-push 默认禁止。
- 项目研发流程和跨仓执行顺序由项目级 Skill 定义，不写死在 Harness Kernel。
- 详见 `docs/references/WORKSPACE_AND_GIT_MODEL.md`。

# 16. 当前架构待办

所有未决问题以：

`docs/ARCHITECTURE_BACKLOG.md`

为唯一主清单。

不要在其他文档维护第二份互相漂移的 TODO 总表。

# 17. 工作完成定义

一个任务只有同时满足以下条件才可宣称完成：

- 范围内实现/文档已更新。
- 相关架构约束未被破坏。
- 必要测试已执行并通过。
- 失败/Gap 已明确记录。
- 重要 Decision 已沉淀。
- 没有把“未验证”描述成“已验证”。
- 没有把“讨论建议”描述成“正式架构决策”。

如果无法完全完成，应明确说明已完成部分、剩余风险与阻塞点，不得伪造收口。
