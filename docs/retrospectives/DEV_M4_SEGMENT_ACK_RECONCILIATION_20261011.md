# DEV-M4 · Segment 创建 ACK 丢失的受控 Provider 对账（2026-10-11）

## 边界

针对 DEV-M3 的 **v2 PURE Workflow Segment Outbox** 演示真实创建成功、客户端 ACK 丢失、未知绑定对账。Harness PostgreSQL 持有 Outbox/Plan/ProviderBinding，Hatchet 持有真实 WorkflowRun。**不**做第二套 Scheduler，不自动重发 Workflow 创建，不认为取消 ACK 为 Worker 已退出。不覆盖通用 M4 Outbox/Inbox、Tool Receipt、SIGKILL、Lease/Fencing、真实非幂等副作用或生产准入。

## TDD 与失败发现

1. 先写真实 PostgreSQL `test_replan_ack_pg.py` 及 CI，再实现：首次 [Red 38142140618](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38142140618) 因 `poc.closed_loop.segment_reconcile` 尚不存在失败。
2. 实现 `SegmentReconciler.reconcile_unknown`：只允许 `BLOCKED_UNKNOWN` + 冻结 Plan v2 + 可信 Provider 查询唯一候选补录；不存在、多条、不同 Run/版本/Command、复用旧 Workflow ID、Provider 查询失败全部保留 UNKNOWN。对账事务写入原有 Segment Binding，幂等重复不会再次调用 Provider/触发创建。
3. 真实 Hatchet SDK 1.42.1/Engine v0.110.5 联调发现：调用 `second.list_runs(additional_metadata=...)` 返回 **2 条**，包括其他 Run 的 `harness_command_key`，说明不能信任此过滤已经在 Provider 端执行。第一次 live CI [38142256547](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38142256547) 正确 Fail Closed，阻止了错误绑定。
4. 新增 `HatchetSegmentLookup`：即使 Provider 原生过滤被忽略，也对每个返回的 `additional_metadata` 的 Command Key/Run/Plan Version 做 **本地精确匹配**，读取 Provider `metadata.id`，并分页至最后一页；若分页上限/异常，保留 UNKNOWN。单元负例覆盖跨页多候选、忽略过滤、元数据不匹配、Native ID 缺失及列表不可用。
5. 添加本地严格匹配和完整分页后，[真实 PG/Hatchet CI 38142456717](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38142456717) **SUCCESS**：34 项 PG/API/Model/Stream/M3/M4 合同测试 PASS、8 项架构合同 PASS，正常 v2 创建与模拟 ACK 丢失后原生查询补绑两条实际 Workflow 验证 PASS。
6. 真实 ACK 丢失 E2E：Platform Run `m3-hatchet-34134ed70df840379f9754fe75671c35`；初始 v1 Provider `b528c54c-56d4-4d5e-8dbb-9cbe044b11c6`（原生 COMPLETED），新 v2 Provider `aa7f7f8a-235b-464a-a63c-7ff6b07f2307`。创建 ACK 人为丢弃后先进入 BLOCKED_UNKNOWN；Hatchet 查询精确补绑至同一个 Provider ID，最终 Segment `CONFIRMED`，Plan Version=2，事件数 9。返回 `simulated_creation_ack_loss=true`；旧 Worker Cancel 与非幂等 Tool/Receipt 均明确 `NOT_TESTED`。
7. 增加真实 PostgreSQL 双 Reconciler 并发冲突测试：两个对账者在同一 `BLOCKED_UNKNOWN` Segment 下收到不同 Provider 候选，PG CAS/行锁只允许其中一个写入有效 Binding，领域对账事件仅发生一次。[CI run 38142745445](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38142745445) SUCCESS；[Architecture Guard 38142745286](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38142745286) SUCCESS。
8. PR 最后提交的 CI、OpenSpec Strict/门禁审查证据以最终 Head 对应的 GitHub Actions 为准；不把子切片成功上升为整阶段 Gate。

## 安全与局限

- 真实 ACK 丢失的模拟方式：Hatchet `second.run(..., wait_for_result=False, additional_metadata=frozen)` 实际接受请求，调用方故意不写入返回的 Provider ID，转为 `BLOCKED_UNKNOWN`，再通过 **新的 Native Provider List 查询**找回唯一 Run 并确认 PG 绑定；不从缓存的 `ref2.workflow_run_id` 补写。只有补绑确认后才放行 v2 Worker。
- 查询器为可信后台 Adapter；Metadata/Workflow ID 不接受前端 Header 或模型输出，拒绝把“过滤调用成功”视为匹配证据。
- 当前过滤/分页并不是跨系统严格 Exactly-Once 证明：并发重建、元数据可见性/一致性、严重分页压力、超出扫描窗口、Provider 多候选、没有任何可验证 Run 都必须持续阻断；实际私有工具写副作用需要专门 HC-02 Receipt 独立验收。
- 本次只能证明本地 Engine、双数据库和 PURE Segment 的狭义 ACK 窗口，无法替代真实 SIGKILL/并发调度器、跨 Worker / Cube 的全套门禁；DEV-M4 整体不能关闭。
