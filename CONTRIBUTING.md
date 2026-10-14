# Contributing

Agent Harness Platform is developed through small, reviewable changes with reproducible evidence. Before writing code, read [AGENTS.md](AGENTS.md) and the [G01–G20 architecture guardrails](docs/ARCHITECTURE_GUARDRAILS.md).

## Workflow

1. Check the [development plan](docs/DEVELOPMENT_MILESTONES.md) and relevant accepted [OpenSpec](openspec/) and [architecture contract](docs/references/README.md). Keep work within the agreed milestone; don't import consumer-specific business code, customer data or credentials.
2. Make a dedicated branch; for behavior changes write failing regression first, implement minimally, and record actual environment evidence. Documentation-only changes should validate links, schemas and repository navigation.
3. Use `python -B -m unittest discover -s tests -v`, `python -B scripts/check_architecture_guardrails.py`, `python -B scripts/export_openapi.py --check` (requires FastAPI dependencies), and the relevant integration/PG tests. A skipped test cannot count as PASS.
4. Submit a focused PR via [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md), including affected Gxx/ADR, scope exclusions, RED→GREEN proof, failure paths, CI and remaining risk.
5. Do not mark a milestone closed or a release production-ready until its own official gates succeed.

## Reporting issues

Please describe a reproducible behavior, the component/version, the smallest non-sensitive example, expected vs actual result, and relevant non-secret logs. Do not post private API keys, production credentials, proprietary schemas or full customer traces in issues.

See [Documentation](docs/README.md) and [Deployment](docs/deployment/README.md) to distinguish current source-level capabilities from the localhost Inspector.