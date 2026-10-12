# Minimal runnable Harness closed-loop POC

**Architecture:** [HC-01](../../docs/references/HATCHET_WORKFLOW_MAPPING_CONTRACT_20261010.md) · [HC-02](../../docs/references/HARNESS_HATCHET_CONSISTENCY_CONTRACT_20261010.md) · [HC-03](../../docs/references/HATCHET_WORKER_SANDBOX_BINDING_CONTRACT_20261010.md) · [OpenSpec](../../openspec/changes/minimal-run-closed-loop/proposal.md).

This is a **LIMITED model-only POC, NOT production Accepted**. Real Hatchet SDK + Engine → real Pydantic AI and OpenAI Agents SDK → PostgreSQL persistent domain facts → localhost-only Run Inspector.

## Launch (Docker)

```sh
docker compose up -d postgres
docker compose --profile inspector up -d --build inspector
# Browser:
# http://127.0.0.1:8765
# Or black-box E2E:
python -B -m poc.closed_loop.verify_inspector_live
```

Docker Hub may reject OAuth/token pulls on restricted networks. You can override the base Python image and wheel mirror when rebuilding (for a base image **you have separately verified and trust**):

```powershell
$env:HARNESS_POC_PYTHON_BASE = "mcr.azure.cn/azure-functions/python:4-python3.11"
$env:HARNESS_POC_PIP_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
docker compose build loop inspector
docker compose --profile inspector up -d inspector
```

The Compose PG **container is mandatory**. The Docker PG instance contains **two separate databases**: `hatchet_poc` (Engine-owned) and `harness_poc` (Harness-owned). Database port (host) defaults to `127.0.0.1:55447`, Inspector to `127.0.0.1:8765`.

Alternatively, run the Python POC from a trusted Linux environment using exact pinned packages and Host-reachable Docker PG URLs:

```sh
python -m pip install 'hatchet-sdk==1.42.1' 'pydantic-ai-slim==2.54.0' 'openai-agents==0.23.1' 'psycopg[binary]>=3.2,<4' 'fastapi>=0.115,<1' 'uvicorn>=0.30,<1' 'httpx>=0.27,<1'
export HATCHET_CLIENT_EMBEDDED_VERSION=v0.110.5
export HATCHET_CLIENT_EMBEDDED_CHECKSUM=18ddacae0005042bd982328bcb8d370cca6907352a1ab2a3c8406001d31e7dee
export HATCHET_POC_DATABASE_URL=postgres://harness_poc:local_poc_only@127.0.0.1:55447/hatchet_poc
export HARNESS_POC_DATABASE_URL=postgresql://harness_poc:local_poc_only@127.0.0.1:55447/harness_poc
python -B -m poc.closed_loop.serve
```

## Read the demo like a product reviewer

The first screen explains **what is being verified**, its scope and the exact two-node chain. The right pane starts with a **final Run result**, followed by explicit Step A/Step B purpose, real persisted input and actual output. Step B's input must equal the persisted output of Step A. Below that, a human-readable event timeline tells what happened; raw JSON and Provider IDs are in a collapsed technical-details panel.

**This is a deterministic-model orchestration demo.** It uses real Pydantic AI/OpenAI Agents SDKs but each SDK receives a local model with a fixed test answer. The system is **not** interpreting the submitted business text and must never pretend to generate an actual product report. The completed Run's final result is the confirmed output of Step B, persisted atomically as a dedicated business result. A previously completed Run with no persisted original prompt shows “not recorded” instead of inventing its input; its older final result can be read from Step B's committed output and marked as derived.

## 两个 Tab：双 Agent 演示 + 能力验证

原来的 Inspector 页面保持在 `http://127.0.0.1:8765`，**只新增一个「能力验证」Tab**，不创建另一套页面/演示服务。第一个 Tab「双 Agent 演示」保留原 Run 提交、两 SDK 节点输入输出、最终 Run 结果、PG 历史和 SSE。

新增的「能力验证」Tab 用场景而不是 JSON 为主线，针对四项能力逐一展示：

- **双 Agent 跨 SDK 接力**：业务场景是产品分析与独立审核；证明跨 Agent SDK 调度、持久化节点数据和最终结果。这一项可以从原 Tab 直接执行。
- **Cube Workspace 恢复**：业务场景是研发/测试 Agent 中断后续跑，证明同一 Sandbox ID / WorkspaceRef、旧 Owner 失效、新 Owner Guest 文件内容保持；实际 Cube Guest 和释放必须由真实运行器证明。
- **Hatchet Worker A→B 故障接管**：业务场景是 Worker 异常退出后任务恢复；必须有真实 PID、A SIGKILL 退出码 -9、B 不同 PID、同 Workflow Native Retry、原 Cube 数据与 Epoch 才能算 PASS。该联合实机 Gate 尚未通过。
- **非幂等 Tool Receipt**：业务场景是外部副作用落盘但 ACK 丢失；必须验证外部真实效果仅一次、UNKNOWN 保持/对账、过期 Owner 拒绝；不能只凭 PostgreSQL Receipt 事件断言外部事实。

