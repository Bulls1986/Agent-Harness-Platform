# Inspector API · localhost development endpoints

> The local Inspector is an **unauthenticated demonstration UI** published on `127.0.0.1:8765` by the provided Compose profile. **Never attach this API directly to a corporate/Public Gateway** or treat persisted POC evidence as a production security decision.

Base: `http://127.0.0.1:8765`. Source: [inspector.py](../../poc/closed_loop/inspector.py); [OpenAPI](openapi-inspector.json); interactive docs at `/docs`.

| Method | Endpoint | Request | Notes |
|---|---|---|---|
| GET | `/` | — | Inspector HTML (not in OpenAPI schema) |
| GET | `/api/config` | — | non-secret `mode`, `model_id`, token SSE status |
| POST | `/api/runs` | JSON `{"prompt":"Synthetic request"}` | `202` new persisted Run; only with actual submit adapter |
| GET | `/api/runs` | `limit` 1–100, default 20 | recent persisted Run list |
| GET | `/api/runs/{run_id}` | path ID | full persisted domain snapshot; 404 unknown |
| POST | `/api/runs/{run_id}/cancel` | path ID | `202` cancel request; `acknowledged:false` is **not physical cancellation** |
| GET | `/api/runs/{run_id}/events` | `after` event seq, default 0 | persisted event list and cursor |
| GET | `/api/runs/{run_id}/stream` | optional `after` or `Last-Event-ID: {run_id}:{seq}` | `text/event-stream`; bounded lifecycle |
| GET | `/api/verification/scenarios` | — | scenario catalog/explanation |
| GET | `/api/verification/evidence/{run_id}` | path ID | **PERSISTED_FACTS_ONLY** evidence; not live Guest/OS proof |

### Try locally

```sh
curl http://127.0.0.1:8765/api/config
curl http://127.0.0.1:8765/api/verification/scenarios
curl -sS -H 'Content-Type: application/json' \
  -d '{"prompt":"Synthetic requirements for addition"}' \
  http://127.0.0.1:8765/api/runs
# Use the returned run_id:
curl "http://127.0.0.1:8765/api/runs/<run_id>/events?after=0"
```

A `503` with a persisted Run ID may mean Hatchet submission was uncertain. Do not treat it as proof that no work started. Approval/Receipt/Cube real injection commands are **not** exposed as unauthenticated actions in this API.

### Optional M7 synthetic mount

When `HARNESS_INSPECTOR_M7_DEMO_ENABLED=1` (the provided local Inspector profile), `/m7-demo/api/v1/...` maps to the separately documented [Public API v1 facade](PUBLIC_API.md) using a **fixed, server-owned synthetic principal**. It does not grant a public authentication flow and is not suitable for production or internet binding.

[API hub](README.md) · [User guide](../guides/USER_GUIDE.md)