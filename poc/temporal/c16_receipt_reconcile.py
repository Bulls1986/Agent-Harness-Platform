"""C16 trusted Tool Receipt verifier: read-only HTTP reconciliation after UNKNOWN.

Never redispatch Tool, never rewrite immutable UNKNOWN Attempt/Execution.
External receipt status must be durable, exact lineage and single application.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit
import urllib.request
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
from platform_facts import FrozenTemporal,TemporalTaskFacts

class ReceiptReconciler:
    def __init__(self,dsn):
        self.dsn=dsn

    def initialize(self):
        TemporalTaskFacts(self.dsn).initialize()
        with psycopg.connect(self.dsn) as db:
            db.execute((Path(__file__).parent/"sql"/"005_receipt_reconciliation.sql").read_text())

    def reconcile(self,binding:FrozenTemporal,receipt_base:str):
        parsed=urlsplit(receipt_base)
        if parsed.hostname not in ("127.0.0.1","localhost") or parsed.scheme!="http":
            raise ValueError("C16 POC Tool receipt must be loopback")
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            snapshot=db.execute("""SELECT b.*,r.state AS run_state,
              a.state AS attempt_state,e.state AS execution_state,
              rec.state AS reconciliation_state,o.revoked_at
              FROM poc_c_temporal_bindings b
              JOIN poc_runs r ON r.run_id=b.run_id
              JOIN poc_attempts a ON a.attempt_id=b.attempt_id
              JOIN poc_executions e ON e.execution_id=b.execution_id
              JOIN poc_reconciliations rec ON rec.execution_id=b.execution_id
              JOIN poc_execution_ownership o ON o.execution_id=b.execution_id
              WHERE b.execution_id=%s""",(binding.execution_id,)).fetchone()
        if not snapshot or any(snapshot[field]!=getattr(binding,field) for field in
                ("run_id","step_id","attempt_id","execution_id",
                 "native_workflow_id","frozen_workflow_version","frozen_runtime_version")):
            raise ValueError("C16 forged native or platform binding")
        if (snapshot["run_state"]!="RUNNING" or
            snapshot["attempt_state"]!="UNKNOWN" or
            snapshot["execution_state"]!="UNKNOWN" or
            snapshot["revoked_at"] is None):
            raise ValueError("C16 receipt not allowed except fenced UNKNOWN")
        if snapshot["reconciliation_state"]=="RESOLVED":
            with psycopg.connect(self.dsn,row_factory=dict_row) as db:
                old=db.execute("SELECT receipt_id FROM poc_c16_reconciled_receipts WHERE execution_id=%s",
                               (binding.execution_id,)).fetchone()
            return {"state":"RESOLVED","receipt_id":old["receipt_id"],"idempotent":True}
        if snapshot["reconciliation_state"]!="PENDING":
            raise ValueError("C16 cannot resolve manual/unknown state")
        url=receipt_base.rstrip("/")+"/receipt/"+binding.execution_id
        with urllib.request.urlopen(url,timeout=6) as response:
            receipt=json.loads(response.read(8192))
        rows=receipt.get("receipts",[])
        # An external Tool is truly NON_RETRYABLE. Multiple applied effects
        # require manual correction; NEVER call POST again from reconciler.
        if (receipt.get("execution_id")!=binding.execution_id or
            receipt.get("effect_count")!=1 or len(rows)!=1 or
            rows[0].get("execution_id")!=binding.execution_id or
            rows[0].get("attempt_id")!=binding.attempt_id or
            rows[0].get("effect_delta")!=1 or
            not str(rows[0].get("receipt_id","")).startswith("receipt-")):
            raise ValueError("C16 ambiguous/forged/repeated external side effect")
        proof=json.dumps(receipt,sort_keys=True,separators=(",",":")).encode()
        digest=sha256(proof).hexdigest()
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            lock=db.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                            (binding.run_id,)).fetchone()
            if lock["state"]!="RUNNING":raise ValueError("Run not active")
            state=db.execute("SELECT state FROM poc_reconciliations WHERE execution_id=%s FOR UPDATE",
                             (binding.execution_id,)).fetchone()
            if state["state"]=="RESOLVED":
                return {"state":"RESOLVED","receipt_id":rows[0]["receipt_id"],"idempotent":True}
            if state["state"]!="PENDING":raise ValueError("Reconciliation no longer pending")
            db.execute("""INSERT INTO poc_c16_reconciled_receipts
                (execution_id,run_id,attempt_id,receipt_id,external_ref,
                 receipt_sha256,external_effect_count)
                VALUES(%s,%s,%s,%s,%s,%s,1)""",
                (binding.execution_id,binding.run_id,binding.attempt_id,
                 rows[0]["receipt_id"],
                 "receipt://"+binding.execution_id+"/"+rows[0]["receipt_id"],digest))
            db.execute("UPDATE poc_reconciliations SET state='RESOLVED' WHERE execution_id=%s",
                       (binding.execution_id,))
            seq=db.execute("SELECT max(seq)+1 AS next_seq FROM poc_events WHERE run_id=%s",
                           (binding.run_id,)).fetchone()["next_seq"]
            db.execute("""INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                 VALUES(%s,%s,%s,'execution.reconciled',%s::jsonb)""",
                 ("event-"+uuid4().hex,binding.run_id,seq,
                  json.dumps({"execution_id":binding.execution_id,
                              "attempt_id":binding.attempt_id,"status":"APPLIED",
                              "receipt_ref":"receipt://"+binding.execution_id+"/"+rows[0]["receipt_id"]})))
        return {"state":"RESOLVED","receipt_id":rows[0]["receipt_id"],
                "idempotent":False,"external_effect_count":1,
                "original_attempt_state":"UNKNOWN"}
