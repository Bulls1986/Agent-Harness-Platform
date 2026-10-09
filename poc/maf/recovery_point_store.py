"""G2/G6 platform-owned immutable RecoveryPoint reference records.

A RecoveryPoint is a *candidate*, not a checkpoint or a successful resume.
Actual checkpoint verification/workspace restore/Runtime resume belong to
their respective Provider Adapters. Never deserialize framework internals.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

import psycopg
from psycopg.rows import dict_row

from task_ledger import TaskFactConflict, _id


@dataclass(frozen=True)
class RecoveryPointRefs:
    run_id: str
    step_id: str
    attempt_id: str
    runtime_type: str
    runtime_checkpoint_ref: str | None = None
    workspace_state_ref: str | None = None
    repository_revision_set: Mapping[str, str] | None = None
    environment_fingerprint: str | None = None
    sandbox_snapshot_ref: str | None = None
    provider_fingerprint: str | None = None


@dataclass(frozen=True)
class RecoveryPointChoice:
    outcome: str
    recovery_point_id: str | None = None
    runtime_checkpoint_ref: str | None = None
    workspace_state_ref: str | None = None
    sandbox_snapshot_ref: str | None = None


class RecoveryPointStore:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("Platform PostgreSQL DSN required")
        self.dsn = dsn

    def record(self, refs: RecoveryPointRefs) -> str:
        """Persist only refs with verified Harness lineage, not actual snapshots."""
        if not all((refs.run_id,refs.step_id,refs.attempt_id,refs.runtime_type)):
            raise ValueError("Run/Step/Attempt/Runtime identity required")
        if not any((refs.runtime_checkpoint_ref, refs.workspace_state_ref,
                    refs.sandbox_snapshot_ref)):
            raise ValueError("At least one external recovery reference required")
        if not refs.environment_fingerprint:
            raise ValueError("Frozen environment fingerprint required for safe recovery selection")
        if refs.runtime_checkpoint_ref and not refs.provider_fingerprint:
            raise ValueError("Native checkpoint reference requires provider fingerprint")
        if refs.repository_revision_set is not None:
            if not isinstance(refs.repository_revision_set, Mapping) or not refs.repository_revision_set:
                raise ValueError("Repository revision set must be nonempty mapping")
            if not all(isinstance(k,str) and k and isinstance(v,str) and v
                       for k,v in refs.repository_revision_set.items()):
                raise ValueError("Repository revision set keys and revisions must be strings")
        if refs.sandbox_snapshot_ref and not refs.workspace_state_ref:
            # A sandbox snapshot is optional acceleration, never the sole
            # guarantee of restoring the workspace or task.
            raise TaskFactConflict("Sandbox snapshot requires workspace state reference")
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT state,runtime_type FROM poc_runs WHERE run_id=%s FOR UPDATE",
                    (refs.run_id,))
                run = cur.fetchone()
                if run is None or run["state"] != "RUNNING":
                    raise TaskFactConflict("RecoveryPoint only recorded in active Run")
                if run["runtime_type"] != refs.runtime_type:
                    raise TaskFactConflict("RecoveryPoint runtime differs from frozen Run runtime")
                cur.execute(
                    """SELECT a.state,p.run_id
                       FROM poc_attempts a
                       JOIN poc_steps s ON s.step_id=a.step_id
                       JOIN poc_plans p ON p.plan_id=s.plan_id
                       WHERE a.attempt_id=%s AND s.step_id=%s FOR UPDATE OF a""",
                    (refs.attempt_id,refs.step_id))
                attempt = cur.fetchone()
                if attempt is None or attempt["run_id"] != refs.run_id \
                   or attempt["state"] != "RUNNING":
                    raise TaskFactConflict("RecoveryPoint Attempt is inactive or wrong lineage")
                point_id = _id("recovery_point")
                cur.execute(
                    """INSERT INTO poc_recovery_points
                       (recovery_point_id,run_id,step_id,attempt_id,runtime_type,
                        runtime_checkpoint_ref,workspace_state_ref,repository_revision_set,
                        environment_fingerprint,sandbox_snapshot_ref,provider_fingerprint)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
                    (point_id,refs.run_id,refs.step_id,refs.attempt_id,refs.runtime_type,
                     refs.runtime_checkpoint_ref,refs.workspace_state_ref,
                     json.dumps(refs.repository_revision_set) if refs.repository_revision_set else None,
                     refs.environment_fingerprint,refs.sandbox_snapshot_ref,
                     refs.provider_fingerprint))
                return point_id

    def choose(self, *, run_id: str, attempt_id: str, runtime_type: str,
               provider_fingerprint: str | None,
               environment_fingerprint: str | None,
               checkpoint_capable: bool, workspace_capable: bool) -> RecoveryPointChoice:
        """Return a bounded candidate; no implicit provider resume or fallback retry.

        A mismatch is fail-closed, not permission to select an older point:
        older checkpoints may not represent latest external side effects.
        """
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                """SELECT recovery_point_id,run_id,runtime_type,runtime_checkpoint_ref,
                          workspace_state_ref,sandbox_snapshot_ref,
                          environment_fingerprint,provider_fingerprint
                   FROM poc_recovery_points
                   WHERE run_id=%s AND attempt_id=%s
                   ORDER BY created_at DESC,recovery_point_id DESC LIMIT 1""",
                (run_id,attempt_id)).fetchone()
        if row is None:
            return RecoveryPointChoice("RECOVERY_POINT_UNAVAILABLE")
        if row["runtime_type"] != runtime_type or \
           row["provider_fingerprint"] != provider_fingerprint or \
           row["environment_fingerprint"] != environment_fingerprint:
            return RecoveryPointChoice("RECOVERY_INCOMPATIBLE")
        if row["workspace_state_ref"] and not workspace_capable:
            return RecoveryPointChoice("RECOVERY_UNSUPPORTED_WORKSPACE")
        if row["runtime_checkpoint_ref"] and not checkpoint_capable:
            return RecoveryPointChoice("RECOVERY_UNSUPPORTED_RUNTIME")
        if not row["runtime_checkpoint_ref"]:
            # Workspace references alone cannot prove a same-Attempt resume.
            return RecoveryPointChoice("STEP_BOUNDARY_REQUIRES_SEPARATE_DECISION")
        return RecoveryPointChoice(
            "CANDIDATE_REQUIRES_PROVIDER_VERIFICATION",
            recovery_point_id=row["recovery_point_id"],
            runtime_checkpoint_ref=row["runtime_checkpoint_ref"],
            workspace_state_ref=row["workspace_state_ref"],
            sandbox_snapshot_ref=row["sandbox_snapshot_ref"],
        )
