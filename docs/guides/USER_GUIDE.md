# User guide · Run Inspector

> **Inspector 是开发用可视化验证工具，不是生产管理控制台。** 默认没有企业 IAM；仅可经 localhost 访问。

## 首页与双 Agent 演示

浏览器访问 `http://127.0.0.1:8765/`。在「双 Agent 演示」Tab 提交任意**合成测试需求**，服务创建 Harness Run、持久化 Outbox 后启动真实 Hatchet/Agent SDK 流程。界面应显示：

1. Run ID 和最终领域状态（先看是否 `COMPLETED`，不能只看 SDK 调用状态）。
2. Step A（需求分析）与 Step B（独立审核）的输入和输出；B 的输入来自 A 已落盘的结果。
3. 事件时间线和重试/Attempt、模型模式等审计信息。刷新页面仍应能按 Run ID 查询持久事实。

默认 `HARNESS_MODEL_MODE=local` 是**确定性 SDK 演示**。它调用了实际 Agent SDK 与 Hatchet，但输出来自固定本地模型。不能将其当成真实业务设计结果。启用真实 LiteLLM/Responses API 属明确 opt-in 的开发集成，见 [部署手册](../deployment/README.md)。

## 能力验证 Tab

此 Tab 展示已保存的能力证据与对应业务场景，包含跨 SDK 接力、Cube Workspace、Worker 恢复和非幂等 Receipt。列表中的静态能力解释或 `PERSISTED_FACTS_ONLY` **不表示在本次页面会话重新执行了真实环境测试**。目前不是四项能力都能从浏览器一键启动；原生 Cube/SIGKILL/Receipt 故障测试需从独立验证程序或 CI 中执行。

M6 已验证的三 Agent Recipe 与 Inspector 默认双 Agent 页面是**两条不同的验收入口**，不要把一个演示误标为另一个。

## Run / 事件读取

使用 `GET /api/runs/{run_id}` 获取状态，`GET /api/runs/{run_id}/events?after=0` 分页查看持久事件；`GET /api/runs/{run_id}/stream` 为 `text/event-stream`，通过形如 `{run_id}:{seq}` 的 `Last-Event-ID` 继续读取。UI 内取消操作返回的是**取消请求**，不等于 Worker 或 Cube 已物理终止。

若提交得到 `503` 且提供已持久化 Run ID，请查询现有 Run 进行对账，**不要盲目重复创建**，避免未知 ACK 窗口的副作用。

## 合成 M7 公共 API 演示

Compose Inspector 设 `HARNESS_INSPECTOR_M7_DEMO_ENABLED=1` 时可访问 `/m7-demo/api/v1/...`。该服务端注入固定合成 USER 与 Project Scope，适合了解版本化 Conversation → Turn → Run、受控 SSE 和 ArtifactRef **元数据**。它不验证真实企业 Gateway、IdP 或签名 OSS 下载。请参阅 [API 合同](../api/PUBLIC_API.md)。

## Troubleshooting

- **网页不能访问：** `docker compose ps`，检查 8765 端口是否被占用；看 `docker compose logs inspector`。
- **503 / Run 未完成：** 检查 PostgreSQL 健康状态和 Hatchet 启动日志，不得伪造 PASS。
- **页面里没有新功能：** Inspector 不是所有阶段的功能演示入口；对照 [M3～M9 状态](../DEVELOPMENT_MILESTONES.md)。
- **模型响应不匹配：** 核查 `/api/config` 的 `mode`，local 固定输出与 live 真实模型不是同一种验收。

[返回 Quickstart](QUICKSTART.md) · [API 参考](../api/README.md)