# DEV-M4 / DEV-M5 · 真实 Hatchet Worker 进程 A→B 接管验证复盘（2026-10-11）

## 验证对象与事实分层

将先前 PR #71 的**同一 Hatchet Worker 内 Native Task Retry + 逻辑 Owner Epoch CAS**推进为真正 **Hatchet Worker A 物理进程 SIGKILL → 独立 Worker B 进程接管**。仍仅限合成非幂等外部 PostgreSQL 账本，不涉及实际业务消费者、Cube Workspace/OCI、Code Runner、审批/Policy、生产跨主机 HA。

根据 Hatchet Embedded 公开的 Fleet 合同，三个独立操作系统进程连接同一个外部 `hatchet_poc` PostgreSQL：控制端在启动时运行 Engine Migration；随后两个 Worker 独立启动 Embedded Engine，`run_migrations=False` 防止并发迁移。技术 Task 排队与 Native Retry 由 Hatchet 自身负责，Harness PG 只记录 Run/Tool Intent/Owner Lease/Fencing/Receipt；外部 `ledger_poc` 没有幂等约束。

## 真实进程故障步骤

1. 控制端创建 Platform Run，提交 Hatchet Workflow，登记相同 Run/Execution ID 的 NON_RETRYABLE Tool Intent 和 A/7 可信 PG Owner。
2. **Worker A 实际进程**领取 Native Task，持久 `DISPATCHED` 后在另一个 PostgreSQL 中提交一个外部副作用，然后保持活跃；此时 Harness 尚未存储 Receipt。
3. 控制端查询外部账本证实恰有一次 Commit，随后 `os.killpg(a.pid, SIGKILL)` 强制杀掉整个 A 进程组（不只是 Tool 子进程），要求实际 OS 退出码 `-9`。
4. 控制端启动独立 **Worker B 进程**（不同 PID），Hatchet 在同一个 WorkflowRun 上发出 Native Task Retry；B 见到已 `DISPATCHED` 的原 Execution，进入 `UNKNOWN`。B 只在 PG Server-clock Lease 已过期之后用 `A/7→B/8` 原子 CAS 取得**仅 Receipt 对账**的恢复许可，旧 A 被 Fencing 拒绝。
5. B 读取外部真实账本的唯一匹配 Effect，确认同一 Execution 的 Receipt；不得调用 `ledger.debit`，也不得新建第二次 Intent/外部写入。最终检查四类持久领域事件各一次。

## CI 实际证据

- PR #72 首轮强制真实 PG/Hatchet Fleet 测试：[CI 38145779308](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38145779308) **SUCCESS**；[Architecture Guard 38145779333](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38145779333) **SUCCESS**；[原有 Inspector/Hatchet 回归 38145779298](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38145779298) **SUCCESS**。
- 首轮真实结果：`outcome=PASS_PHYSICAL_HATCHET_WORKER_A_B`；Run `m4-physical-a20ac5e43930417f85f690e0ace5c95e`；Hatchet Workflow `545db517-6229-4333-9643-2b832a2aaf86`；Worker A PID `3740`、exit `-9`；Worker B PID `3879`；Native Retry `1`；PG Fencing Epoch `8`；外部非幂等写入次数 `1`；Receipt `CONFIRMED_SUCCESS`。
- 同一轮独立 PG Tool Receipt/Owner Fencing 回归 **16/16 PASS**，验证过期 Lease、并发 Owner B/C 只一人接管、旧 Epoch 拒绝、UNKNOWN 之外不能恢复、未执行不推断；Strict M4/M5 OpenSpec PASS。
- 发现/修正：对 Worker 的 PG Binding 等待仅允许并发初始化造成的 `KeyError` 重试，不允许捕捉泛化 `Exception` 后吞掉真实 PG/授权错误（同分支 Refactor）。**最终提交的 CI 结果以最后 Head 工作流为准**，不能拿首轮结果替代最终版本。
- 本次代码主要新增强制测试入口 `verify_physical_hatchet_worker_takeover.py` 与 GitHub CI job，没有把私有应用代码或资料提交公开仓库。

## 边界、风险与阶段判断

- 成功证明：一台 CI 主机上两个独立 Worker 进程（共享技术 Hatchet PG/Fleet）、OS SIGKILL、Native Workflow Task Retry 和恢复后同一 Receipt 对账。**不等于**跨宿主机网络分区/Kubernetes HA；也不等于 Cube Sandbox/Workspace 恢复。
- 受信任的 PG B Permit 只允许 **对账**已有外部副作用；不能把新的 Lease 当作再次调用非幂等 Tool 的理由。外部已 Commit 的行为不能被 Fencing 撤回；当真实外部查询无法唯一确认时应停留 UNKNOWN。
- 本轮 `SIGKILL` 是 Worker A 整组，且控制端保留独立 Hatchet Embedded Engine；不是所有 Engine 同时宕机。Server-side Lease TTL 为测试缩短，与生产 TTL/心跳及长时 Running Step 的恢复政策必须独立定义。
- 没有验证真 Cube Sandbox Allocate/Connect/Release、WorkspaceRef/Git Revision/OCI Digest、Shell/Files/Git Guest 隔离，也没有非幂等真实第三方 API（这里是合成数据库）。
- DEV-M4、DEV-M5 **ACTIVE / OPEN**，M9 Production **NO-GO**；相关主阶段 0.1/0.2、1.x/2.x 完整门禁不因本子切片关闭。下一实测优先 Cube Workspace A→B 重连、跨 Scope/Lease 失效拒绝和资源释放。
