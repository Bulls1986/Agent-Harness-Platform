"""POC-A15: S3-compatible external payloads with platform-owned references.

No local OSS engine, no payload bytes in PostgreSQL. GC never purges a
recoverable Run's required payload. Provider operations are not a distributed
transaction with PostgreSQL: PURGE_PENDING records an interrupted deletion.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from task_ledger import TaskFactConflict


@dataclass(frozen=True)
class PayloadIdentity:
    run_id: str
    step_id: str
    attempt_id: str
    execution_id: str
    kind: str
    media_type: str
    retention_policy_ref: str


@dataclass(frozen=True)
class PayloadRef:
    payload_id: str
    kind: str
    content_sha256: str
    byte_size: int


class PayloadIntegrityError(RuntimeError):
    pass


class PayloadRefStore:
    def __init__(self, dsn: str, *, s3, bucket: str):
        if not dsn or not bucket:
            raise ValueError("PostgreSQL DSN and S3 bucket required")
        self.dsn, self.s3, self.bucket = dsn, s3, bucket

    def _lineage(self, cur, ident: PayloadIdentity):
        cur.execute(
            """SELECT r.state
               FROM poc_executions e
               JOIN poc_attempts a ON a.attempt_id=e.attempt_id
               JOIN poc_steps s ON s.step_id=a.step_id
               JOIN poc_plans p ON p.plan_id=s.plan_id
               JOIN poc_runs r ON r.run_id=p.run_id
               WHERE e.execution_id=%s AND a.attempt_id=%s
                 AND s.step_id=%s AND r.run_id=%s
               FOR UPDATE OF r""",
            (ident.execution_id,ident.attempt_id,ident.step_id,ident.run_id),
        )
        row=cur.fetchone()
        if row is None or row["state"]!="RUNNING":
            raise TaskFactConflict("Payload must belong to an active Harness Run/Execution")

    def put(self, ident: PayloadIdentity, payload: bytes) -> PayloadRef:
        if not all(vars(ident).values()) or ident.kind not in ("ARTIFACT","EVIDENCE","WORKSPACE"):
            raise ValueError("Complete payload identity and kind required")
        if not isinstance(payload,bytes):
            raise TypeError("Payload must be bytes; never put provider-private object structures")
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                self._lineage(cur,ident)
        payload_id="payload-"+uuid4().hex
        key="poc-a/"+uuid4().hex
        digest=hashlib.sha256(payload).hexdigest()
        # External put may succeed but PG commit may fail. Clean up the orphan
        # in the error path, never claim a cross-system atomic transaction.
        self.s3.put_object(Bucket=self.bucket,Key=key,Body=payload,
                           ContentType=ident.media_type)
        try:
            with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    self._lineage(cur,ident)
                    cur.execute(
                        """INSERT INTO poc_payload_refs
                           (payload_id,run_id,step_id,attempt_id,execution_id,
                            kind,media_type,content_sha256,byte_size,object_key,
                            retention_policy_ref)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (payload_id,ident.run_id,ident.step_id,ident.attempt_id,
                         ident.execution_id,ident.kind,ident.media_type,digest,
                         len(payload),key,ident.retention_policy_ref),
                    )
        except Exception:
            try:
                self.s3.delete_object(Bucket=self.bucket,Key=key)
            except Exception:
                pass
            raise
        return PayloadRef(payload_id,ident.kind,digest,len(payload))

    def metadata(self, payload_id: str) -> dict:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row=conn.execute(
                "SELECT * FROM poc_payload_refs WHERE payload_id=%s",
                (payload_id,),
            ).fetchone()
        if row is None:
            raise KeyError(payload_id)
        return dict(row)

    def get(self, payload_id: str) -> bytes:
        meta=self.metadata(payload_id)
        if meta["payload_status"]!="AVAILABLE" or not meta["object_key"]:
            raise PayloadIntegrityError("Payload unavailable or purged")
        obj=self.s3.get_object(Bucket=self.bucket,Key=meta["object_key"])
        try:
            content=obj["Body"].read()
        finally:
            obj["Body"].close()
        if (len(content)!=meta["byte_size"] or
            hashlib.sha256(content).hexdigest()!=meta["content_sha256"]):
            raise PayloadIntegrityError("External object digest or size mismatch")
        return content

    def pin_to_recovery_point(self, payload_id: str, recovery_point_id: str)->None:
        """Pin Artifact/Evidence/Workspace when referenced by a live RP."""
        with psycopg.connect(self.dsn,row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT p.run_id,p.payload_status,p.kind,
                              rp.run_id AS point_run,r.state
                       FROM poc_payload_refs p
                       JOIN poc_recovery_points rp ON rp.recovery_point_id=%s
                       JOIN poc_runs r ON r.run_id=rp.run_id
                       WHERE p.payload_id=%s FOR UPDATE OF p""",
                    (recovery_point_id,payload_id),
                )
                row=cur.fetchone()
                if not row or row["run_id"]!=row["point_run"] or \
                   row["state"]!="RUNNING" or row["payload_status"]!="AVAILABLE":
                    raise TaskFactConflict("RecoveryPoint/payload active lineage mismatch")
                cur.execute(
                    """INSERT INTO poc_payload_recovery_pins(payload_id,recovery_point_id)
                       VALUES (%s,%s) ON CONFLICT DO NOTHING""",
                    (payload_id,recovery_point_id),
                )

    def restore_workspace_file(self,payload_id:str,root:Path,relative_path:str)->Path:
        meta=self.metadata(payload_id)
        if meta["kind"]!="WORKSPACE":
            raise TaskFactConflict("Only a Workspace payload can restore a Workspace file")
        relative=Path(relative_path)
        if (not relative_path or relative.is_absolute()
            or any(part in ("..",".") for part in relative.parts)
            or relative.drive):
            raise ValueError("Invalid workspace-relative path")
        root=Path(root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Workspace root must already exist")
        target=root/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.parent.resolve().is_relative_to(root):
            raise ValueError("Workspace path escapes authorized root")
        if target.is_symlink():
            raise ValueError("Workspace destination may not be symlink")
        content=self.get(payload_id)  # digest check before writing any file
        descriptor,tmp=tempfile.mkstemp(dir=target.parent,prefix=".poc-restore-")
        try:
            with os.fdopen(descriptor,"wb") as out:
                out.write(content)
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp,target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return target

    def purge(self,payload_id:str)->str:
        """Fail-closed GC; keep immutable metadata/tombstone when bytes are gone."""
        with psycopg.connect(self.dsn,row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT p.object_key,p.payload_status,r.state
                       FROM poc_payload_refs p
                       JOIN poc_runs r ON r.run_id=p.run_id
                       WHERE p.payload_id=%s FOR UPDATE OF p,r""",
                    (payload_id,),
                )
                row=cur.fetchone()
                if row is None:
                    raise KeyError(payload_id)
                if row["payload_status"]=="PURGED":
                    return "ALREADY_PURGED"
                if row["state"] not in ("COMPLETED","FAILED","ABORTED","CANCELLED"):
                    return "PINNED_RUN_RECOVERABLE"
                # A different active Run can hold a reference to this object.
                cur.execute(
                    """SELECT 1 FROM poc_recovery_points rp
                       JOIN poc_runs r ON r.run_id=rp.run_id
                       LEFT JOIN poc_payload_recovery_pins pin
                         ON pin.recovery_point_id=rp.recovery_point_id
                       WHERE r.state NOT IN ('COMPLETED','FAILED','ABORTED','CANCELLED')
                         AND (rp.workspace_state_ref=%s OR pin.payload_id=%s)
                       LIMIT 1""",
                    (payload_id,payload_id),
                )
                if cur.fetchone():
                    return "PINNED_ACTIVE_RECOVERY_POINT"
                cur.execute(
                    """UPDATE poc_payload_refs SET payload_status='PURGE_PENDING'
                       WHERE payload_id=%s AND payload_status='AVAILABLE'""",
                    (payload_id,),
                )
                key=row["object_key"]
        # Interrupted S3 deletion keeps PURGE_PENDING for a safe retry.
        self.s3.delete_object(Bucket=self.bucket,Key=key)
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """UPDATE poc_payload_refs SET payload_status='PURGED',
                   object_key=NULL,purged_at=now()
                   WHERE payload_id=%s AND payload_status='PURGE_PENDING'""",
                (payload_id,),
            )
        return "PURGED_TOMBSTONE_RETAINED"
