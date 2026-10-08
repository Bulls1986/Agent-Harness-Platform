# POC-A: Microsoft Agent Framework implementation

> Status: **A00 offline baseline passed; A01–A04 in verification; A05 and A31 production execution not demonstrated.**  
> This is a framework evaluation harness, **not** a production Harness Control Plane.

## Current slices

| ID | Implemented | Evidence needed before PASS |
|---|---|---|
| A00 | Original MAF streaming smoke + offline CI | Offline public imports and unit tests already passed |
| A01 | Pinned direct packages + public API/optional capability probe | CI must install exact versions and run `api_probe.py`; transitive `pip freeze` captured per run |
| A02 | Versioned Coding/Document broken/reference fixtures + independent verifier | CI must prove known-good passes and broken cases fail |
| A03 | PostgreSQL/OTLP Compose + optional external S3-compatible store + isolated model runtime image | Compose validation/build **plus Postgres/OTLP runtime startup/health** (not yet done) |
| A04 | Evidence template with Gate and scenario IDs | Every later case must record real exit status, version, and evidence refs |
| A05 | Live two-turn memory/streaming probe | Requires real provider credential and successful model response; no CI secrets assumed |
| A31 | Durable feasibility memo | Python MAF + Functions/MSSQL in private cluster and cross-worker recovery NOT tested |

## 1. Install and inspect (A01)

Use Python 3.11+ in a clean venv:

```bash
python -m pip install -r poc/maf/requirements.txt
python poc/maf/api_probe.py
python -m unittest discover -s poc/maf/tests -p "test_*.py" -v
```

Direct MAF dependencies are fixed at `agent-framework-core==1.20.0`
and `agent-framework-openai==1.15.0`. This is **not a transitive lockfile**:
record the exact resolved dependencies with `python -m pip freeze`.
Optional symbol presence is introspection, **not proof** that a capability
works or that a Durable backend is available.

## 2. Reproducible acceptance fixtures (A02)

Both cases are deliberately defined **outside the agent prompt** and will be
reused by MAF, Temporal and ADK so evaluation difficulty is identical.

```bash
# Expected PASS (exit 0):
python poc/maf/verify_fixture.py --case coding --candidate poc/maf/fixtures/coding/solution
python poc/maf/verify_fixture.py --case document --candidate poc/maf/fixtures/document/expected

# Expected FAIL (exit 1, VERIFICATION_FAILURE):
python poc/maf/verify_fixture.py --case coding --candidate poc/maf/fixtures/coding/buggy
python poc/maf/verify_fixture.py --case document --candidate poc/maf/fixtures/document/buggy
```

`fixtures/scenarios.json` declares IDs, tasks, accepted outputs and future
failure-injection plans. The UNKNOWN external-write scenario is **declared
but not implemented**; it belongs to A28, not A02.

**Security:** The coding verifier executes candidate Python. Never execute
model-modified/untrusted candidate code on the Harness Control Plane host.
For POC-A2 and beyond, run it only inside CubeSandbox (Docker fallback smoke);
the offline unit tests use only committed trusted fixture code.

## 3. Local infrastructure and container smoke (A03/A05)

Copy the example config, replace local-only credentials (do not commit `.env`):

```bash
cp poc/maf/.env.example poc/maf/.env
docker compose --env-file poc/maf/.env -f poc/maf/compose.yml config -q
docker compose --env-file poc/maf/.env -f poc/maf/compose.yml up -d postgres otel-collector
docker compose --env-file poc/maf/.env -f poc/maf/compose.yml ps
```

Ports bind to **127.0.0.1 only**:
Postgres `54329`, S3-compatible MinIO `9002`, MinIO Console `9003`,
OTLP gRPC `14317`, OTLP HTTP `14318`. This is only an *infrastructure
harness*, not a hosted HTTP Agent API (A18). Current Compose configuration
does not claim Postgres SessionStore, durable MAF history or ArtifactStore
are integrated — those are A15/A23/A24. OTLP receiver is not a production APM
backend; do not turn on prompt/response telemetry by default.

Set the following **only for an explicit real-provider probe**, not in
committed files or logs. Provider is OpenAI-compatible with a Responses API:

```bash
export OPENAI_API_KEY="<local-secret>"
export MAF_POC_MODEL="<model-or-deployment>"
# Optional supported gateway only:
# export OPENAI_BASE_URL="https://<enterprise-model-gateway>/v1"
python poc/maf/session_probe.py
# OR containerized, without relying on Foundry Hosted Agents:
docker compose --env-file poc/maf/.env -f poc/maf/compose.yml --profile live-model run --build --rm maf-runtime-smoke
```

PowerShell uses `$env:OPENAI_API_KEY` and `$env:MAF_POC_MODEL`; environment
variables are inherited by Docker Compose when launching from the same shell.
Be aware `docker compose config` can print resolved environment variables,
including secrets: use `config -q` rather than copying full output.
Use a temporary provider-scoped credential, and never upload raw responses.

The live probe reports only `streamed_both_turns`, `recalled_marker`,
`turn_count`, and `passed`; it does not print marker content or raw responses.
**Even a PASS does not satisfy G1, G2, G3 or G6**: durable state, protocol,
and task-level recovery each require their own gates.

## 4. Evidence & Durable feasibility

Copy `evidence-template.json` to a private evidence directory under
`poc/maf/evidence/` and record task ID, commit, exact SDK versions, command
without credentials, run UUID if available, observed exit code, UTC timestamp,
and trustworthy trace/artifact URI. Use `NOT_RUN`, `PASS`, `FAIL`,
`GAP` or `BLOCKED` accurately; this template does not assert any PASS.

A31 technical risks and untested private Durable backend proof requirements
are recorded in [DURABLE_FEASIBILITY.md](DURABLE_FEASIBILITY.md).

## Next slice

- A06/A07: probe MAF Todo/Mode/Context/History/Compaction using public APIs.
- A11/A12/A13: deterministic Workflow + independent verification/replanning.
- A18/A19/A20: real self-hosted API, Responses/Event Translator.
- A23–A30: Postgres task facts and task-level recovery before claiming G2/G6.
- A32/A33: real Python MAF Durable + Functions/MSSQL worker test.

References: `docs/POC.md`, `docs/POC_A_TASK_PLAN.md` and Accepted Contracts.

## Upstream MinIO image caveat (2026-10-08)

The upstream public Docker Hub and Quay MinIO images could not be pulled in GitHub Actions, and the fixed-release binary URL returned HTTP 410. The optional `local-oss` Compose profile therefore requires an explicitly configured `POC_OBJECT_STORAGE_IMAGE` from an enterprise-approved registry. This should not block the Harness POC: ArtifactStore/S3 integration is tested at A15 against an enterprise S3-compatible endpoint, not by building a storage product. Local object-store ports 9002/9003 are exposed only if the optional profile is started. No image mirror or official upstream availability is assumed.

Optional object store command after setting `POC_OBJECT_STORAGE_IMAGE` to an approved image reference:

```bash
docker compose --env-file poc/maf/.env -f poc/maf/compose.yml --profile local-oss up -d object-store
```
