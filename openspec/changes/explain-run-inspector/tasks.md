# Tasks — explainable Run Inspector

- [x] Tests before behavior: added Run input/final result/backend API/UI acceptance assertions; verified Red (missing create(prompt), missing snapshot result and explanatory UI).
- [x] Implement PG nullable input_prompt + result_json atomic creation/terminal, legacy read compatibility and A→B input derivation.
- [x] Implement self-explanatory UI, purpose/state/Step input/output/final result, human-readable event timeline and collapsed raw JSON; retain text-safe rendering.
- [x] Green: 7 real Docker PG/API regression tests pass locally without skips.
- [x] Live black-box: RunResult from real Docker PG, Step B.input=A.output, 14 events, one terminal; local Hatchet/SDK PASS Run run-2e0fa189e0b34d40b38d241384d0deb7; Inspector restart + same persisted Run PASS.
- [x] OpenSpec strict validation PASS, 7 Docker PG/API tests PASS, 8 architecture guard tests PASS, real GitHub CI 38039434789 PASS, architecture CI 38039434810 PASS.
- [x] Record root cause, Red/Green failures and lessons in [retrospective](../../../docs/retrospectives/INSPECTOR_EXECUTION_EXPLANATION_20261010.md); limitations remain explicit.
- [ ] Merge PR #56 only after final head checks PASS; verify Main contains specs and implementation.