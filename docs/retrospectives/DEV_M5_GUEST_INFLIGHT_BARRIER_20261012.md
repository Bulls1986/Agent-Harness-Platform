# DEV-M5 OpenCode Guest 在途副作用防护复盘（2026-10-12）

## 本轮结论与真伪门禁

PG 在途工具接管屏障已完成 Red→Green，并在真实 PostgreSQL 16 上通过同步与并发合同。此前真实 OpenCode v2 Native Session、Shell、Files、VCS 已在 Cube MicroVM、Hatchet Worker A SIGKILL -> B Native Retry 和同一 PG Scoped Workspace 中通过。**但“阻止不安全接管”不等于“强制杀死任意 Guest 后台进程”。完整 DEV-M5 1.3/2.1/2.3 保持 OPEN。**

## 缺陷与修复

之前 BoundOpenCodeGuest 的 Native Shell 请求仅在 HTTP 前后复核 PG Owner/Epoch；OpenCode Shell API 可能异步执行。即使 A 被 SIGKILL，Guest 中已触发的 Shell 仍可能继续，而 B 在 A Lease 过期后可以接管同一沙箱。

新增 PostgreSQL 表 harness_cube_guest_effect，记录执行 ID、Owner、Epoch、工具种类、操作意图摘要、DISPATCHED/CONFIRMED 与已确认回执摘要。BEGIN EFFECT 必须在同一 PG Sandbox Binding 行锁下执行，并且发生在任何 HTTP 副作用之前；该执行已有 DISPATCHED 状态时拒绝第二个 Tool。Takeover 和 Release 均在相同行锁下检查 DISPATCHED，一律拒绝未知结果的盲目重派或销毁。

新增每笔 Shell 随机终态 marker，前台命令成功退出后才写入 Guest 回执文件。确认需要同时读回预期文件字节和对应 marker，并经过同一 PG 当前 Owner/Lease/Epoch 的 CAS；文件提前出现、marker 尚未写入时不允许标为 CONFIRMED。HTTP 错误、Worker 物理故障或授权过期都留下可查 DISPATCHED。绝不自动清除在途记录以“解决”卡住的任务。

## TDD 证据

- 真实 PG 红灯：原先没有 begin_guest_effect 等事务操作，新增 3 个测试先 RED；引入 PG 记录、事务隔离和拒绝逻辑后 3/3 GREEN。加上并发 HTTP 故障窗口，A 的已 dispatch 但未完成请求碰上 Lease 过期时，B 接管被拒绝；即使 A 之后收到 HTTP 响应，旧 Lease 仍无法提交成功回执，B 继续 fail closed。
- Mock Native 负例：只有输出文件、没有 Guest 终态 marker 不得 CONFIRMED；Native HTTP 报错后仍必须保留未确认记录。
- 完整真实 PG Cube OpenCode 正常路径回归：Run m5-opencode-pg-0dd50d8a00724f98a9563833a99d23f4、原 Sandbox 6b3562554cca44238bec992662e51ca7、原 Session、PG Fencing 7 -> 8、旧 Owner/Scope 拒绝、B 继续执行 Shell/Files/VCS，Destroy ACK RELEASED，进程退出 0。
- 历史完整物理 OpenCode Gate：Run m5-joint-33728323da044a308cf02f91f619c10f、Sandbox 77579476b0b94e16acd799957c22648f，A OS SIGKILL -9，B Native Retry 1、原 Native Session/Guest 数据连续。该历史通过发生在本次 PG Effect Ledger 引入之前，不能用作新代码的物理 Gate PASS。
- **PG Effect Ledger + Guest 前台终态 marker 后的最新物理复验 PASS**：Run m5-joint-02d6561f68064dadb46555eeb486756c、Workflow 1633b6df-0028-4f79-8206-5c3640351083、Sandbox e5427b7efa6e4ec09f8663f82390a234、Native Session ses_ecf6f5585ffe9ES8rdFckW4qLT。A PID 456553、OS SIGKILL -9；B PID 457367、Native Retry 1、原 Cube/Session/Guest 原文件一致；PG Fencing 7 -> 8；Native Shell/Files/Git 正常，PG effect_receipts_confirmed=2、effects_pending=0；Destroy ACK RELEASED，Cube 健康检查 sandboxes=0；脚本退出码 0。**只证明前台受控命令及其回执；不证明任意 detached 后台进程被强制杀掉。**
- **新增真实在途 Guest 沙箱级隔离门禁 PASS**：OpenCode Native Shell 执行前景写入 started 后进入 45 秒休眠，HTTP 客户端先遇 ACK Unknown；PG 仍为 DISPATCHED，Lease 故障注入过期后 Worker B Takeover 被拒绝。受信任的独立隔离路径只允许核对原 Scope/Workspace/Environment 与原 Cube Provider 身份后，向 Native Cube 发 Destroy；保留 PG Effect 未确认状态并记录隔离完成事件。最终实机 Run m5-containment-b1712253e0cf40e28dc25c0a33866f0d、原 Sandbox 3fb0a85e54114a3b891f51cdeae6095f、原 Native Session ses_ecf4d18c3ffesHn4pEDk7fgQns，Native Destroy ACK RELEASED、Provider List 原 Sandbox 不再存在、脚本退出 0，返回 PASS_REAL_OPENCODE_GUEST_INFLIGHT_CONTAINED。**它通过销毁整个原沙箱实现隔离，不保存原 Session，不能证明任何沙箱外部已产生的影响可回滚。**
- **根因记录**：最初隔离失败落在 Cube Native get_info 元数据验证；SDK 返回全部 Harness 冻结元数据字段正确，同时追加 11 个 Provider 自有字段。原适配器将元数据字典严格全等比较，错误拒绝合法原沙箱。以真实 PG 先 RED 再 GREEN，改为所有 Harness 可信字段逐项值严格匹配、允许附加 Provider 字段，篡改/遗漏冻结身份字段仍 fail closed；PG Cube 合同 23/23 PASS，真实隔离重跑 PASS。

## 明确未满足的硬门禁

## PR Head CI 首轮回归根因与修复

提交 66a2aa9 后，Architecture Guard 与 DEV-M5 PG/SDK 两个 Workflow 第一次均 FAILED，而 Inspector Closed Loop SUCCESS。读取 GitHub Actions 的**实际失败日志**可知不是产品行为回归：新增负例导入的 poc.closed_loop.facts 需要 psycopg，而架构最小环境没有安装；真实 Native Worker 证据校验模块导入 pydantic，而 PG/SDK 最小环境没有安装。已在对应 Workflow 显式补充 psycopg[binary] 与 pydantic 版本上界，重新以本地 41/41、PG 19/19 和严格 OpenSpec 执行验证；修复后仍须以最新远端 Head CI 结果为准。

本轮已在真实 Provider 上证明**原整个 MicroVM 毁灭式隔离**（且无法再恢复原 Session），但**没有**证明不销毁沙箱的 Guest 工具进程级精确撤销，也没有任何保证能回滚外部非幂等副作用。UNKNOWN Native Tool Receipt 的权威对账、隔离与重建新工作区所需审批/恢复协议尚未完整；正式产品仍不能自动释放 Pending、盲重放 Tool 或将被隔离 Run 报告为成功。此恢复 API 仅存在于受信任 Python 内部适配层，没有通用操作员 IAM/审计工作流。完成其剩余硬门禁之前，DEV-M5 1.3/2.1/2.3 继续 OPEN。
