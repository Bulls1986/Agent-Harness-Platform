# Design · Independent external consumer

- Application → versioned public Harness API/SDK → Harness Domain/Runtime → Hatchet/Cube. No reverse dependency.
- The sample consumer shall use artificial data only. No private business identifiers, schema, group/project names or credentials.
- Harness provides only execution, event, approval, artifact-reference and sandbox contracts. Identity/authorization evidence enters through a trusted, documented public boundary.
- Fail closed if an unsupported contract version, invalid scoped identity, missing receipt or unknown external side effect is observed.
- CI / real API integration and architecture checks are required before completing this stage.
