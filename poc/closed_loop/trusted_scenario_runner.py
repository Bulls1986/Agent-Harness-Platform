"""Opt-in, operator-authenticated B03 scenario execution and durable evidence.

Never a generic shell/RPC facility. Its sole privileged operation is a fixed
synthetic-data native Hatchet + real Cube verifier. A local-only Inspector must
not gain a route to arbitrary host commands, Cubes or kill(2). Credentials
must be injected by the operator, never returned by the Catalog or HTML.
"""
from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
from typing import Callable
from uuid import uuid4


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
NATIVE_B03_TIMEOUT_SECONDS = 780
_PUBLIC_FIELDS = (
    "outcome", "run_id", "execution_id", "workflow_run_id",
    "worker_a_pid", "worker_a_exit_code", "worker_b_pid",
    "b_worker_role", "native_retry_count", "initial_epoch", "new_epoch",
    "a_cube_id", "b_cube_id", "guest_original_bytes_preserved",
    "old_epoch_rejected", "wrong_scope_rejected", "destroy_ack",
)


def _verified_native_proof(proof: object) -> dict:
    """Validate independently correlated public claims; never pass fake PG facts."""
    if not isinstance(proof, dict) or proof.get("outcome") != (
            "PASS_PHYSICAL_HATCHET_CUBE_SAME_RUN"):
        raise ValueError("Authoritative live B03 terminal proof absent")
    ids = ("run_id", "execution_id", "workflow_run_id", "a_cube_id", "b_cube_id")
    if any(not isinstance(proof.get(k), str) or not _ID.fullmatch(proof[k])
           for k in ids):
        raise ValueError("Correlated identity missing")
    if (proof["a_cube_id"] != proof["b_cube_id"]
            or type(proof.get("worker_a_pid")) is not int
            or type(proof.get("worker_b_pid")) is not int
            or proof["worker_a_pid"] <= 0 or proof["worker_b_pid"] <= 0
            or proof["worker_a_pid"] == proof["worker_b_pid"]
            or proof.get("worker_a_exit_code") != -9
            or proof.get("b_worker_role") != "worker-B"
            or type(proof.get("native_retry_count")) is not int
            or proof["native_retry_count"] < 1
            or proof.get("initial_epoch") != 7
            or proof.get("new_epoch") != 8
            or proof.get("guest_original_bytes_preserved") is not True
            or proof.get("old_epoch_rejected") is not True
            or proof.get("wrong_scope_rejected") is not True
            or proof.get("destroy_ack") != "RELEASED"):
        raise ValueError("Native OS/Cube/PG evidence does not meet the B03 gate")
    return {key: proof[key] for key in _PUBLIC_FIELDS}


def run_native_b03() -> dict:
    """Fixed privileged command, no browser-supplied command/arguments/paths."""
    if os.name != "posix":
        raise RuntimeError("Linux physical Worker environment required")
    for key in ("CUBE_API_URL", "CUBE_TEMPLATE_ID",
                "HARNESS_POC_DATABASE_URL", "HATCHET_POC_DATABASE_URL"):
        if not os.getenv(key):
            raise RuntimeError("Required trusted B03 environment unavailable")
    # Real worker logs are written by its own synthetic verifier. Do not keep
    # CLI stderr or upstream SDK credentials in an Inspector evidence record.
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as output:
        process = subprocess.Popen(
            [sys.executable, "-B", "-m",
             "poc.sandbox.verify_hatchet_cube_worker_takeover", "controller"],
            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            shell=False, start_new_session=True,
        )
        try:
            exit_code = process.wait(timeout=NATIVE_B03_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            # The verifier owns its own synthetic native Worker children.
            # Terminate the entire private verifier process group rather than
            # leaving an orphaned Worker that could mutate a Guest later.
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=15)
            raise RuntimeError("Native B03 deadline reached; reconcile provider before retry") from None
        if exit_code != 0:
            raise RuntimeError("Native B03 failed; inspect server-side operator log") from None
        output.seek(0)
        last_json = None
        for line in output:
            if line.startswith("{") and len(line) < 12000:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict) and item.get("outcome"):
                    last_json = item
    return _verified_native_proof(last_json)


