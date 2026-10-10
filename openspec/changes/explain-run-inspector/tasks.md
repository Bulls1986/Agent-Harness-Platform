# Tasks — explainable Run Inspector

- [x] Tests before behavior: added Run input/final result/backend API/UI acceptance assertions; verified Red (missing create(prompt), missing snapshot result and explanatory UI).
- [x] Implement PG nullable input_prompt + result_json atomic creation/terminal, legacy read compatibility and A→B input derivation.
- [x] Implement self-explanatory UI, purpose/state/Step input/output/final result, human-readable event timeline and collapsed raw JSON; retain text-safe rendering.
- [x] Green: 7 real Docker PG/API regression tests pass locally without skips.
- [ ] Extend live black-box assertions (RunResult, Step B verified A output and refresh), pass real Docker PG/Hatchet SDK execution.
- [ ] Pass OpenSpec strict validation and architecture tests; clean GitHub CI PR.
- [ ] Record root cause, learned design principles and limitations in retrospective; merge when all evidence is green.