# run-inspector

## ADDED Requirements

### Requirement: Local browser entrypoint shall start a real business Run
The POC SHALL provide a lightweight, localhost-only browser Run Inspector. A submitted prompt SHALL create a real platform Run and durable PostgreSQL Outbox before real Hatchet dispatch. The page SHALL NOT simulate success or create a dummy result.

#### Scenario: User submits a new prompt
- **WHEN** the user clicks Start Run on the localhost page with a nonempty prompt
- **THEN** the server returns a new stable platform Run ID, persists a CREATED Run in PostgreSQL and starts the actual Hatchet processing asynchronously without blocking the browser

#### Scenario: Runtime or database unavailable
- **WHEN** the necessary PostgreSQL or Hatchet service cannot run
- **THEN** the UI shows an actionable error and SHALL NOT announce a successful Run

### Requirement: Inspector shall present persisted execution evidence
The UI SHALL show platform Run ID, current business state, Hatchet Provider WorkflowRun ID, Plan Version, Outbox state, two Agent Steps and their Attempts/outputs, and a chronological platform Event timeline. Every displayed result SHALL originate from Harness PostgreSQL queries or a validated backend API, never hard-coded success records.

#### Scenario: Two agents complete
- **WHEN** Pydantic AI Step A and OpenAI Agents SDK Step B finish through the real Hatchet DAG
- **THEN** the UI shows both Step states/results, the dependency handoff and one authoritative platform Run COMPLETED state

#### Scenario: Engine runtime events arrive
- **WHEN** an individual SDK emits its own runtime completed event
- **THEN** the UI identifies it as a Step/Runtime event; it SHALL NOT imply the parent platform Run has completed

### Requirement: Refresh/reopen shall reconstruct the same Run
The backend SHALL expose at least POST /api/runs, GET /api/runs, GET /api/runs/{run_id}, and GET /api/runs/{run_id}/events?after=cursor. The UI SHALL reload a selected Run by platform ID and reconstruct the timeline using persisted events after refresh or server restart. Polling is acceptable; synthetic token streaming is NOT.

#### Scenario: Browser refresh
- **WHEN** the user refreshes the page after completion
- **THEN** the selected Run can be found in the run list and has the same Provider Binding, Step results and ordered event sequence backed by PostgreSQL

#### Scenario: Duplicate or delayed polling
- **WHEN** the client polls again with the last event sequence as cursor
- **THEN** only later events are returned in increasing sequence order, and previously shown events are not duplicated

### Requirement: Debug UI shall stay thin and safe
The Inspector MUST run on localhost by default, MUST avoid embedding secrets/tokens in pages/events, MUST render Agent output as plain text, and MUST NOT add authentication products, persistent per-session worker processes or a new scheduler.

#### Scenario: Model-only task
- **WHEN** the Run invokes the model-only two-SDK workflow
- **THEN** the Inspector shows it without creating Cube instances or allocating Session-specific Agent processes

#### Scenario: Incomplete POC gates
- **WHEN** the Inspector is displayed
- **THEN** it SHALL label itself local/development POC and clearly distinguish untested real Token SSE, Cube cross-worker recovery, Approval and side-effect Receipts