class TrustedScenarioRunner:
    """One native privileged run at a time; no automatic retry on restart."""

    def __init__(self, *, token: str, evidence_dir: str | Path,
                 execute: Callable[[], dict] = run_native_b03):
        if (not isinstance(token, str) or len(token) < 32
                or not token.isascii() or not token.strip()):
            raise ValueError("Explicit >=32-character operator token is required")
        self._token = token
        self._dir = Path(evidence_dir).expanduser()
        self._dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self._dir.is_symlink():
            raise ValueError("Evidence directory cannot be a symbolic link")
        self._execute = execute
        self._lock = threading.Lock()
        self._running: str | None = None
        self._owner_lock_path = self._dir / ".active-native-run"

    def authorized(self, supplied: str | None) -> bool:
        return (isinstance(supplied, str)
                and supplied.isascii()
                and hmac.compare_digest(supplied, self._token))

    def _file(self, execution_id: str) -> Path:
        if not _ID.fullmatch(execution_id) or not execution_id.startswith("proof-"):
            raise KeyError(execution_id)
        return self._dir / (execution_id + ".json")

    def _record(self, item: dict) -> None:
        path = self._file(item["execution_id"])
        fd, tmp_name = tempfile.mkstemp(prefix=".evidence-", suffix=".tmp",
                                       dir=self._dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as writer:
                json.dump(item, writer, sort_keys=True, ensure_ascii=False)
                writer.flush()
                os.fsync(writer.fileno())
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def start(self) -> str:
        with self._lock:
            if self._running is not None:
                raise RuntimeError("Privileged B03 execution already running")
            # Cross-process lock also prevents blind retry if a server crashes
            # after an unknown external effect. Operator reconciliation is
            # required before an orphaned lock can be removed.
            try:
                fd = os.open(self._owner_lock_path,
                             os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                raise RuntimeError("Prior native execution unresolved") from None
            execution_id = "proof-" + uuid4().hex
            with os.fdopen(fd, "w", encoding="utf-8") as writer:
                writer.write(execution_id)
            self._running = execution_id
            try:
                self._record({"execution_id": execution_id,
                              "scenario_id": "worker-takeover",
                              "status": "RUNNING", "verified": False,
                              "evidence": None})
                thread = threading.Thread(target=self._run,
                                          args=(execution_id,),
                                          name="trusted-m5-native-verifier",
                                          daemon=True)
                thread.start()
            except Exception:
                self._running = None
                self._owner_lock_path.unlink(missing_ok=True)
                raise
        return execution_id

    def _run(self, execution_id: str) -> None:
        try:
            try:
                attestation = _verified_native_proof(self._execute())
                status = "PASSED"
                reason = None
            except ValueError:
                # A code-0 process with inconsistent facts is an unknown
                # external execution, not an invitation to retry it.
                status = "BLOCKED_UNKNOWN"
                reason = "NATIVE_EVIDENCE_INVALID_RECONCILIATION_REQUIRED"
                attestation = None
            except Exception:
                status = "BLOCKED_UNKNOWN"
                reason = "NATIVE_EXECUTION_UNCERTAIN_RECONCILIATION_REQUIRED"
                attestation = None
            self._record({
                "execution_id": execution_id, "scenario_id": "worker-takeover",
                "status": status, "verified": status == "PASSED",
                "evidence": attestation, "reason": reason,
            })
        finally:
            with self._lock:
                self._running = None
                # Unknown external outcomes must never silently unlock for
                # reexecution. Keep the lock and require manual reconciliation.
                try:
                    item = self.get(execution_id)
                    if item["status"] in ("PASSED", "FAILED"):
                        self._owner_lock_path.unlink(missing_ok=True)
                except (KeyError, OSError):
                    pass

    def get(self, execution_id: str) -> dict:
        path = self._file(execution_id)
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise KeyError(execution_id) from None
        if item.get("execution_id") != execution_id:
            raise KeyError(execution_id)
        if item.get("status") == "RUNNING" and execution_id != self._running:
            return dict(item, status="BLOCKED_UNKNOWN",
                        reason="NATIVE_EXECUTION_INTERRUPTED_RECONCILE",
                        verified=False, evidence=None)
        return item
