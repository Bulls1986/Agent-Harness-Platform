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

## What the browser shows

- Submit prompt to **create a real** Platform Run and PG Outbox, dispatch on **one shared Hatchet Engine/Worker**.
- Inspect **final Run output and status** first, **what Step A/B did**, original Step A prompt, Step B handoff input, their exact outputs and Attempt count. Provider IDs remain available in the collapsed raw diagnostics.
- Refresh and reload persisted results and ordered Domain Event history from PostgreSQL.
- Distinguish `runtime.run.completed` (SDK-level) from the **sole** `run.completed` business terminal event.
- No fake success if engine is unavailable. An unresolved workflow submission ACK becomes `BLOCKED_UNKNOWN` rather than replaying an unknown duplicate.

## M1: Real LiteLLM Responses model (explicit opt-in)

[OpenSpec M1](../../openspec/changes/real-model-agent-closed-loop/) introduces an **actual LLM requirement-analysis → independent review** chain. This is a limited POC, **not** a production-ready business agent. The default remains `local` for deterministic clean CI.

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

A returns validated JSON with feature, summary, capabilities, rules and acceptance criteria; B reviews the **persisted A JSON**, then produces a readable business report containing acceptance criteria and audit issues. Both run real SDKs through the existing AgentRuntime SPI, with **zero Sandbox**. Native Token SSE/replay/cancel, Cube, Approval, external Tool Receipts and production IAM/OSS large-artifact retention still require their own gates. The Inspector UI loads `GET /api/config` with nonsecret model metadata and never shows the API key.

## Tests and limitations

```sh
openspec validate minimal-run-closed-loop --strict
python -B -m unittest poc.closed_loop.test_facts_pg poc.closed_loop.test_inspector_pg poc.closed_loop.test_real_model -v
python -B -m poc.closed_loop.verify_inspector_live
```

Note: PG contract tests require `HARNESS_POC_DATABASE_URL`; otherwise they skip and **must not be counted PASS**. End-to-end test requires the real application dependencies and actual Engine. Independent legacy Hatchet SDK POCs are insufficient proof for this combined path.

**Not yet tested here:** CubeSandbox authorization/lease/fencing and cross-Worker recovery, non-idempotent Tool Receipts/UNKNOWN reconciliation, durable Approval/Wait, true model Token SSE and cursor/cancellation (independent gate), 100 concurrent Runs, production authentication or PDLC migration.

**Safety:** localhost-only published ports, local disposable passwords (never use in production). No input is executed as Host Shell, and browser rendering uses `textContent`, never `innerHTML`.