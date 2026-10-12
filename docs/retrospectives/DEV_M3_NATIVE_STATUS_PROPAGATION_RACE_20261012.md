# DEV-M3 · Hatchet Replan Native Workflow terminal observation race (2026-10-12)

## Symptom and cause

During the Inspector B.3b PR verification, GitHub Actions Closed Loop CI run 38247632262 failed at its existing PURE Replan v1-to-v2 live gate. The native v1 task result had returned, but a subsequent Hatchet workflow status lookup did not yet report a typed COMPLETED terminal. The guarded ReplanV2.promote correctly rejected it:

> Old Provider not proven COMPLETED; cancellation ACK is insufficient

This is an eventual-observation race in the test orchestrator, **not** permission to relax domain authorization. A completed native task result is distinct from the authoritative WorkflowRun terminal status.

## TDD and correction

- RED: added tests/test_native_provider_terminal_poll.py before implementation. It requires typed trusted Provider status, supports transient RUNNING then COMPLETED, rejects string COMPLETED, cancellation/failed and deadline expiry.
- GREEN: added poc/closed_loop/native_completion_gate.py, a bounded read-only Provider status observer (30-second budget, 250 ms polling), never creating a new WorkflowRun or treating cancellation ACK as completion.
- The real verify_replan_v2_hatchet script now waits for typed COMPLETED before calling the **unchanged** domain ReplanV2.promote, which independently repeats native status lookup and PG domain checks.
- Offline tests 4/4 PASS. In the actual Linux Hatchet Embedded/PG environment, both native Replan cases passed: normal v1-to-v2 and creation-ACK-loss reconciliation, separate WorkflowRun IDs, PG Plan v2 committed, Segment CONFIRMED, exit 0. Run IDs: m3-hatchet-29ce6322ea2a49feba1d99c9ccdaef81 and m3-hatchet-bbe49f46bbd94c439aa9edccc9028fd8.

## Architectural consequence

Maintain strict separation of provider task result, native terminal workflow state and Harness domain admission. Do not force Provider COMPLETED, accept a string assertion, or promote on cancellation ACK. Recheck the full remote PR Head CI after this correction; a local PASS cannot substitute for remote CI.
