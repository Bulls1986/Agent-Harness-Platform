# API reference · HTTP / SSE / OpenAPI

Agent Harness has two established FastAPI surfaces and an optional **DEV-SBX M1 pilot factory** (not mounted in Inspector by default). Do not confuse the unprotected localhost Inspector with the injected-authentication Public API facade.

| Interface | Source | Documentation | Machine-readable contract |
|---|---|---|---|
| **Versioned Public API** | [platform_api.py](../../poc/platform_access/platform_api.py) | [Public API v1](PUBLIC_API.md) | [OpenAPI v1](openapi-v1.json) |
| **DEV-SBX M1 pilot Create/Operation** | [sbx_api.py](../../poc/sandbox/sbx_api.py) | [SBX-M1 API](SANDBOX_M1_API.md) | [SBX-M1 OpenAPI](openapi-sbx-m1.json) |
| **Local Inspector / debugging** | [inspector.py](../../poc/closed_loop/inspector.py) | [Inspector API](INSPECTOR_API.md) | [Inspector OpenAPI](openapi-inspector.json) |

## Live Swagger / OpenAPI in development

After starting the [local deployment](../deployment/README.md):

- Inspector Swagger UI: [http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs)
- Inspector raw OpenAPI: [http://127.0.0.1:8765/openapi.json](http://127.0.0.1:8765/openapi.json)
- **Synthetic M7** mounted Swagger UI: [http://127.0.0.1:8765/m7-demo/docs](http://127.0.0.1:8765/m7-demo/docs)
- Synthetic M7 raw OpenAPI: [http://127.0.0.1:8765/m7-demo/openapi.json](http://127.0.0.1:8765/m7-demo/openapi.json)

The Public API is a **Python application factory** requiring server-side authenticated identity, Policy and actual PostgreSQL adapters. It has no independently published production Gateway. Mounting it beneath `/m7-demo` provides a **hard-coded synthetic test identity only**. The portable checked-in OpenAPI schema documents the factory's versioned routes, not a deployed public endpoint.

## Maintaining the API specifications

```sh
python -B scripts/export_openapi.py
python -B scripts/export_openapi.py --check
python -B -m unittest tests.test_repository_docs -v
```

The exporter instantiates the real FastAPI route factories with **non-executable schema-only adapters**: it does not connect to a database, authenticate users or invoke Agents. It strips unversioned internal read aliases from the public snapshot. The `--check` guard compares method/path, request parameters, body fields and response codes rather than framework-generated metadata: supported FastAPI/Pydantic versions may emit different examples, internal validation error schemas or titles. The checked-in JSON is a representative export; use `python -B scripts/export_openapi.py` to regenerate after an intentional contract change. Run with the project's installed FastAPI/Pydantic dependencies. API Markdown covers access/security boundaries and event semantics that OpenAPI cannot infer from injected authorization callbacks.

**Versioning:** `/api/v1` is the public contract. Legacy `/api/runs` belongs to local Inspector/debug access, not the v1 consumer contract. Any compatible change requires corresponding OpenSpec/tests and regenerated OpenAPI; no claim of semantic stability beyond currently implemented routes.