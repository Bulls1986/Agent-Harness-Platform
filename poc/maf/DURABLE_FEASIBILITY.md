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

## Explicit conclusion

A31 is **IN_PROGRESS**. We have a source-grounded candidate pathway and identified a critical unproven integration. Neither G1 nor G6 nor G8 is PASS on this basis.
