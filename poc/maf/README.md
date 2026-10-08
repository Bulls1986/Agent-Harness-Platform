# POC-A0 — MAF HarnessAgent Self-host Smoke

> Status: **CODE READY / NOT YET EXECUTED AGAINST REAL MAF**. This is a bounded first implementation slice, **not** a POC gate PASS.

## Purpose

Prove the basic public Python API path `create_harness_agent` + `OpenAIChatClient`,
two-turn native session reuse, and streaming `chunk.text` from a locally launched
Python process **without Foundry Hosted Agent**. The provider/model are supplied
through the environment. No external shell, Git, browser, MCP, or sandbox tool is
exposed in A0.

This is a **runtime smoke**, not a substitute for the platform Run/Plan/Step/
Attempt domain model. Native MAF `AgentSession` must not be equated with a
durable Harness `Run` or a persisted cross-process checkpoint.

## Run

Python 3.11+ and an OpenAI Responses-compatible provider/account are required.
Install only the public MAF packages used here:

```bash
python -m pip install agent-framework-core agent-framework-openai
export OPENAI_API_KEY="<configure outside the repository>"
export MAF_POC_MODEL="<model-or-deployment-id>"
# Optional for a supported enterprise OpenAI-compatible gateway:
# export OPENAI_BASE_URL="https://<enterprise-gateway>/v1"
python poc/maf/smoke.py
```

PowerShell uses `$env:OPENAI_API_KEY` and `$env:MAF_POC_MODEL` instead of
`export`.

Override the prompt/model via `--model`, `--prompt`, `--follow-up`.
Do not commit API keys, provider payloads, or raw prompt/response logs. For
reproducibility, capture the installed package versions with
`python -m pip freeze` in private POC evidence, plus the platform and
provider configuration **without** credentials.

Unit tests require no network, vendor SDK or credentials:

```bash
python -m unittest discover -s poc/maf/tests -p "test_*.py" -v
python -m py_compile poc/maf/smoke.py
```

## Observable evidence

The smoke exits **0** only when both turns yield at least one non-empty text
chunk; exits **1** for provider errors or inconclusive output; exits **2**
for missing configuration or dependencies. It validates session object
reuse, not durable session persistence. Model output is printed to stdout
solely for local manual inspection.

| Gate / scenario | A0 outcome | Remaining evidence |
|---|---|---|
| S01 streaming | NOT RUN on real SDK | Local execution, TTFT, cancel, disconnect/reconnect |
| S03 plan | NOT RUN | Structured Plan/Step facts + TodoProvider mapping |
| G1 self-host | NOT RUN | Containerized runtime without Foundry + restart |
| G2 state autonomy | NOT RUN | Postgres Run/Session refs, opaque MAF checkpoint, OSS payload |
| G3 UI bridge | NOT RUN | Typed Event Translator and replay/reconnect |
| G6 task recovery | NOT RUN | Worker failure, safe boundary/attempt, reconciliation |
| S08 HITL | NOT RUN | Approval fact, durable wait, same Run resume |
| G4/G5 other adapters | NOT RUN | Model/Sandbox swap without domain model change |

## Next slice (POC-A1)

Introduce a **platform-owned test Run/Step/Attempt ledger** and a minimal
Event Translator around real MAF events. Verify actual public API compatibility
and persistence before attempting production-grade durable tests. Proceed to
the independently documented MAF Python Durable + MSSQL / Temporal decision
gate only after basic runtime execution is measured. Do not implement a
custom TaskHub/Workflow engine, lease coordinator, full IAM, MCP Governance,
cost accounting, APM or infrastructure backup/DR.

Related contracts: `docs/POC.md`,
`docs/references/DOMAIN_MODEL_AND_STATE_CONTRACT.md`,
`docs/references/TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md`,
`docs/references/MAF_PYTHON_DURABLE_PRIVATE_DEPLOYMENT.md`.

API reference: https://learn.microsoft.com/en-us/agent-framework/get-started/harness
