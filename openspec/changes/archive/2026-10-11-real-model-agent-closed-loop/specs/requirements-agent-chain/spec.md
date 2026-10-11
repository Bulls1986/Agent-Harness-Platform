# Requirements Agent Chain

## ADDED Requirements

### Requirement: Agent A produces a verified structured requirements draft
The Pydantic AI stage SHALL request a structured requirement-analysis JSON response and validate its required feature, summary, capabilities, business_rules and acceptance_criteria before declaring Step A completed.

#### Scenario: A returns valid business analysis
- **WHEN** the real model produces the required nonempty fields for the user prompt
- **THEN** Step A stores a validated normalized JSON draft in Harness PostgreSQL and only then releases Step B

#### Scenario: A returns invalid or missing fields
- **WHEN** the response is not valid JSON or violates the structural schema
- **THEN** Step A SHALL reject the result; Step B SHALL NOT execute and business Run SHALL NOT be marked COMPLETED

### Requirement: Agent B independently reviews persisted A output
The OpenAI Agents SDK stage SHALL consume exactly the verified A output, request a review containing decision, issues, risks, recommendations and summary, validate it, and combine it with the original draft as an end-user readable report.

#### Scenario: Successful two-SDK business handoff
- **WHEN** Step A has a persisted validated draft and Step B passes schema validation
- **THEN** the final Run Result SHALL contain a readable summary, functional scope, business rules, acceptance criteria, review decision and risks; the Step B input SHALL match Step A's committed output

#### Scenario: Parent output is absent or different
- **WHEN** B's supplied input cannot be matched to Step A's verified persisted result
- **THEN** B SHALL be rejected before the model call

### Requirement: Run Result provenance is explicit
The final business Run Result SHALL distinguish `live` from `deterministic_local_model` and list source step/model metadata without leaking credentials; terminal business completion SHALL require successful verification and valid Provider Binding.

#### Scenario: Refresh and read back
- **WHEN** the user opens a completed live Run after Inspector restart
- **THEN** the same human-readable final result, two step outputs, mode and model ID SHALL be available from PostgreSQL

#### Scenario: Failed review
- **WHEN** B returns an invalid review structure
- **THEN** the Run SHALL NOT be marked COMPLETED and the UI SHALL surface an honest error observation