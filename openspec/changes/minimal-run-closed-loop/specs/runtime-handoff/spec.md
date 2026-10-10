# runtime-handoff

## ADDED Requirements

### Requirement: Real SDK invocation through replaceable AgentRuntime SPI
The POC SHALL invoke both Pydantic AI and OpenAI Agents SDK through existing public Runtime Adapters, not simulated SDK classes. Deterministic public local Models MAY be used to avoid remote model/network credentials.

#### Scenario: Two real runtime stages
- **WHEN** a valid initial Run is submitted
- **THEN** the Hatchet DAG SHALL invoke Pydantic AI first and OpenAI Agents SDK second, with their distinct runtime identifiers and matching persisted results

### Requirement: Model-only tasks consume zero Sandbox
The initial closed loop SHALL declare only model capability and SHALL NOT create Cube/E2B sandbox instances or execute Host Shell/Git. The absence of a sandbox grant MUST NOT block a pure model Run.

#### Scenario: Safe no-Sandbox invocation
- **WHEN** both Runtime Adapters perform model-only operations
- **THEN** the Run SHALL complete without allocating Sandbox and the output SHALL explicitly label Cube as NOT_REQUIRED_MODEL_ONLY

### Requirement: Typed runtime event translation
Each SDK result SHALL pass through the existing AgentRuntime Dispatcher to produce platform-owned typed events. For this iteration, text events are buffered output and SHALL NOT be described as actual token-level SSE.

#### Scenario: Persisting runtime results
- **WHEN** a Runtime Adapter returns output and a successful terminal runtime event
- **THEN** the Harness SHALL persist its typed events and Step result atomically before releasing downstream execution

### Requirement: No silent privileged operation fallback
Any FS/Shell/Git capability requested without a valid trusted Sandbox Grant MUST fail closed; no SDK or Worker may substitute Host-native execution.

#### Scenario: Untrusted Shell attempt
- **WHEN** a Run requests Shell while presenting no authorized Sandbox grant
- **THEN** the Runtime Dispatcher MUST reject before SDK or Host Shell executes