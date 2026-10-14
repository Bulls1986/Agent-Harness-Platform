# Agent Harness Platform

**Composable AI agent execution, durable workflows, verified handoffs — without locking applications to a single Agent SDK.**

[![Architecture](https://github.com/Bulls1986/Agent-Harness-Platform/actions/workflows/architecture-guard.yml/badge.svg)](https://github.com/Bulls1986/Agent-Harness-Platform/actions/workflows/architecture-guard.yml)
[![Integration](https://github.com/Bulls1986/Agent-Harness-Platform/actions/workflows/closed-loop-poc.yml/badge.svg)](https://github.com/Bulls1986/Agent-Harness-Platform/actions/workflows/closed-loop-poc.yml)
[![GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)

> **正式研发实施 (active development) · Production NO-GO.** M3–M8 are closed only within their documented, bounded acceptance scope. Docker Compose starts a **localhost-only development Inspector**, not a production service. See [milestones](docs/DEVELOPMENT_MILESTONES.md).

Agent Harness Platform is a Python-based execution platform for composing independent AI agents into reliable tasks. It provides shared Run / Plan / Step / Attempt facts, optional sandbox execution, approval, structured handoff and traceable results. **Hatchet** owns technical scheduling, while **Harness PostgreSQL** holds authoritative business execution facts. IAM, Secrets and Object Storage are external integrations, not rebuilt platform products.

## Features

- **Vendor-neutral runtimes:** demonstrated Pydantic AI and OpenAI Agents SDK; separate coding/runtime adapter boundaries.
- **Durable execution:** Hatchet workflow + PostgreSQL-backed state, events, idempotent submission, recovery and non-idempotent Tool Receipt reconciliation.
- **Verification and approval:** bounded three-Agent plan → code → verify workflow; approval rejection prevents side effects.
- **Workspace isolation:** optional Cube sandbox with bounded trusted execution; model-only runs need no sandbox.
- **Development Inspector:** browser-facing Run evidence and an opt-in local versioned API demonstration.

## Quick start · local Docker

Requires Docker Engine / Docker Desktop with Compose V2, Git and free port **8765**. Default demo uses deterministic model responses and disposable local credentials; **no model key is required**.

```bash
git clone https://github.com/Bulls1986/Agent-Harness-Platform.git
cd Agent-Harness-Platform
docker compose up -d postgres
docker compose --profile inspector up -d --build inspector
```

Open **http://127.0.0.1:8765**. Inspect the Run timeline and persisted results; see the [Quickstart](docs/guides/QUICKSTART.md) for verification, cleanup and troubleshooting. Optional `/m7-demo` exposes a **synthetic local identity**, not enterprise authentication. Never publish these development ports directly to the internet.

## Architecture

```text
Client / verified Gateway
          │ versioned API · typed SSE
          ▼
Harness Domain (Run · Plan · Step · Attempt · Approval · Receipt)
          │                         └── PostgreSQL domain facts
          ▼
Hatchet durable workflow / shared Worker
          ├── Pydantic AI runtime
          ├── OpenAI Agents SDK runtime
          └── Coding runtime → optional trusted SandboxProvider / Cube
```

The architecture deliberately avoids a second technical scheduler or a provider-owned business state machine. Accepted [G01–G20 architecture guardrails](docs/ARCHITECTURE_GUARDRAILS.md) govern changes.

### 3.1 八类分层架构视图

The **nine canonical Mermaid diagrams** (eight views plus runtime recovery) are maintained only in [Architecture Views](docs/ARCHITECTURE_VIEWS.md), with rationale in [Architecture](docs/ARCHITECTURE.md).

## Documentation

| Topic | Start here |
|---|---|
| Documentation directory | [Docs hub](docs/README.md) |
| Get started / operate Inspector | [Quickstart](docs/guides/QUICKSTART.md) · [User guide](docs/guides/USER_GUIDE.md) |
| Deploy / maintain / release | [Deployment guide](docs/deployment/README.md) · [Release guide](docs/deployment/RELEASE.md) |
| Public HTTP API, SSE and OpenAPI | [API documentation](docs/api/README.md) |
| Architecture and diagrams | [Architecture](docs/ARCHITECTURE.md) · [Architecture Views](docs/ARCHITECTURE_VIEWS.md) |
| Project status and decisions | [Milestones](docs/DEVELOPMENT_MILESTONES.md) · [Backlog](docs/DEVELOPMENT_BACKLOG.md) |
| Contributor workflow | [AGENTS.md](AGENTS.md) · [Guardrails](docs/ARCHITECTURE_GUARDRAILS.md) |

## Repository layout

```text
.github/      PR workflow and CI pipelines
docs/         guides, deployment, API, architecture, history and evidence
openspec/     versioned requirements, accepted specs and archived changes
poc/          bounded executable integrations and local Inspector
scripts/      repository and documentation checks
tests/        contract, architecture and documentation regressions
compose.yaml  local PostgreSQL + Inspector Docker profiles
```

## Current limitations

This is **not** a production-ready distribution: no published hardened image, verified enterprise gateway/IdP, real OSS authorization/signing, guaranteed cross-host recovery or M9 capacity/security acceptance. Test ArtifactRefs and independent PostgreSQL effect ledgers are synthetic fixtures, not production object storage or Tools. Consult [Release / Readiness](docs/deployment/RELEASE.md); keep all consumer-specific source, secrets and data outside this repository.

## Contributing and license

Read [Contributing](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) before changes, preserve architecture contracts, and include reproducible tests/CI evidence. Licensed under the [GNU GPL v3.0](LICENSE); see the license for redistribution obligations.