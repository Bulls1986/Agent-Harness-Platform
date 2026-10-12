# Inspector · 单新增 Tab「能力验证」与需求分析审核保留（2026-10-12）

## 实际交付与使用场景

本切片保持原 Inspector **同一页面**，仅增加一个顶层 `能力验证` Tab，已有第一 Tab 明确命名“需求分析与独立审核 · 双 Agent”。原持久化 Run/Result/历史/SSE 与真实 Hatchet 调度未更改。新 Tab 是对平台能力的可解释验收入口，不再让用户只看 JSON；各卡均阐述业务使用场景、所证明能力、实际执行步骤、验收证据与边界。

1. **需求分析 → 独立审核**：节点 A Pydantic AI 在真实 Live 模式提取结构化需求（feature、summary、capabilities、business_rules、acceptance_criteria），节点 B OpenAI Agents SDK 读取 A 的已持久化结果并出具 `PASS/NEEDS_WORK`、issues、risks、recommendations，Harness 输出人类可读的需求分析与审核报告。默认本地确定性模型只证明双 SDK 调度/传值，不生成真实报告。此前功能**保留且明确标注**。
2. **Cube Workspace 恢复**：研发/测试 Agent 恢复同一 Sandbox/Workspace 数据，要求原生 Guest 字节、PG Owner A/7→B/8 Fencing、旧 Owner 拒绝及 Cube Kill ACK；在 Inspector 中当前仅可查看已保存 PG 事实，不能无授权发起真实 Cube。
3. **Hatchet Worker A→B 接管**：必须核验独立进程 PID、真实 A SIGKILL -9、原 Native Workflow Retry、B 新 Epoch 和原 Cube 文件；**M5 Cube+Hatchet 物理联合 Gate 未 PASS，不能宣称完成**。
4. **非幂等 Tool Receipt**：外部系统实际完成副作用但 ACK 丢失后，UNKNOWN 不重派、唯一可信独立外部证据确认、没有重复写入；PG 事件只证明平台记录，不证明外部效果。

## 关键实现

- 复用 `poc/closed_loop/inspector.html`，两个 Tab 仅原演示/能力验证，没有额外 Demo 站点、第二套技术 Scheduler、浏览器端 Host Shell 或 SIGKILL 接口。
- `GET /api/verification/scenarios` 提供有界场景定义；`GET /api/verification/evidence/{run_id}` 从真实 Harness PG 只读 Run/ProviderID、白名单事件、可选 Cube SandboxID/WorkspaceRef/Owner/Epoch/Binding State 和 Tool Receipt State。全部返回 `evidence_level=PERSISTED_FACTS_ONLY`、`verified=false`；不返回 Run 原始 Prompt、模型流 Token、敏感业务负载。无记录或数据库不可用明确 404/503；非法 ID 422。
- 旧两个 SDK 的 Live 需求分析与审核代码在 `poc/closed_loop/real_model.py` 沿用 `RequirementsDraft`、`ReviewOutcome` 与 `render_business_report`；只增强原页面的含义解释，不重构原链路或修改领域状态。
- Tab 切换支持键盘和独立加载故障；所有动态文本只用 `textContent`，不使用 `innerHTML`。Cube/物理故障/非幂等工具仍为 **READ_ONLY_NOT_EXECUTABLE**，没有任何假“执行成功”按钮。

## TDD：真实失败和修复

1. 先创建 `poc/closed_loop/test_inspector_capabilities_pg.py`，完整约束四类场景、PG 事实拒绝伪 PASS、缺失 Run/非法 ID、新 Tab 原页面合同；未实现时测试为 Red。
2. 初轮 [CI 38210310339](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38210310339) 实际在 **40 项真实 PG 合同中有 1 项失败**：测试错误地期待一个**根本不存在**的特权 POST 路由返回 HTTP 405，FastAPI 正确返回 404。修复**测试断言**为 404，未为此新增不安全的 POST/SIGKILL 路由。
3. 补回用户要求的业务语义——原 Tab 明确写出结构化需求 → 独立审核的业务链路，同时强制说明默认确定性模型和显式 Live 的差异。

## 最终真实 CI 证据

- [Closed-loop PG + Hatchet + HTTP Inspector CI 38210468250](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38210468250) **SUCCESS**：真实 PostgreSQL/API 合同 40/40 PASS、架构单测 8/8 PASS、Strict Inspector OpenSpec PASS、浏览器 JavaScript 语法检查 PASS；真实 Hatchet Engine 的双 SDK 工作流、v1→v2 事实恢复与 Inspector 真实 HTTP 提交/运行历史/重启回放均 PASS。
- [Architecture Guard CI 38210468286](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38210468286) **SUCCESS**。
- 文档收口后的最后 HEAD CI 需要再次核实通过才可合并，不用先前提交的 CI 结果冒充最终状态。

## 复盘与未关闭门禁

- 不同层级的证据必须明确：数据库绑定记录 `sandbox.binding.confirmed` ≠ 原生 Cube Guest 文件内容保留；PG Fencing 转移 ≠ Worker OS 实际 SIGKILL；Tool Receipt 终态 ≠ 独立外部系统唯一副作用。所有场景都需要可解释的“使用场景—证明标准—原始可信证据—局限”。
- 本次是**Inspector 演示可读性与只读数据观察层**，并未实现有认证的 Cube/Worker/Tool 一键故障场景启动器。以后必须通过可信授权后端执行，并且存储操作系统/Provider/Guest/外部 Effect 的独立 Evidence；不应让公开页面直接拥有 Host SIGKILL 权限。
- Inspector POC 仍 localhost-only；未有生产 IAM、授权、数据脱敏体系；不可外网公开。DEV-M5 物理 Worker+Cube 联合故障和完整阶段收口继续 OPEN，Production NO-GO。
