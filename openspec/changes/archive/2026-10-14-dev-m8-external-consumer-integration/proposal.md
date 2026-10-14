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

CLOSED (original bounded synthetic external-consumer contract; effective on archive PR passing latest Head CI and merging). M6/M7 CLOSED; 7/7 Node TDD, actual public HTTP/PG/Native Hatchet + two Agent SDK M8 CI SUCCESS, security/retrospective evidence docs/retrospectives/DEV_M8_FINAL_CLOSEOUT_20261014.md. Enterprise IdP/OSS/native physical cancel and production deployment NOT VERIFIED.
