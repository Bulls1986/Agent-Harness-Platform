# Durable Run Facts — explainable result

## MODIFIED Requirements

### Requirement: Local POC retains the original run input and final result for inspection
The Harness PG business Run fact SHALL capture optional local-only `input_prompt` at creation and `result_json` atomically with its final business transition. The final result SHALL include the Step B output, the source Step, both Step outputs and a mode marker identifying deterministic local models. Hatchet engine tables are not used as business facts.

#### Scenario: New run is created
- **WHEN** POST /api/runs accepts a nonempty prompt
- **THEN** the initial Run and Outbox share one PG transaction with the submitted prompt, and GET /api/runs/{id} exposes it

#### Scenario: Both steps complete
- **WHEN** the platform verifies both Step outcomes and the Provider Binding
- **THEN** the final Run result and run.completed event are committed together, and subsequent completion attempts remain rejected

#### Scenario: Older PG data is present
- **WHEN** the minimal schema is upgraded in place
- **THEN** existing records load without loss; an old missing prompt remains null, and a pre-upgrade completed Run may explicitly derive a display-only final output from its already committed Step B output

### Requirement: Sensitive input restrictions are explicit
This local POC SHALL warn users not to submit secrets or sensitive data; production use requires governed refs/redaction instead of plain-text prompt storage.

#### Scenario: Demo description
- **WHEN** the user sees the start form
- **THEN** the plain-text storage limitation is stated prior to submission