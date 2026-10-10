# 复盘：让 Run Inspector 真正说明执行过程（2026-10-10）

> **范围：** OpenSpec `explain-run-inspector`；基于已合并的 `minimal-run-closed-loop`。演示 POC SUCCESS 不等于生产 HC-01/02/03 Accepted。
>
> PR [#56](https://github.com/Bulls1986/Agent-Harness-Platform/pull/56)，架构 CI [38039434810](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38039434810)、真实 PG/SDK/Inspector CI [38039434789](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38039434789) 均 SUCCESS。

## 1. 用户反馈与原始问题

用户打开页面后无法理解“这是做什么”“两个节点分别做了什么”“最终返回什么”，只能看到 JSON 列表。原因并不是引擎没有执行，而是 UI 仅具备技术视角的 `Step.output` 与 `Event.data`，缺少任务目标说明、节点语义、可展示原始输入和完整业务 `RunResult`。需求验收此前偏重真实 DAG/数据库可运行，**未给非开发者建立结果可解释性门禁**。

## 2. 先失败、再最小实现、再真实验证

1. **Red**：先扩展真实 Docker PostgreSQL 合同测试：`create(prompt=...)` 原本不支持，`snapshot.input_prompt`/`snapshot.result` 不存在，Step B 接力输入不可见；HTTP 页面也缺少“这个演示验证什么”“节点 A/B”“最终运行结果”和默认收起 JSON。这些断言最初明确失败。
2. **Green**：在 Harness **自有** PG Run 表中用向后兼容 `ALTER ... IF NOT EXISTS` 添加可空的 `input_prompt`/`result_json`；Run+Outbox 创建事务保存 Prompt，业务 `complete()` 在合法终态 CAS 同一事务保存 `final_output`、`result_source_step`、`mode` 与每步输出。
3. **真实关联**：Step A 输入使用 Run 原始 Prompt，Step B 输入必须来自已经持久化并验证通过的 Step A 输出（只有 B 产生 Attempt 时才展示其输入）；旧记录没有 Prompt 时返回 null，不编造；旧已完成 Run 的 Result 只能从保存的节点 B 输出派生，明确 `derived_legacy_step`。
4. **UI 最小变更**：页面头部直接解释用途与 POC 限制；**优先展示最终 RunResult**，其次两个节点的职责/输入/输出、中文事件摘要；原始 JSON/Provider ID 置于默认关闭的 `details`。所有用户/模型输入经 `textContent` 展示，不执行富文本。
5. **测试**：真实 Docker PG/API 7 tests PASS，无 skipped；实测 PG 上真实 Hatchet+Pydantic AI+OpenAI Agents SDK HTTP 黑盒 PASS：Run `run-2e0fa189e0b34d40b38d241384d0deb7`，Workflow `ad4b686e-e6f9-4175-aac3-9343899d0923`，14 个持久事件，`result.final_output = openai-sdk-real-run`，Step B.input=Step A.output；重启 Inspector 后同 Run 查询再 PASS。对旧 Run `run-1f9cc8929f534de3b5f273701c59c543` 验证 input_prompt=null 且 `provenance=derived_legacy_step`；不虚构历史输入。
6. **CI**：OpenSpec strict validation PASS；Architecture guardrails SUCCESS；真实 Docker PG + SDK + Run Inspector/restart CI SUCCESS。实时网页在本地 `http://127.0.0.1:8765` 可打开；尚未进行跨浏览器的完整视觉回归，因此不额外宣称视觉验收。

## 3. 最有价值的经验

- **演示的验收标准不只是“底层任务成功”，而是“一打开页面就知道为什么做、每个节点做什么、输入输出从哪里来、整个 Run 返回什么”。** 用户可见结果是业务/平台可解释性的一部分，必须在 OpenSpec/测试阶段写明。
- **Runtime Terminals ≠ Domain Terminal**：两个 SDK 分别完成，只有 Harness 完成域级验证之后才显示 Run 已完成；UI 不应直接从 Hatchet 技术状态推导业务结论。
- **区别技术验证与模型智能**：真实 SDK 调用 + 固定本地 Model 并不意味着真实需求分析。必须在页面醒目披露确定性模型、无远程 LLM/Token SSE，不能让测试文案伪装成业务输出。
- **Raw JSON 是排障入口，不是正常 UI**：默认结果视角优先；技术细节保持可展开可复制即可。
- **迁移不伪造历史事实**：新增字段采用兼容迁移；旧 Prompt 不存在就诚实呈现，旧结果派生也应保留来源标签。
- **继续遵守薄 Control Plane**：只修改 Harness PG 事实、只读投影和 Inspector；不额外实现调度器/恢复引擎、不将 Agent SDK 业务语义混入 Hatchet History。
- **POC 本地 Prompt 明文保存仅供演示**：显式提醒不得输入密码/敏感内容；生产必须通过受控 Artifact/Ref/脱敏策略接入，不把这份示例 Schema 直接推广生产。

## 4. 遗留限制（继续 OPEN）

真实 LiteLLM/LLM 语义输出、Token SSE、审批、非幂等 Receipt 对账、Cube Session/Worker Fencing、100 并发、旧 PDLC 数据迁移均不在本次范围。用户可见的业务结果展示规范也需要在正式 Portal 的协议设计中进一步深化，本次只验证**固定模型输出的两个 SDK 接力 POC**。

**此复盘承诺：后续每条业务/Agent POC，都把“用户是否能读懂输入、执行与最终结果”作为测试先行的验收条件，而不仅是技术 API/日志正确。**