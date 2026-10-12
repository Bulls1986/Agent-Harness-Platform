# Inspector 能力验证 Tab · Design

## UI 结构

现有单页 Inspector 顶部仅有两个 Tab：「双 Agent 演示」「能力验证」。原 Panel、历史 Run、SSE、最终输出及原始 JSON 保留在原视图；新 Tab 的场景卡分别写清楚：使用场景、证明什么能力、执行步骤、实际验收证据、不代表什么、当前是否可直接执行。

能力验证展示四类不同链路：双 Agent 跨 SDK 接力、Cube Workspace 恢复、Hatchet Worker 物理故障接管、非幂等 Tool Receipt 安全恢复。现阶段只有原两 Agent 流程可直接提交；其余三个场景不提供假「开始」按钮，也不新增客户端发起 SIGKILL 的 HTTP 接口。

## API / 数据与可信边界

- `GET /api/verification/scenarios`: 版本内固定、非敏感的四场景说明，不包含真实密钥或业务资料，不伪造当前执行成功状态。
- `GET /api/verification/evidence/{run_id}`: 只读既有 Harness PostgreSQL Run/Provider ID、白名单领域事件、可选 Cube Binding（原 Sandbox ID、WorkspaceRef、Owner/Epoch/State）及可选 Tool Receipt State。不存在的表按无证据处理；不存在的 Run 为 404；非法 ID 为 422；PG 不可用为 503。
- 数据库行/事件属于 `PERSISTED_FACTS_ONLY`，不是可信的外部 Cube Guest 字节校验、Worker OS PID/SIGKILL、Native Retry 或独立非幂等外部账本计数。任何此类读取一律返回 `verified=false`，UI 明确“仅观察 PG，整体验收未判定”。
- 保留原运行端 `submit` 与 Hatchet 技术调度；新模块不写数据库、不实施第二套任务引擎、不执行 Host Shell；浏览器只读 API 和双 Agent 原入口分离。

## Security and UX

事件白名单避免返回原 Prompt、模型 Token、外部任意 Tool 数据；场景输入/证据字段统一通过 DOM `textContent` 写入，不使用 `innerHTML`。Run ID 长度、字符集校验；“能力验证”视图可键盘切换、局部数据出错不会影响已有 Run Inspector 的刷新。Inspector 仍为 localhost-only 开发工具，**没有生产认证**，不可对外暴露。

## Tests

先提交真实 PG 负例：目录完整性、四场景 Availability、不存在 Run、越界 ID、Mock Cube Binding 事件不得冒充实机通过、单独新 Tab 可访问且没有 `innerHTML`。随后实现并在原本的真实 PostgreSQL/Hatchet/Inspector CI 回归及架构检查下验收。

## B.3a 增量：受控物理场景（默认为 OFF）

保持原先一个 Inspector 页面/两个 Tab 与真实 Hatchet 两 Agent 主流程不变。新增独立受控执行层，只有服务端显式启用才在 Worker Takeover 场景展示操作员入口；其他两个场景仍是只读。操作员令牌由可信服务端管理，在客户端一次请求中以专用 Header 传递，绝不写入 URL、本地持久存储或回传 JSON。只有 loopback 受控环境、正确凭证及允许来源可调用。

服务端仅运行固定的真实 Native B03 Verifier，不从浏览器接收命令、参数或文件路径；Run 接口先返回未验证的独立执行 ID。专用 Evidence API 严格校验实际 OS PIDs、Native Hatchet Retry、同 Sandbox、PG Epoch、Guest 校验及销毁回执后才可为新执行置 PASSED。存储采用私有目录、单活锁与原子脱敏证据写入；未确认执行保留 BLOCKED_UNKNOWN 和锁，禁止盲目重发。PG 只读 Evidence API 仍独立且从不将持久事件推断为真实外部证明。

本阶段只覆盖 B03 的代码合同与离线拒绝测试，尚需真实 API → Hatchet → Cube 联合实机及 Head CI，其他场景的可信执行不是 B.3a 范围。
