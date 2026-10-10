# run-workflow-binding

## ADDED Requirements

### Requirement: Stable Run to Hatchet execution mapping
The system SHALL create a platform-owned Run identifier and immutable initial Plan Version before dispatch. It SHALL record the Hatchet WorkflowRun identifier only as a Provider Binding, and SHALL NOT treat that identifier as the business Run ID.

#### Scenario: Real workflow acknowledged
- **WHEN** a Run creation transaction commits and Hatchet returns one WorkflowRun ID
- **THEN** the Harness stores exactly one mapping for that Run/segment and preserves both independent identifiers

#### Scenario: Duplicate platform Run request
- **WHEN** a Run ID already exists
- **THEN** creation MUST reject the duplicate without submitting another Hatchet Workflow

### Requirement: Verified dependent Step handoff
The system SHALL execute two ordered Steps through a real Hatchet DAG. Step B MUST depend on the persisted successful result of Step A, not only an in-memory model response.

#### Scenario: Pydantic to OpenAI handoff
- **WHEN** Step A completes with persisted verified output
- **THEN** Step B receives exactly that output and may execute its own distinct Runtime Adapter

#### Scenario: Invalid or absent parent
- **WHEN** Step A has no completed matching persisted output
- **THEN** Step B MUST fail closed and MUST NOT call its SDK

### Requirement: Platform-owned business completion
Hatchet Task completion SHALL be treated as technical evidence, not authorization to terminate a business Run. The Harness MUST verify every required Step, the Provider Binding and state transition before writing a terminal Run.

#### Scenario: Successful completion
- **WHEN** the Provider reports completion and both required platform Steps have persisted successful results
- **THEN** the business Run MAY atomically become COMPLETED and an audit Event SHALL be appended

#### Scenario: Provider completes without verified Steps
- **WHEN** a required platform Step is pending, failed or unknown
- **THEN** the business Run MUST NOT become COMPLETED

### Requirement: Retry, Replan and recovery boundaries
The minimal implementation MUST NOT equate every Hatchet internal technical delivery Retry with a new business Attempt. Replan is outside the initial executable happy path; the data and interfaces MUST NOT assume permanent 1:1 Platform Step↔Hatchet Task correspondence.

#### Scenario: Historical Step already completed
- **WHEN** an already committed PURE Step is observed or delivered again with identical input
- **THEN** it MUST return the previously committed result without repeating the SDK invocation

#### Scenario: Changed input for completed Step
- **WHEN** replay presents a different input for an already committed Step
- **THEN** it MUST reject the replay and preserve the original output