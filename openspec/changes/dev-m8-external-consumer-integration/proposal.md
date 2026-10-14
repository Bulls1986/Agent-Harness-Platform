# DEV-M8 · External consumer integration

## Why

Agent Harness is an independent cross-domain execution platform. All vertical business applications are independently deployed consumers. Private application migration and its source materials are outside this repository.

## What Changes

Demonstrate a versioned, authenticated public Harness API/SDK against an external test consumer, including isolated Run/Conversation identity, streaming cursor, cancellation and failure propagation.

## Non-goals

Do not implement, enumerate or migrate a specific private application, internal repository, business schema, deployment, identity configuration or data source.

## Dependencies

DEV-M3 through DEV-M7 and accepted G01–G20/Harness owner contracts. Production GO remains independently gated.

## Status

ACTIVE / PARTIAL. M7/M6 are CLOSED. Independent generic consumer contract 7/7 local tests PASS; real public API + PG/Native integration CI and final security review/retrospective are pending. No customer data or private consumer implementation.
