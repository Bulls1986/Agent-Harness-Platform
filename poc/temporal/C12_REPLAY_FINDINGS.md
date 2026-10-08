# POC-C C12 — Native Temporal Workflow History Replay 兼容性门禁

> 2026-10-08 | **原生 OSS Temporal + PostgreSQL 历史 Replay 实测 PASS（部署前静态兼容性检测）**
>
> 此处证明的是部署前能查出显著不兼容的 Workflow Command
> 演进，不是新 Worker 镜像实际接管、Build ID Versioning、
> workflow patch/migration 或生产升级零停机的完整证明。

## 1. 运行与验证范围

- 官方 `temporalio==1.34.0`，非 `start-dev` 的
  `temporalio/server:1.31.0`、独立 PostgreSQL 存储。
- 创建真实 Native `poc-c-document-review` V1 Workflow，
  分别调度 fixture Agent/独立 Verifier Activity，第一次 Verify
  FAIL 后经 Approval Signal 触发 Plan v2、最终 COMPLETED。
- 通过 SDK 官方 `WorkflowHandle.fetch_history()`
  读取该已完成实例的**真实持久化 History：33 个事件**。
- 先停掉 Worker，再执行两个**同一份 History** 的
  `temporalio.worker.Replayer` 校验。
- **V1 正例**：`Replayer(workflows=[DocumentReviewWorkflow])`
  返回 `replay_failure=None`。
- **不兼容 V2 负例**：新类保持**相同 Native Workflow TYPE**
  `poc-c-document-review`，但将第一条 Command 从原本的
  `ScheduleActivityTask` 修改为 `StartTimer`。
  Temporal 原生报出
  `NondeterminismError`：
  `Timer machine does not handle ... ActivityTaskScheduled`。
  该失败来自原生 Command/History 不匹配，不是 Python 导入错误
  或手写 ID 检查。

这是可重复的**部署前阻断证据**：候选新版本必须对代表性的历史样本
做官方 Replayer 校验，失败版本不得接管该队列的存量 Workflow。
这不意味着 Temporal 自动为应用层任何未来改动提供无条件兼容。

## 2. 确定性与副作用边界

- 实现将 `IncompatibleDocumentReviewWorkflow` 放在独立的
  `incompatible_workflow_v2.py`，其中没有文件、DB、HTTP
  或进程操作；`verify_workflow_replay.py` 是测试 Driver。
- 初次测试由于 V2 类与 Driver 写在同一模块，被 Temporal Sandbox
  在 `pathlib.Path.resolve` 导入行为上正确拒绝，
  **这是 Sandbox 的约束而非 Workflow Replay 结果**。
  拆分模块后得到真正的原生 `NondeterminismError`，
  未禁用或绕过 Sandbox。
- Replayer 不注册 Activity 实现，也没有活跃 Worker 在测试
  期间可调用外部 Tool/Model/Sandbox。
  因此本实验不会新派发副作用，但并非验证生产环境实际
  不兼容 Worker B 镜像接管时的副作用隔离。
- C06/C07 已独立证明 NonRetryable 外部 Tool Admission 必须
  受 Harness PG FrozenBinding + Fencing 约束；
  **Replay preflight 不能替代真实 Tool dispatch gate**。
- 真实方案仍需声明 workflow version/build ID、patch/
  worker-rollout、长任务在途版本保留、回滚和不兼容代码上线
  失败策略，遵循企业部署治理，不把 Native Server 机制重做成
  Harness 自研迁移器。

## 3. 可复现入口与退出条件

```bash
# 使用 C05 已验收的 OSS Temporal Server + PG，自带隔离 Worker。
export POC_C_TEMPORAL_ADDRESS=127.0.0.1:17234
python poc/temporal/verify_workflow_replay.py
```

本机真实 History 的 V1/V2 Replay 正反验证 PASS，GitHub
[CI #37770188545](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/37770188545)
中 `selfhost-oss-postgres-proof` 的 **C12 Native Replay 步骤 SUCCESS**，
其他两组作业也全部 SUCCESS。对应
[PR #29](https://github.com/Bulls1986/Agent-Harness-Platform/pull/29)
已经合并 main；因此 C12 **部署前 Replay 子项最终 scoped PASS**。

**结论：C12 部署前 Native History Replay 负例 PASS，
但真实不兼容 Worker 接管/镜像身份、生产版本管理仍 GAP；
不将整个 POC-C 或 G6 标为全面通过。**
