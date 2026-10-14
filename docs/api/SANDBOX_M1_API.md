# DEV-SBX M1 路 Cube Native Create/onCreate API (pilot)

**Status: development slice only / NOT SBX-M1 CLOSED / Production NO-GO.**
This API is an **optional separate FastAPI factory**, not automatically mounted in
the local Inspector or exposed as a production endpoint. Complete M1 needs a real
Cube MicroVM + Template Manager integration, exact native SDK conformance, and
current-head CI. M2 Attach and M3 Execute do not exist here.

## Entry points

| Method | Route | Current behavior |
|---|---|---|
| POST | `/api/v1/sandboxes` | Authorized Cube native Create, optional ordered `onCreate.commands`, 202 |
| GET | `/api/v1/sandbox-operations/{operation_id}` | Scoped idempotent operation status |

```json
{
  "cube": {"template": "tpl-native-id", "timeout": 3600},
  "onCreate": {"commands": [
    {"command": "git --version", "cwd": "/workspace", "timeoutSeconds": 30}
  ]}
}
```

Required request header: `Idempotency-Key`; the trusted Gateway context
must supply `principal_id` and `project_scope` on the **server**.
`create_sbx_m1_app(resolve_context=..., service=...)` requires explicit
authentication/Policy adapters and `PgSandboxCreateStore(PgFacts())`.
Never publish test identity adapters or the localhost Inspector to the internet.

The `cube` object uses Cube **native** field names, not a Harness template
DSL. This pilot admits only `template`, `timeout`, `lifecycle`,
`env_vars`, `volume_mounts` pending installed-SDK and security conformance.
An immutable `tpl-...` native Template ID is required: alias resolution and
Template build/list/delete administration are **not yet implemented**.
Privileged Volume/Network/Secret choices require the injected Policy check;
they are not implicitly allowed by admission. Calls into native Cube
`Sandbox.create(...)` and Guest `commands.run(...)` have no Host fallback.
Template ID is not authorization.

Successful response (including already-completed synchronous pilot operation):

```json
{
  "operationId": "sbx-op-...",
  "sandboxRef": "native-cube-id",
  "nativeTemplateId": "tpl-native-id",
  "state": "READY",
  "exitCode": 0
}
```

States: `PENDING`, `CREATING`, `INITIALIZING`, `READY`, `FAILED`,
`UNKNOWN`. Nonzero Guest exit gives `FAILED`; a lost native ACK or
ambiguous Guest command becomes `UNKNOWN`. Retry with the **same**
Idempotency-Key can read the original Operation but **never** blindly
creates a second VM or replays a side-effecting command. There is no
automatic UNKNOWN reconciler or cancellation in this M1 slice.

HTTP errors: 400 missing key, 403 denied, 404 cross-scope operation,
409 repeated key with changed payload, 422 unsupported/invalid native
parameter or Guest command, 503 unknown native outcome. Never assume an
HTTP timeout means Cube did not create a sandbox.

The operation database stores request fingerprint, immutable template ID,
scope, trusted caller, provider Sandbox ID and exit code, not the full
Shell command/Secret/Guest stdout. Original Workspace recovery, release,
Session Attach and run-time Fencing remain existing HC-03/future SBX-M2/M3.

## Validation

```sh
python -B -m unittest poc.sandbox.test_sbx_m1 poc.sandbox.test_sbx_api_m1
# Requires real disposable PostgreSQL configured in HARNESS_POC_DATABASE_URL:
python -B -m unittest poc.sandbox.test_sbx_pg_m1
python -B scripts/export_openapi.py --check
```

A fake Cube transport verifies API/PG idempotency behavior **only**.
These tests are **not evidence of a real Cube Template or MicroVM**.
Schema: [OpenAPI M1](openapi-sbx-m1.json); master frozen scope:
[Sandbox V1](../references/CUBE_SANDBOX_MANAGEMENT_V1_20261014.md).