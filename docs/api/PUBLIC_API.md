# Public API v1 · HTTP contract

> **Status:** M7 bounded development contract, **not an internet-facing service**. All examples assume a trusted Gateway with a server-side resolved identity, Project Scope and current Policy adapter. Directly sending `X-User-Id` or `X-Project` headers does **not** authenticate. The `/m7-demo` mount uses a fixed synthetic identity and is **unsafe for public exposure**.

Base route: `/api/v1`. For local Inspector only: `http://127.0.0.1:8765/m7-demo/api/v1`.

## Resource and identity contract

- `Conversation`: belongs to the authenticated principal and project; title length 1–200.
- `Turn`: belongs to a Conversation; `message` 1–8192, `agent_ref` and `recipe_ref` 1–256; references are labels, **not execution authority**.
- `Run`: an immutable binding to Turn, principal, Project and model; authorization and actual Reader/Policy are injected from the trusted service. A user cannot select raw Provider IDs.
- `Artifact`: metadata-only read. A returned `ArtifactRef` is **not** a signed OSS URL and does not authorize payload download.

## Operations

| Method | Path | Body / parameters | Success |
|---|---|---|---|
| POST | `/api/v1/conversations` | JSON `{"title":"Synthetic test"}` | `201 {"conversation_id":"..."}` |
| GET | `/api/v1/conversations` | current project/principal | `200 {"conversations":[...]}` |
| GET | `/api/v1/conversations/{conversation_id}` | path ID | `200` conversation with turns / Runs |
| POST | `/api/v1/conversations/{conversation_id}/turns` | JSON `{"message":"Add two numbers","agent_ref":"dual-sdk-requirements-review@v1","recipe_ref":"requirements-review@v1"}` | `201 {"turn_id":"...","conversation_id":"..."}` |
| POST | `/api/v1/turns/{turn_id}/runs` | **required** `Idempotency-Key` request header (1–128 characters, alphanumeric first, then `[A-Za-z0-9._:-]`) | `202 {"run_id":"...","turn_id":"...","state":"...","replayed":false,"needs_reconciliation":false}` |
| POST | `/api/v1/turns/{turn_id}/runs/{run_id}` | attach an already owned Run to Turn | `200 {"run_id":"...","turn_id":"..."}` |
| GET | `/api/v1/runs/{run_id}` | path ID | `200` persisted Run snapshot |
| GET | `/api/v1/runs/{run_id}/events` | `after>=0` (default 0), `limit` 1–250 (default 250) | `200 {"run_id":"...","events":[...],"cursor":n}` |
| GET | `/api/v1/runs/{run_id}/stream` | optional `Last-Event-ID: {run_id}:{seq}` | `200 text/event-stream` |
| POST | `/api/v1/runs/{run_id}/cancel` | path ID | `202 {"run_id":"...","state":"CANCEL_REQUESTED","provider_terminated":false}` |
| GET | `/api/v1/runs/{run_id}/artifacts` | path ID | `200 {"run_id":"...","artifacts":[...]}` |
| GET | `/api/v1/artifacts/{artifact_id}` | path ID | `200` metadata with Run linkage |

**Execution admission:** the versioned Run creation route only dispatches if `start_run`, `model_binding` and `admit_recipe` are explicitly injected. A supported Agent/Recipe pair is a server-side authorization decision, not arbitrary user-configurable execution. The Inspector synthetic demo currently admits only `dual-sdk-requirements-review@v1` / `requirements-review@v1`; it does **not** expose all M6 Recipes as a general public service.

## Local example (synthetic identity only)

Start the local Inspector with the [Quickstart](../guides/QUICKSTART.md) first:

```sh
BASE=http://127.0.0.1:8765/m7-demo/api/v1
curl -sS -H 'Content-Type: application/json' -d '{"title":"Synthetic test"}' "$BASE/conversations"
# Use returned conversation_id (replace in path below):
curl -sS -H 'Content-Type: application/json' -d '{"message":"Add two numbers","agent_ref":"dual-sdk-requirements-review@v1","recipe_ref":"requirements-review@v1"}' "$BASE/conversations/<conversation_id>/turns"
# Use returned turn_id; request key is client-generated and stable for retries:
curl -sS -X POST -H 'Idempotency-Key: example-run-001' "$BASE/turns/<turn_id>/runs"
curl -sS "$BASE/runs/<run_id>/events?after=0&limit=100"
```

Placeholders `<conversation_id>`, `<turn_id>` and `<run_id>` are values returned by preceding calls; the example does not invent existing IDs. Never use actual company/personal prompts in this local demo.

## Streaming, replay and cancellation

```text
id: <run_id>:17
event: runtime.run.completed
data: {"seq":17,"type":"runtime.run.completed","data":{...}}

```

Each Server-Sent Event is a persisted, typed domain Event. Resume with `Last-Event-ID: <run_id>:17`; cross-Run IDs or bad cursors return `422` before streaming. The server rechecks Policy across batches; a revoked access ends delivery. A requested cancellation is only a durable **intent**, not verified worker/Provider termination.

## Error semantics

| Status | Meaning |
|---|---|
| `401` | no trusted server-side authenticated SecurityContext |
| `404` | missing resource **or** denied project/principal/Policy (intentionally concealed) |
| `409` | conflicting Run binding / invalid state / already attached |
| `422` | invalid request JSON, Idempotency-Key, query cursor or SSE resume cursor |
| `503` | missing/unavailable identity Policy adapter, database, execution/cancel adapter, or uncertain submission ACK |

On `503` with a persisted `run_id` and `Dispatch outcome uncertain`, **reconcile that Run**, do not blindly submit again. A retry with the same immutable Idempotency-Key must not trigger a second dispatch.

[OpenAPI schema](openapi-v1.json) · [API index](README.md) · [M7 architecture contract](../../poc/platform_access/README.md)