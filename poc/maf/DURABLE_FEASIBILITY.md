# POC-A31 Durable production route — preliminary evidence review

> Date: 2026-10-08  
> Status: **RESEARCH COMPLETE / DEPLOYMENT AND RECOVERY NOT RUN**  
> This note is a POC feasibility input, NOT a new ADR, and does not revise the Accepted Durable Contract.

## What the public documentation establishes

| Route | Python entry | Durable state owner | What is currently supported by documentation | POC evidence status |
|---|---|---|---|---|
| Standard MAF Workflow checkpoint | Framework Workflow/CheckpointStorage | Framework-specific checkpoint storage | Workflow checkpoint/resume and storage abstraction; not equivalent to distributed durable execution | Not tested |
| MAF Durable BYOC | `agent-framework-durabletask` + `DurableAIAgentWorker` | Durable Task Scheduler / TaskHub-compatible service | Own worker/container; Durable Task Scheduler worker endpoint; official samples target scheduler/emulator | Docs reviewed, no backend deployed |
| MAF Durable Functions | `agent-framework-azurefunctions` / `AgentFunctionApp` | Azure Functions + Durable Functions storage provider | Durable Functions has independent MSSQL storage provider documented for disconnected/on-prem SQL Server | **Combined Python MAF + Functions + MSSQL end-to-end NOT verified** |
| External Durable CP | Temporal adapter + MAF agent runtime | Existing Temporal cluster | Architecture candidate, to be measured in POC-C | Not tested |

**Important:** A self-hosted BYOC worker is not itself a self-hosted durable state backend. `DurableTaskSchedulerWorker(host_address=...)` still needs compatible Durable Task Scheduler infrastructure; DTS emulator is a developer tool, not proof of a privately hosted production backend. Likewise, MSSQL as a Durable Functions storage provider does NOT establish that an arbitrary standalone Durable Task Scheduler gRPC client can point to SQL Server.

## A31 remaining proof

1. Resolve exact `agent-framework-durabletask` and `agent-framework-azurefunctions` compatible package versions and licensing/support levels.
2. On real self-hosted Functions Runtime + MSSQL storage provider, register a Python MAF agent and verify activity/workflow execution end to end.
3. Restart two workers; verify persistent WAITING_APPROVAL and no repeat of completed side effects.
4. Capture deployment topology, SQL Server edition/license and runtime/hosting package prerelease exposure.
5. If the combined route fails or requires private APIs / bespoke TaskHub backend, record FAIL/GAP; downgrade MAF Durable CP candidacy, **do not implement custom durable infrastructure**.

## Sources reviewed

