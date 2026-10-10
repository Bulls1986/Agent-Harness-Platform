# Run Inspector UI explanation contract

## ADDED Requirements

### Requirement: Inspector explains purpose and limitations before raw technical details
The UI SHALL explain that it verifies a Hatchet-coordinated two-real-Agent-SDK handoff and PostgreSQL persistence, not a real business inference task. It SHALL explicitly explain the fixed local deterministic models and absence of real remote-LLM calls.

#### Scenario: Open the page before running anything
- **WHEN** a reviewer opens the Inspector
- **THEN** they can read why the page exists, the order of Step A/B, and what this demo does *not* prove without scrolling through JSON

### Requirement: The two nodes have distinct visible purpose, input and output
Each Step SHALL show the SDK name, what action is performed, the persisted input, actual output, status and Attempt count. Step B input SHALL be the verified persisted Step A output.

#### Scenario: Completed Run
- **WHEN** a full Run reaches COMPLETED
- **THEN** Step A and Step B show purpose, exact input and exact output, and Step B input equals Step A persisted output

#### Scenario: Historical record lacks original input
- **WHEN** an older Run did not persist input_prompt
- **THEN** the UI marks the original input as unrecorded, not a guessed prompt

### Requirement: Final business Run result is immediately visible
The UI SHALL show Run state and a final output area before node details. New Runs SHALL store a dedicated immutable-by-terminal-transition Run result in the Harness business database; it SHALL identify Step B as the source. A non-terminal Run SHALL show a waiting state, not a fabricated success.

#### Scenario: Run completes
- **WHEN** both required Steps and Provider Binding are confirmed
- **THEN** the terminal Domain transaction persists a final_output from Step B and the UI shows that value

#### Scenario: Refresh or backend restart
- **WHEN** a reviewer reopens a Run
- **THEN** the same persisted final result and each Step's input/output appear from PostgreSQL, not from process/browser cache

### Requirement: Raw JSON is opt-in debugging
The default timeline SHALL use human-readable event descriptions. Raw event payloads and Provider IDs SHALL remain available in a closed-by-default details section.

#### Scenario: Typical run is inspected
- **WHEN** the user selects a Run
- **THEN** they can see purpose, result and readable timeline without raw JSON; expanding details reveals the original JSON

### Requirement: Display-only and safe scope
Input/output SHALL always be escaped as text, never interpreted as HTML. The Inspector stays localhost-only and shall not create a new execution engine, credential store or unisolated Host Shell.

#### Scenario: A prompt contains markup
- **WHEN** input or output contains HTML-like text
- **THEN** the UI displays it as literal text and does not execute it