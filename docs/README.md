# Documentation / 文档中心

Root [README](../README.md) is the short open-source landing page. This directory holds maintained user, operator and developer documentation; architecture decisions and historical POC evidence are not interchangeable with production instructions.

| Goal | Maintained source | Scope |
|---|---|---|
| Start in 5 minutes | [Quickstart](guides/QUICKSTART.md) | Local Docker and localhost Inspector |
| Understand the screens | [User guide](guides/USER_GUIDE.md) | Browser flows, evidence and limitations |
| Install and troubleshoot | [Deployment](deployment/README.md) | Compose profiles, config and lifecycle |
| Build, package, upgrade | [Release guide](deployment/RELEASE.md) | Maintainer checklist; production still NO-GO |
| HTTP and SSE contracts | [API hub](api/README.md) | Public API / Inspector API / OpenAPI |
| Current decisions | [Architecture](ARCHITECTURE.md) · [Guardrails](ARCHITECTURE_GUARDRAILS.md) | Accepted constraints |
| Architecture diagrams | [Architecture Views](ARCHITECTURE_VIEWS.md) | **Only canonical Mermaid source** |
| Phases and backlog | [Milestones](DEVELOPMENT_MILESTONES.md) · [Development Backlog](DEVELOPMENT_BACKLOG.md) | M3–M8 bounded CLOSED, M9 pending |
| Alternatives, ADR context | [References](references/README.md) · [Architecture Backlog](ARCHITECTURE_BACKLOG.md) | Historical and candidate decisions |
| POC and regression evidence | [POC Index](../poc/README.md) · [POC](POC.md) · [Retrospectives](retrospectives/) | Date-specific tests, not production guarantee |
| Superseded long homepage | [Historical overview (2026-10-11)](history/PROJECT_OVERVIEW_20261011.md) | Historic snapshot, not a how-to |

**Documentation rules.** API endpoints are documented from current source; Docker examples are development-only unless an acceptance gate says otherwise. Do not duplicate the nine diagrams in README or reclassify historic experiments as production releases. Avoid moving Accepted Contracts, OpenSpec archives or evidence paths without a dependency audit.