- [Microsoft Agent Framework Durable Extension](https://learn.microsoft.com/en-us/agent-framework/hosting/azure-functions)
- [Durable Functions storage provider comparison](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-storage-providers)
- [Durable Functions MSSQL quickstart](https://learn.microsoft.com/en-us/azure/azure-functions/durable-functions/quickstart-mssql)
- [Microsoft Agent Framework self-hosting](https://learn.microsoft.com/en-us/agent-framework/hosting/self-hosting)
- [Accepted architecture contract](../../docs/references/MAF_PYTHON_DURABLE_PRIVATE_DEPLOYMENT.md)

## 2026-10-08: A31 public API and hosting topology recheck

Evidence and upstream version references (explicitly **not** execution proof):

- Official Python Durable Extension repo currently declares
  `agent-framework-durabletask==1.0.0b260922` (beta), with
  `agent-framework-core>=1.19.0,<2`,
  `durabletask>=1.7.1,<2`, `durabletask-azuremanaged>=1.4.0,<2`.
  Repo: https://github.com/microsoft/agent-framework-durable-extension/blob/main/python/packages/durabletask/pyproject.toml.
- Upstream native non-Functions Worker uses
  `DurableTaskSchedulerWorker(host_address,taskhub)`,
  `DurableAIAgentWorker.configure_workflow()`, and
  `DurableWorkflowClient` for start/HITL/resume.
  Samples:
  https://github.com/microsoft/agent-framework-durable-extension/tree/main/python/samples/08_workflow
  and
  https://github.com/microsoft/agent-framework-durable-extension/tree/main/python/samples/09_workflow_hitl.
- Official documentation describes **DTS as Azure-managed** and the
  `mcr.microsoft.com/dts/dts-emulator` Docker image for **local development**.
  The Docker emulator does not establish availability/support/licensing of a
  distributable, self-managed **production** DTS backend:
  https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-storage-providers.
- Durable Functions **can** use a disconnected/on-premises Microsoft SQL
  Server storage provider. This is different from pointing
  `DurableTaskSchedulerClient` directly at MSSQL. The combination
  `AgentFunctionApp (Python) + Azure Functions Core Tools/host + MSSQL
  Durable Functions provider` must be **run and exercised**, not inferred
  from independent product docs.
- Official `agent-framework-azurefunctions==1.0.0b260922` remains beta,
  and the Azure Functions workflow example
  (`python/samples/azure_functions/12_workflow_hitl`) uses an extension
  bundle without MSSQL-specific configuration. These examples do **not**
  count as Python+MSSQL integration evidence:
  https://github.com/microsoft/agent-framework-durable-extension/blob/main/python/packages/azurefunctions/pyproject.toml.

### A31/A32/A33 bounded DTS emulator verification

Separate Docker Compose file:
`poc/maf/compose-durable-emulator.yml` (localhost-only ports 18080/18082,
isolated TaskHub `pocmaf`). Pinned beta dependencies:
`poc/maf/requirements-durable-emulator.txt`. Actual native MAF
`DurableAIAgentWorker` / `DurableWorkflowClient` POC:
`poc/maf/durable_emulator_probe.py`.

The CI fault injection is intentionally two *OS processes* sharing the
DTS emulator: Worker A completes the deterministic Prepare activity and
pauses at native HITL; Worker A is killed; Worker B registers exactly the
same workflow and receives the APPROVED/REJECTED decisions. A shared
file marker detects repeated completed Prepare/controlled Action activity.
This marker is a **test observer**, not an application checkpoint or a
claim of exactly-once external tool behavior. CI captures
`pip freeze` and Docker image digest to identify mutable upstream inputs.

Even if it passes, the only justified conclusion is:
**MAF Python + official Durable Extension + DTS dev emulator can retain
the Workflow/HITL across a Worker replacement**. Production requirements
G1/G2/G6/G8 remain OPEN until a truly self-managed backend path passes
real cross-worker lifecycle/handoff/replay on that backend. Do not import
the DTS emulator into the normal platform production Compose profile.

### Next production candidate experiment: Functions + MSSQL

This is a **distinct POC**, not a change of connection string:
1. Deploy a local SQL Server Developer Edition instance and Functions
   Runtime v4 with the supported MSSQL storage provider bundle; configure
   an empty TaskHub and required Azure Functions host storage separately.
2. Register a minimal **non-LLM** Python `AgentFunctionApp(workflow=...)`
   using the same MAF Workflow HITL pattern. Confirm Functions runtime
   logs that MSSQL storage provider actually owns Durable orchestration
   state (not silently Azure Storage or DTS).
3. Kill Worker A while a durable HITL request remains pending; start
   Worker B against the **same SQL Server task hub**; respond and assert
   no replay of completed activity plus durable outcome and DB evidence.
4. Check package compatibility, disconnected operation, SQL Server license
   and production support of the combined stack. If this cannot work
   strictly on public supported interfaces, record GAP and compare the
   external Durable Control Plane candidate (Temporal POC-C).

## Explicit conclusion

A31 is **IN_PROGRESS**. We have a source-grounded candidate pathway and identified a critical unproven integration. Neither G1 nor G6 nor G8 is PASS on this basis.
