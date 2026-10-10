# HC-01 · Harness ↔ Hatchet Workflow Mapping Contract

> **2026-10-10 · DECIDED / Architecture Implementation Contract**（映射与领域语义已冻结；Hatchet 动态 Workflow/Child 行为尚待 POC）。
> 归属：ARCH-TODO-025/028。依赖：[Accepted Domain Model](DOMAIN_MODEL_AND_STATE_CONTRACT.md)、[Failure Contract](FAILURE_IDEMPOTENCY_AND_RECOVERY.md)、[Registry](REGISTRY_AND_VERSIONING.md)、[ADR-031](THIN_HARNESS_CONTROL_PLANE_DECISION_20261010.md)。
>
> 本文只冻结由平台拥有的身份、版本、关联和流程边界；不声称 Hatchet 指定版本已支持任意在线变更运行中的 DAG。Hatchet Workflow/Task 的技术状态权威仍在引擎。生产 GO 需由集成 POC 确认。

## 1. 唯一权威与映射决策

- **Platform Run**：承载一次业务意图的领域执行实例；终态不可重新打开，重做生成 New Run。
- **Platform Plan Version**：一次 Run 内可有 v1..vN，Replan **新增版本**，不覆盖旧版本；既有 Step/Attempt/Artifact/Receipt 的历史永不删除。
- **Platform Step**：版本化、稳定的业务工作单元/意图；完成需要平台 Verification PASS（若配置）。技术上可由一个 Hatchet Task、多个 Task 或受控子 Workflow 实现，**不强制 1:1**。
- **Platform Attempt**：针对某个 Step 的一次具体 SDK/Tool 执行尝试；每次重新执行真实可能带副作用的代码，必须有可区分 Attempt/Execution 并获得可信 Lease/Fencing。
- **Hatchet WorkflowRun/TaskRun**：具体调度实例及真实技术状态，所有 ID 只记录在 ProviderBinding，不成为领域 ID。
- **推荐默认映射**：一次 Platform Run 的**初始 Plan 对应一个主要 Hatchet WorkflowRun**；未触发 Replan 时尽量保持单 Workflow。经批准的 Replan 可以创建该 Run 关联的**新的 Workflow Segment/子 Workflow**，沿同一 Platform Run 继续。不要假设一个 Run 永久只能拥有一个 Provider Workflow ID，也不要求在线修改已部署/正在执行的 Hatchet DAG。
- **编排源**：冻结的 Recipe/Plan/Step 依赖是平台源数据；Hatchet Adapter 将**当前冻结版本的执行段**映射成引擎 DAG。验收结果、Approval/Receipt 安全门禁作为显式步骤/输入条件/受控等待，不允许模型或 SDK 自主放行后继任务。

## 2. 可实现的绑定结构（逻辑 Schema，非最终 DDL）

| 字段 | 含义与约束 |
|---|---|
| `run_id`, `plan_id`, `plan_version` | 平台权威；一个 Run 多 Plan Version |
| `segment_id`, `segment_ordinal`, `previous_segment_id?` | 平台生成的执行段 ID；同 Run 按已持久的 Replan Decision 串联；只有一个活动可写 Segment |
| `step_id`, `step_version`, `attempt_id?`, `execution_id?` | 平台稳定身份；技术 task 可能多对一、Attempt 与 Provider retry 并非固定一对一 |
| `provider`, `provider_workflow_run_id`, `provider_task_run_id?`, `provider_retry_ref?` | Hatchet opaque 关联与实际 SDK/Engine 返回的标识 |
| `workflow_definition_version`, `runtime_adapter_version`, `recipe_digest` | Run 创建时冻结；恢复禁止静默升级为 latest |
| `binding_revision`, `idempotency_key`, `parent_ref?` | 绑定写入/确认使用幂等键与 CAS；已确认 Provider 标识不可擅自改写 |
| `step_execution_kind` | `PURE`、已声明副作用或等待/恢复操作；供 Retry/Receipt Gate 使用 |

**唯一键/约束**：`(run_id, segment_ordinal)` 和 `(run_id, plan_version, step_id)` 唯一；有效 Provider `(provider, provider_workflow_run_id)` 不得分配给另一业务 Run。Provider Task 可能细分平台 Step，故需允许多个 Task Binding/Step。只记录足够恢复/对账的技术标识，不镜像 Hatchet 内部完整 Task History。

## 3. 正常执行与依赖放行

1. Run 创建：冻结 Recipe/Adapter/Model/Policy/Tool/OCI Digest → 持久化 Plan v1 + Step 依赖与执行 Segment → 经 HC-02 Outbox 请求 Hatchet 创建 Workflow。
2. Hatchet 以其 DAG 决定技术就绪/入队；Worker 每次调用 AgentRuntime 前经 HC-03 获取可信 ExecutionContext。**Step 的业务完成**以结构化 Outcome + Verification/Policy/Approval 为准，不能仅凭 Hatchet Task SUCCEEDED 推断。
3. A → B 跨 SDK 交接：A 的 `ArtifactRef/Digest/Scope/Lineage` 与 Verification PASS 持久化后才允许 B 读取；B 不持有 A 的裸 Sandbox ID 或未授权全量聊天历史。
4. 如独立 Engine Task 已完成而领域 Event 丢失，HC-02 先核对 Provider/Artifact/Receipt 并幂等补写，不自动重复执行已完成 Step。
5. 条件分支与有限并行允许由冻结 Recipe/Plan DAG 显式建模；**动态 A2A/无限递归子 Agent/运行中任意 DAG 热编辑**不作为 V1 前提。

