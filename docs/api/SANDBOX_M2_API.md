# DEV-SBX M2 路 Session Attach / onAttach (bounded V1)

**Status: bounded SBX-M2 acceptance CLOSED; production NO-GO.** This is an opt-in
FastAPI factory extension of M1; not mounted in Inspector or backed by
production IdP/Gateway. No general Run-time Execute endpoint (SBX-M3).

## Contract

| Method | Route | Scope |
|---|---|---|
| POST | `/api/v1/sandbox-bindings` | Initial Session Attach, optional ordered onAttach.commands |
| GET | `/api/v1/sandbox-bindings/{bindingId}` | Authorized binding status (never a Shell permit) |
| POST | `/api/v1/sandbox-bindings/{bindingId}/reconnect` | Same Session, no onAttach replay; verify native Cube connection |
| POST | `/api/v1/sandbox-bindings/{bindingId}/reconcile` | Operator-authorized, fail-closed UNKNOWN for interrupted initialization |

Example POST request with `Idempotency-Key: unique-for-session-attach`:

```json
{
  "createOperationId": "sbx-op-...",
  "sessionRef": "trusted-session-id",
  "onAttach": {
    "commands": [
      {"command": "git clone /workspace/remote.git /workspace/app",
       "cwd": "/workspace", "timeoutSeconds": 120},
      {"command": "git -C /workspace/app fetch origin",
       "cwd": "/workspace", "timeoutSeconds": 120}
    ]
  }
}
```

Example 202 response:

```json
{
  "bindingId": "sbx-bind-...",
  "sessionRef": "trusted-session-id",
  "sandboxRef": "cube-native-sandbox-id",
  "state": "ACTIVE",
  "exitCode": 0
}
```

All commands run only inside the original Cube Guest, using the native
SDK. No host fallback. `onAttach` is ordered; a nonzero exit marks
`FAILED`; command or connect result ambiguity marks `UNKNOWN`.
Neither status permits redispatch through the same Binding.

## Mandatory authorization and persistence

- The server-side authenticated Gateway supplies trusted scope/principal;
  an upper-layer **trusted Session resolver** authorizes `sessionRef`.
  The caller cannot authorize an arbitrary Session by putting its ID
  in JSON. Recheck Session authority on binding get and reconnect.
- M1 authoritative PostgreSQL Create Operation MUST be `READY` and
  owned by that same scope/principal. No fabricated Run.
- A server-side Policy must authorize the Attach action, **and** issue
  an `InitializationPermit` for nonempty onAttach.commands. Permit
  binds scope, principal, Session, **native Sandbox ID**, the hash of
  the exact command list, and an expiration not more than one hour
  away. Verify before each Guest command. Permits are not supplied
  through the HTTP API or embedded in Cube metadata.
- PostgreSQL enforces one writable Sandbox -> one Session Binding,
  one Session -> one current Binding, and one
  (scope, principal, Idempotency-Key) -> one request fingerprint.
  Same-key retries return the original fact without running commands.
  Different Session, Scope or commands are rejected.
- On a stale `INITIALIZING` record, an **operator-only** reconcile
  changes the association to `UNKNOWN` without executing Git or
  claiming Guest side-effect correctness. UNKNOWN has no automatic
  recovery or replay; a human may need Cube-native evidence. A
  successful reconnect checks native Cube connectivity, not just PG.
- A Binding is **not an Execution Permit**. Official Agent Run
  commands still require original M5 ExecutionContext, Lease/Fencing.
  Volume Mount is Cube Create-time infrastructure, *not* Session Attach.
  A Session/Workspace reference is distinct from the Sandbox ID.
- Upper layer chooses Git command/revision/workspace overwrite policy.
  Harness does not autonomously `git pull` or reset dirty work trees.
  Successful repeated reconnect does not re-run `git clone`.
- Until M3, this factory does not expose Session detach/release,
  pause/resume, generic Shell Execute, File Execute or Workspace
  recovery. The API has no production IAM.

## Tests and evidence

- Red: `ModuleNotFoundError` for absent Session Attach module.
- Real PostgreSQL contract and FastAPI negative tests:
  `python -B -m unittest poc.sandbox.test_sbx_m2 poc.sandbox.test_sbx_m2_api -v`
  (with actual `HARNESS_POC_DATABASE_URL`).
- Opt-in REAL Cube MicroVM + PostgreSQL + HTTP smoke:
  `python -B -m poc.sandbox.verify_sbx_m2_cube_live` with the same
  `CUBE_API_URL`, `CUBE_PROXY_NODE_IP`,
  `HARNESS_POC_DATABASE_URL`, `SBX_M1_CUBE_TEST_TEMPLATE_ID`
  used for M1's real smoke.
- That real smoke creates a temporary Git origin with a genuine commit
  **inside Cube Guest**, attaches via HTTP and executes clone/fetch/
  rev-parse, checks same-Binding reconnect does not replay, verifies
  a previously written file remains, denies other Sessions, and
  destroys only its newly created test VM.
- Native lost ACK/HTTP disconnect negative cases use fake SDK/real PG
  to verify fail-closed/idempotency, not real external network packet
  loss; no false exactly-once assertion.

[OpenAPI M2](openapi-sbx-m2.json) 路
[DEV-SBX frozen scope](../references/CUBE_SANDBOX_MANAGEMENT_V1_20261014.md) 路
[OpenSpec M2](../../openspec/changes/dev-sbx-cube-sandbox-management-v1/tasks.md).