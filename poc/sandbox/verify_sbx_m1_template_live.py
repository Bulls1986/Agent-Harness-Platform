"""Opt-in real Cube Template build/alias/delete smoke for DEV-SBX M1.

Only touches template(s) freshly built by this smoke. Never runs in default CI.
Requires explicit mutation opt-in, OCI image and actual Cube SDK connection.
"""
from __future__ import annotations

import json
import os
import time
from uuid import uuid4

from poc.sandbox.sbx_template import CubeTemplateGateway


def run():
    if os.environ.get("SBX_M1_ALLOW_DISPOSABLE_TEMPLATE_MUTATION") != "1":
        raise RuntimeError("Disposable Cube template mutation requires explicit opt-in")
    image = os.environ.get("SBX_M1_DISPOSABLE_OCI_IMAGE", "")
    if not ((image.startswith("localhost:5000/") and "@sha256:" in image)
            or image == "cube-sandbox-int.tencentcloudcr.com/cube-sandbox/sandbox-code:latest"):
        raise RuntimeError("Use explicitly approved disposable OCI image source")
    if not os.getenv("CUBE_API_URL"):
        raise RuntimeError("Real Cube API endpoint required")
    from cubesandbox import Template
    scope = "sbx-m1-isolated-" + uuid4().hex
    principal = "sbx-m1-operator-local"
    admin = CubeTemplateGateway(
        sdk=Template, authorize=lambda s, p, a, _: s == scope and p == principal)
    alias = "sbxm1tmp-" + uuid4().hex[:10]
    original = None
    job = None
    success = False
    try:
        before = {t["template_id"] for t in admin.list(scope=scope, principal=principal)}
        print("EXISTING_TEMPLATES",len(before),flush=True)
        accepted = admin.build(scope=scope, principal=principal,
                               cube={"image": image, "name": alias, "writable_layer_size": "1G",
                                     "exposed_ports": [49983], "probe_port": 49983,
                                     "probe_path": "/health"})
        original = accepted.get("template_id")
        print("DISPOSABLE_BUILD_ACCEPTED", json.dumps(accepted),flush=True)
        if not original or original in before:
            raise RuntimeError("Native build did not return a fresh isolated Template ID")
        job = accepted.get("job_id")
        if not job:
            raise RuntimeError("Missing native Cube Template Build job ID")
        state = None
        for iteration in range(180):
            # Native async job exists before Template.get() is readable.
            # DO NOT resubmit Build because detail returned 404.
            outcome = Template.get_build_status(original, job)
            state = outcome.status.lower()
            if state in ("ready", "error", "failed"):
                print("DISPOSABLE_BUILD_TERMINAL",
                      json.dumps({"template_id": original, "status": state,
                                  "message": outcome.message[:200]}), flush=True)
                if state != "ready":
                    raise RuntimeError("Disposable Cube Template Build failed")
                item = admin.get(scope=scope, principal=principal, template=original)
                if item["status"] != "READY":
                    raise RuntimeError("Cube Build READY but Template not READY")
                break
            if iteration % 10 == 0:
                print("WAIT_DISPOSABLE_JOB", iteration, outcome.status,
                      outcome.progress, outcome.message[:80], flush=True)
            time.sleep(3)
        else:
            raise RuntimeError("Cube Build still active; use job ID for reconciliation")
        current = admin.set_alias(scope=scope, principal=principal,template=original,alias=alias)
        print("DISPOSABLE_ALIAS_APPLIED",json.dumps(current),flush=True)
        assert admin.resolve(alias) == original, "Cube Alias did not resolve to native ID"
        print("DISPOSABLE_ALIAS_RESOLVED",original,flush=True)
        success = True
    finally:
        if original:
            print("DISPOSABLE_DELETE_STARTED",original,flush=True)
            # Cube rejects deletion while Build is active.  Keep this
            # explicit rather than attempting repeated destructive requests.
            if job and Template.get_build_status(original, job).status.lower() not in (
                    "ready", "failed", "error"):
                print("CLEANUP_DEFERRED_ACTIVE_NATIVE_JOB", original, job, flush=True)
            else:
                admin.delete(scope=scope, principal=principal, template=original)
                leftovers = {x["template_id"] for x in admin.list(
                    scope=scope, principal=principal)}
                if original in leftovers:
                    raise AssertionError("Test Cube Template still exists after deletion")
                print("DISPOSABLE_DELETE_CONFIRMED", original, flush=True)
    if not success:
        raise RuntimeError("Cube Template native mutation not verified")
    print("SBX_M1_TEMPLATE_MUTATION_LIVE_PASS",flush=True)


if __name__ == "__main__":
    run()