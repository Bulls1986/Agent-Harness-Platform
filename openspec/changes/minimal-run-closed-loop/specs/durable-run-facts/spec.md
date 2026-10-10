# durable-run-facts

## ADDED Requirements

### Requirement: Docker PostgreSQL with independent data ownership
The POC SHALL use PostgreSQL 16 in Docker and separate Harness business facts and Hatchet engine storage into isolated PostgreSQL databases (or independently owned schemas). It SHALL NOT use SQLite as the execution store, nor mutate existing unrelated local POC containers.

#### Scenario: Container bootstrap
- **WHEN** `docker compose up -d postgres` completes and healthcheck passes
- **THEN** `hatchet_poc` and `harness_poc` SHALL be available and Harness schema initialization SHALL succeed

#### Scenario: Engine database isolation
- **WHEN** the Agent Workflow executes
- **THEN** Harness business queries SHALL access only Harness-owned objects and Hatchet technical Task History SHALL remain engine-owned

### Requirement: Atomic initial Run and Outbox intent
The Harness SHALL commit the Run, initial Steps and workflow creation Outbox command in one Harness PostgreSQL transaction before contacting Hatchet. Dispatch attempts MUST have a stable key; cross-database distributed 2PC is forbidden.

#### Scenario: Transaction abort
- **WHEN** the Run creation transaction fails before commit
- **THEN** no valid Outbox command SHALL exist for submission

### Requirement: Fail closed on unknown workflow creation ACK
The Harness MUST distinguish PENDING, DISPATCHING, CONFIRMED and BLOCKED_UNKNOWN Outbox states. A network/API timeout after attempting workflow creation SHALL NOT be classified as certainly-not-executed; until reliable engine-side discovery/dedup is verified, resubmission MUST be blocked.

#### Scenario: Lost ACK
- **WHEN** a workflow submission may have succeeded but its acknowledgment is lost
- **THEN** the Outbox SHALL become BLOCKED_UNKNOWN and a subsequent blind dispatch MUST be rejected

### Requirement: Durable ordered business events and state projection
The Harness SHALL persist business Events independently of Hatchet execution history and assign monotonically increasing per-Run sequence values. A replay SHALL preserve event type, order and payload; model completion text SHALL NOT be advertised as real Token-level streaming.

#### Scenario: Reopen persisted Run
- **WHEN** a second process reads a previously completed Run from the same PostgreSQL database
- **THEN** it SHALL recover the committed Provider Binding, Step states, digests and ordered domain Events

#### Scenario: Late terminal mutation
- **WHEN** a completed Run receives another completion request
- **THEN** the Harness MUST reject reopening or duplicating its terminal Event

### Requirement: Explicit unfinished reliability scope
The POC SHALL report external non-idempotent Tool Receipts, UNKNOWN reconciliation, authentic Worker→Cube Fencing, durable approvals, real token SSE, 100 active Runs and Worker A→B failover as NOT_TESTED unless independently proven on this exact end-to-end path.

#### Scenario: POC report
- **WHEN** the happy path passes
- **THEN** its machine-readable summary SHALL distinguish actually tested features from remaining production gates