## 4. Retry、Resume、Replan 的不可混淆合同

| 情形 | 平台语义 | Hatchet 处理 |
|---|---|---|
| 已证实无副作用/可安全重做的 Step 重新运行 SDK/Tool | **Same Run + Same Step + New Attempt** | 可以使用受控 Hatchet Retry/新 Task；进入 Runtime 前建立新 Attempt/Execution |
| 只恢复技术等待/挂起，SDK 原生支持继续同一 Attempt | **Same Run/Step/Attempt Resume** | Provider wait/wakeup/Resume；不可误建 New Attempt |
| Hatchet 内部任务交付/调度重试，尚未执行 Runtime/Tool | 同一平台 Attempt 可保持未开始；以是否真实开始执行为界 | Provider 自行重派；不能把每条 Engine 内部 Retry 都当新业务 Attempt |
| Worker 已调用外部非 PURE Tool，结果可能发生但 ACK 不明 | **UNKNOWN → Reconciliation** | 禁止自动重放该 Tool；先查可信 Receipt/外部结果 |
| Verification 失败需修改方案/依赖 | **Same Run + New Plan Version + 新 Segment** | 关闭/阻断旧 Segment 后继并以稳定 Link 创建新 Workflow Segment；不重写已完成旧 DAG |
| 用户 Regenerate / 新业务请求 | **New Run** | 创建新 Root Workflow，不 reopen 原 Run |

**重要**：平台可配置 Hatchet 纯技术 Task Retry，但**未经 HC-02/HC-03 安全准入，不得用引擎重试包围不确定的 SDK Tool 副作用**。默认把可能含副作用的 Agent 执行包装成 `fail-closed` 的执行关口，而非裸 Hatchet 自动重跑。

## 5. Replan 决策事务与失败窗口

1. 当前 Plan 的 Verifier 产生 `REPLAN_REQUIRED` + 原因；Harness Domain 验证限制（如 max_replans）与副作用状态。
2. **先证明**尚未完成或仍活跃的旧 Segment 下游不再会被错误执行：等待/取消是受控请求，必须等待可信的停止/安全边界或将其置为 UNKNOWN，不以 Cancel ACK 当 TERMINATED。
3. 在平台事务中新建 Plan vN+1、不可变 Step 列表、`supersedes` 与 `ReplanDecision`；已完成的业务成果引用旧 Plan 的 Evidence/Revision，不丢失历史。
4. 为 vN+1 创建新 Segment Outbox + 幂等启动；若尚未确认旧 Segment 停止，**不放行有副作用的新 Segment**。
5. 新 Segment 与相同 Platform Run 绑定；Domain Run 终态依已冻结业务规则/Verification 裁决，不直接使用最后一个 Hatchet Task 终态。
6. 如新 Segment 创建 ACK 丢失，按 HC-02 外部 ID/幂等键核对，不产生第二个同一 Segment；如 Replan 已提交但新 Segment 失败，可安全补投，不重开旧 Segment。

## 6. 接口边界（概念 SPI，不声称存在现成的 Hatchet API）

```python
# Platform-facing protocol sketch, NOT a verified native SDK signature
class ProcessDurablePort:
    async def ensure_segment(self, frozen_segment, idempotency_key) -> ProviderBinding: ...
    async def get_provider_state(self, binding) -> ProviderExecutionState: ...
    async def request_cancel(self, binding, reason) -> ProviderCancellationReceipt: ...
    async def resume_wait(self, binding, verified_decision) -> ProviderOperationRef: ...
    async def observe_task(self, binding, provider_event) -> ProviderProjectionInput: ...
```

`HatchetProcessAdapter` 使用公开 SDK/HTTP 接口实现上述语义；动态定义/注册 Workflow/Child Key/Cancel/Wait 的具体公开 API 与版本兼容由 POC 验证，功能不具备时显式 `UNSUPPORTED`，**禁止用自造第二套 Durable Scheduler 假装兼容**。

## 7. 可执行验收门禁（集成 POC 待完成）

- M01 单 Run A(Pydantic) → B(OpenAI/OpenCode) → Verification；A 失败/拒绝时 B **0 次**实际运行，ArtifactRef/Digest/Scope 可核对。
- M02 Verifier 触发 Replan：v1/v2、各 Step/Attempt/Segment 可追溯；旧 Segment 已完成 Step 0 重放；旧工作未安全停止时新副作用 0。
- M03 Hatchet Worker A 失联、B 接管：Provider Task 历史按 Hatchet 恢复；平台 Retry/Resume/Attempt 的语义与真实 Runtime 调用次数一致。
- M04 创建 Segment 请求/ACK 丢失后重复补投：同一 `(run_id, segment_ordinal)` **最多一个有效 Workflow**；如 Provider 无法证明去重必须阻断而不是默认创建多个。
- M05 版本冻结：新部署 Adapter/Workflow Definition 后，旧 Run 的已冻结版本继续或明确拒绝恢复，不能使用 latest 静默漂移。
- M06 数据/SDK/定义升级及 Workflows 动态/子工作流公开 API 的真实支持验证，逐项 `LIVE PASS / UNSUPPORTED`，不得将合同当成已完成实现。

**结论：映射与安全语义 DECIDED；具体 Hatchet API、动态 DAG/子 Workflow、实际 Retry/Resume 行为属于实施验证，ARCH-TODO-025/028 保持 OPEN。**
