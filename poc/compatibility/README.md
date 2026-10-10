# Verified Stack Baseline

This directory is a **POC evidence snapshot**, not a production dependency lock.

- [Human-readable baseline](../../docs/references/VERIFIED_STACK_BASELINE_20261010.md)
- [Machine-readable versions, tested combinations, negative tests, digest and Cube template](verified_stack.json)
- [Version/digest drift guard](verify_stack.py)

The default guard reads repository files only. `--profile` additionally checks the actual installed Python SDK distribution versions for one *specific* verified combination, and fails closed on mismatches or missing distributions. No test downloads packages, starts Cube or calls a model.

Do not put all SDK versions into one global requirements file: `e2b 2.53.1` is a separately observed incompatible version, and the native E2B POC runs in its own venv. This manifest is to seed per-Run frozen bindings according to the Accepted [Registry and Versioning Contract](../../docs/references/REGISTRY_AND_VERSIONING.md), *not* to treat a passed POC as automatically deployment-ready.

For a new version: create a separate candidate snapshot, run isolated integration/regression tests (including real Cube and Tool SDK tests), record the resulting artifact digest and evidence, then promote a new verified baseline. Keep prior positive and negative evidence unchanged.
