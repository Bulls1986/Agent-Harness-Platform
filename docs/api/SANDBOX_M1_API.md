# DEV-SBX M1 路 Cube-native Sandbox and Template APIs

**Status: SBX-M1 IN PROGRESS (limited development API; Production NO-GO).**
These are optional, separate FastAPI factory routes. They are **not mounted**
by default in Inspector and do not provide enterprise Gateway/IdP. The
factory requires trusted `resolve_context`, `SandboxCreateService`,
and optionally `CubeTemplateGateway` with explicit administrator Policy.

This is **native Cube**, not a Harness SandboxDefinition/Registry/DSL. Cube's
Dockerfile/OCI image and SDK `Template.build()` are the environment source.
Existing, pre-built native Template IDs are used for new Cube MicroVMs.

## Endpoint inventory

| Method | Path | Privilege |
|---|---|---|
| POST | `/api/v1/sandboxes` | Authorized Sandbox Create |
| GET | `/api/v1/sandbox-operations/{operation_id}` | Original trusted scope/principal |
| POST | `/api/v1/sandbox-operations/{operation_id}/reconcile` | Original trusted scope/principal |
| GET | `/api/v1/cube/templates` | Native Template administrator |
| GET | `/api/v1/cube/templates/{template}` | Native Template administrator |
| POST | `/api/v1/cube/templates/build` | Native Template administrator |
| PUT | `/api/v1/cube/templates/{template}/alias` | Native Template administrator |
| DELETE | `/api/v1/cube/templates/{template}` | Native Template administrator |

The last five routes only exist when the `template_gateway` is supplied.
They directly call SDK `Template.list/get/build/set_alias/delete`; no
second Registry, image builder, apt/pip DSL or implicit privilege elevation.
Provider metadata responses exclude stored native `create_request` fields
that may contain credentials. Build fields use native SDK snake_case
(`image`, `name`, `exposed_ports`, `probe_port`, `probe_path`,
`writable_layer_size`, etc.); unsupported `dockerfile` and unknown
properties return 422. The native SDK requires an OCI image for Build.

**Important:** Mutating Template build/alias/delete methods are currently
admin-policy guarded but **not yet production-grade idempotent admin
operations**. If the native ACK is lost, the operator must inspect Cube
directly before any new request. Actual native Build/alias/delete and
their failed-ACK behavior are not yet live-tested; do not mark SBX-M1
CLOSED on the strength of injected SDK tests alone.

## Create and onCreate

```json
{
  "cube": {"template": "tpl-actual-id-or-native-alias", "timeout": 180},
  "onCreate": {"commands": [
    {"command": "git --version", "cwd": "/workspace", "timeoutSeconds": 30}
  ]}
}
```

Required header: `Idempotency-Key`. Trusted scope/principal must be
supplied by server-side authenticated Gateway and checked by Policy.
`cube` accepts Cube-native SDK kwargs admitted by the pinned adapter
(`template`, `timeout`, `lifecycle`, `env_vars`, `volume_mounts`);
authorization is required separately. Native IDs `tpl-...` and aliases
are resolved through Cube `Template.get` before allocation; only READY
templates and their resolved immutable Template ID are used. A retry
reuses the original PG Operation and frozen native Template ID even if
the Cube alias has since moved or disappeared.

Example success:

```json
{
  "operationId": "sbx-op-...",
  "sandboxRef": "native-cube-sandbox-id",
  "nativeTemplateId": "tpl-...",
  "state": "READY",
  "exitCode": 0
}
```

The create flow persists `PENDING`/`CREATING` before calling native
Cube and performs guest `commands.run` only after an ACK. Nonzero exit
returns `FAILED`; lost Cube/Guest ACK returns `UNKNOWN`. Repeating
the same Idempotency-Key cannot create a second VM or rerun the script.
`reconcile` looks up original native correlation via Cube
`Sandbox.list/connect/get_info`, requires a unique metadata and Template
match, and can record a previously unknown Sandbox ID. **It deliberately
does not change UNKNOWN to READY or replay onCreate**, as the command
may already have produced side effects.

HTTP errors: 400 missing Idempotency-Key, 403 denied, 404 cross-scope,
409 conflicting Idempotency-Key or unverifiable reconciliation,
422 invalid/native-unsupported request, 503 provider outcome unknown.
A 503 is never proof the provider did not create the VM.

No Shell executes on the Host. Test-only identity injection must never
be deployed as the production Gateway.

## Verification

Offline contracts:

```sh
python -B -m unittest poc.sandbox.test_sbx_m1 poc.sandbox.test_sbx_api_m1 poc.sandbox.test_sbx_template_m1 poc.sandbox.test_sbx_template_api_m1 -v
```

PG contract needs real `HARNESS_POC_DATABASE_URL`:

```sh
python -B -m unittest poc.sandbox.test_sbx_pg_m1 -v
```

For a **real Cube + PostgreSQL** HTTP鈫扵emplate鈫扖reate鈫抩nCreate鈫扜uest smoke,
explicitly configure `CUBE_API_URL`, `CUBE_PROXY_NODE_IP`,
`HARNESS_POC_DATABASE_URL`, `SBX_M1_CUBE_TEST_TEMPLATE_ID` and run:

```sh
python -B -m poc.sandbox.verify_sbx_m1_cube_live
```

The smoke uses a deliberately local synthetic identity injected into
FastAPI TestClient, validates native onCreate and same-key replay,
then destroys only its own test sandbox. Do not confuse it with
production authentication. Lack of Cube, SDK or PG must be a hard
test failure, never a SKIPPED/PASS.

[OpenAPI M1](openapi-sbx-m1.json) 路
[Frozen contract](../references/CUBE_SANDBOX_MANAGEMENT_V1_20261014.md) 路
[Milestones](../DEVELOPMENT_MILESTONES.md).