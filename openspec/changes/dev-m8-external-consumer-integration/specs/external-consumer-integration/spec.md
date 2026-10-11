# DEV-M8 · External API integration

## ADDED Requirements

### Requirement: Stable boundary-only integration
An independent generic consumer MUST use a versioned public Harness API/SDK without importing private Harness sources, database tables or technical scheduler controls.

#### Scenario: Authorized consumer starts an execution
- **WHEN** a test consumer provides authorized context and approved Run input
- **THEN** Harness returns a verifiable Run reference, scoped event stream and consistent terminal outcome through the public contract

### Requirement: Consumer errors fail closed
A consumer MUST NOT infer success from buffered output, forged IDs, unverified tool effects or lost acknowledgements.

#### Scenario: Untrusted or unsupported request
- **WHEN** the consumer presents an invalid API version, identity/scope or stale command
- **THEN** the operation is rejected with no cross-scope data exposure or hidden tool execution

### Requirement: Consumer data is owned externally
The generic integration MUST NOT require product-domain source, real customer records or business-specific migration artifacts in Harness.

#### Scenario: Private business onboarding
- **WHEN** a private application consumes Harness
- **THEN** application source, business policy and migration plan remain entirely in the consumer's private repository