下方提供**只读 Run ID 证据查询**，通过 `GET /api/verification/evidence/{run_id}` 展示 PG Workflow ID、白名单事件、Cube Binding/Owner/Fencing、Tool Receipt 状态，始终标注 `PERSISTED_FACTS_ONLY` 与 `verified=false`。这意味着它只证明“数据库中观察到什么”，**不等于**真实 Guest 字节、OS SIGKILL 或外部付款等效果已经被独立验收。场景目录 API 为 `GET /api/verification/scenarios`。

Cube/故障注入/外部 Tool 尚**未**在这个无生产认证的 Inspector 中开放“一键执行”；当前只能查看运行结果，或通过各自有权限的开发/CI 实机 Gate 执行。后续若要从 Tab 启动这些演示，必须先集成受信任的服务端执行器、回传证据和适当的访问控制，不能直接从浏览器触发宿主机 Shell 或 SIGKILL。

## What the browser shows

- Submit prompt to **create a real** Platform Run and PG Outbox, dispatch on **one shared Hatchet Engine/Worker**.
- Inspect **final Run output and status** first, **what Step A/B did**, original Step A prompt, Step B handoff input, their exact outputs and Attempt count. Provider IDs remain available in the collapsed raw diagnostics.
- Refresh and reload persisted results and ordered Domain Event history from PostgreSQL.
- Distinguish `runtime.run.completed` (SDK-level) from the **sole** `run.completed` business terminal event.
- No fake success if engine is unavailable. An unresolved workflow submission ACK becomes `BLOCKED_UNKNOWN` rather than replaying an unknown duplicate.

## M1: Real LiteLLM Responses model (explicit opt-in)

[OpenSpec M1](../../openspec/changes/archive/2026-10-11-real-model-agent-closed-loop/) introduces an **actual LLM requirement-analysis → independent review** chain. This is a limited POC, **not** a production-ready business agent. The default remains `local` for deterministic clean CI.

When a trusted LiteLLM-compatible **Responses API** and key are available in the operator's environment, select mode `live`. Never commit the key, endpoint credentials or real sensitive input to source/CI:

```powershell
$env:HARNESS_MODEL_MODE = "live"
$env:HARNESS_MODEL_BASE_URL = "<your-Responses-compatible-base-url-ending-in-/v1>"
$env:HARNESS_MODEL_NAME = "<your-approved-model-id>"
# Inject JUSDA_LITELLM_API_KEY (or HARNESS_MODEL_API_KEY) from an approved local secret source.
docker compose --profile demo run --rm --no-deps -e HARNESS_MODEL_MODE -e HARNESS_MODEL_BASE_URL -e HARNESS_MODEL_NAME -e JUSDA_LITELLM_API_KEY loop
```

To run a separate localhost-only **Live Inspector** while the deterministic Inspector remains at port 8765:

```powershell
docker compose --profile inspector run -d --rm --no-deps --name harness-real-inspector-m1 -p 127.0.0.1:8766:8765 -e HARNESS_MODEL_MODE -e HARNESS_MODEL_BASE_URL -e HARNESS_MODEL_NAME -e JUSDA_LITELLM_API_KEY inspector
python -B -m poc.closed_loop.verify_inspector_live --url http://127.0.0.1:8766 --expect-live
```

On an existing Docker image install/rebuild with current source before running, or for local development bind-mount your current checkout to `/app`. Do **not** combine Live and Local workers on the same unversioned Hatchet Workflow name. The current POC uses distinct workflow definitions `harness-pg-real-responses-v1` / `harness-pg-minimal-run-v1`, and validates model-mode/ID bindings and business evidence before marking a Run COMPLETED.

A returns validated JSON with feature, summary, capabilities, rules and acceptance criteria; B reviews the **persisted A JSON**, then produces a readable business report containing acceptance criteria and audit issues. Both run real SDKs through the existing AgentRuntime SPI, with **zero Sandbox**. Native model **text** Token SSE from both public SDKs → PostgreSQL Event → Last-Event-ID cursor replay and Worker-acknowledged model-only cancel now have **M1 LIMITED LIVE PASS** (see [M1 SSE retrospective](../../docs/retrospectives/M1_TOKEN_SSE_CLOSEOUT_20261011.md)); Cube, Approval, external Tool Receipts and production IAM/PII/OSS/backpressure still require their own gates. The Inspector UI loads `GET /api/config` with nonsecret model metadata and never shows the API key.

## Tests and limitations

```sh
openspec validate --specs --strict
python -B -m unittest poc.closed_loop.test_facts_pg poc.closed_loop.test_inspector_pg poc.closed_loop.test_real_model -v
python -B -m poc.closed_loop.verify_inspector_live
```

Note: PG contract tests require `HARNESS_POC_DATABASE_URL`; otherwise they skip and **must not be counted PASS**. End-to-end test requires the real application dependencies and actual Engine. Independent legacy Hatchet SDK POCs are insufficient proof for this combined path.

**Not yet tested here:** CubeSandbox authorization/lease/fencing and cross-Worker recovery, non-idempotent Tool Receipts/UNKNOWN reconciliation, durable Approval/Wait, production-grade token/Tool/Artifact multi-part SSE, 100 concurrent Runs, production authentication or PDLC migration.

**Safety:** localhost-only published ports, local disposable passwords (never use in production). No input is executed as Host Shell, and browser rendering uses `textContent`, never `innerHTML`.