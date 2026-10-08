"""C11 Harness PostgreSQL Artifact/Evidence identity, immutable lineage and pinning.

No payload bytes in this module; S3 Provider owns physical objects. The
independent verification Activity proves physical digest then persists facts.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
import json
import psycopg
from psycopg.rows import dict_row
from platform_facts import TemporalTaskFacts


def uid(prefix:str)->str:
    return prefix+"-"+uuid4().hex


PROVIDERS=("docker-oneshot","docker-session")


@dataclass(frozen=True)
class C11Run:
    run_id:str
    plan_id:str
    native_workflow_id:str
    frozen_image_digest:str
    stages:tuple[dict,...]
    frozen_workflow_version:str="temporal-c11-artifacts-v1"

    @classmethod
    def build(cls,image_digest:str):
        return cls(uid("run"),uid("plan"),uid("temporal-c11"),image_digest,
                   tuple({"provider":p,"ordinal":i,"step_id":uid("step"),
                          "attempt_id":uid("attempt"),"execution_id":uid("execution")}
                         for i,p in enumerate(PROVIDERS,1)))

    def request(self)->dict:
        return {"run_id":self.run_id,"native_workflow_id":self.native_workflow_id,
                "frozen_workflow_version":self.frozen_workflow_version,
                "frozen_image_digest":self.frozen_image_digest,
                "stages":list(self.stages)}


class C11Facts:
    def __init__(self,dsn:str):
        if not dsn:raise ValueError("Harness PostgreSQL DSN required")
        self.dsn=dsn

    def initialize(self):
        TemporalTaskFacts(self.dsn).initialize()
        with psycopg.connect(self.dsn) as db:
            db.execute((Path(__file__).resolve().parent/"sql"/
                        "003_artifact_metadata.sql").read_text(encoding="utf-8"))

    @staticmethod
    def event(db,run_id:str,kind:str,data:dict):
        db.execute("""INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
          VALUES(%s,%s,(SELECT coalesce(max(seq),0)+1 FROM poc_events WHERE run_id=%s),
                 %s,%s::jsonb)""",(uid("event"),run_id,run_id,kind,json.dumps(data)))

    def prepare(self,run:C11Run):
        if (len(run.stages)!=2 or tuple(s["provider"] for s in run.stages)!=PROVIDERS
                or not run.frozen_image_digest.startswith("sha256:")):
            raise ValueError("Wrong C11 sandbox provider/image freeze")
        with psycopg.connect(self.dsn) as db:
            conversation,turn=uid("conversation"),uid("turn")
            db.execute("INSERT INTO poc_conversations(conversation_id) VALUES(%s)",(conversation,))
            db.execute("INSERT INTO poc_turns(turn_id,conversation_id) VALUES(%s,%s)",
                       (turn,conversation))
            db.execute("""INSERT INTO poc_runs(run_id,turn_id,initiator_principal_id,
                     runtime_type,recipe_version,state)
                     VALUES(%s,%s,'poc-c-internal','temporal','c11-sandbox-v1','RUNNING')""",
                       (run.run_id,turn))
            db.execute("INSERT INTO poc_runtime_bindings(run_id,runtime_type) VALUES(%s,'temporal')",
                       (run.run_id,))
            db.execute("INSERT INTO poc_plans(plan_id,run_id,version,reason) "
                       "VALUES(%s,%s,1,'sandbox SPI + object store smoke')",
                       (run.plan_id,run.run_id))
            db.execute("""INSERT INTO poc_c11_runs
                  (run_id,native_workflow_id,frozen_workflow_version,frozen_image_digest)
                  VALUES(%s,%s,%s,%s)""",
                       (run.run_id,run.native_workflow_id,run.frozen_workflow_version,
                        run.frozen_image_digest))
            for stage in run.stages:
                db.execute("INSERT INTO poc_steps(step_id,plan_id,ordinal,intent) "
                           "VALUES(%s,%s,%s,'controlled isolated sandbox artifact')",
                           (stage["step_id"],run.plan_id,stage["ordinal"]))
                db.execute("INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state) "
                           "VALUES(%s,%s,1,'RUNNING')",(stage["attempt_id"],stage["step_id"]))
                db.execute("""INSERT INTO poc_executions
                        (execution_id,attempt_id,side_effect_class,state)
                        VALUES(%s,%s,'IDEMPOTENT','RUNNING')""",
                           (stage["execution_id"],stage["attempt_id"]))
                db.execute("""INSERT INTO poc_c11_sandbox_stages
                        (attempt_id,run_id,step_id,execution_id,ordinal,provider)
                        VALUES(%s,%s,%s,%s,%s,%s)""",
                           (stage["attempt_id"],run.run_id,stage["step_id"],
                            stage["execution_id"],stage["ordinal"],stage["provider"]))
            self.event(db,run.run_id,"run.started",{"provider_count":2})

    def frozen(self,request:dict,stage:dict):
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            row=db.execute("""SELECT b.native_workflow_id,b.frozen_workflow_version,
                      b.frozen_image_digest,r.state AS run_state,
                      a.state AS attempt_state,e.state AS execution_state,
                      st.step_id,st.execution_id,st.ordinal,st.provider
                 FROM poc_c11_runs b
                 JOIN poc_c11_sandbox_stages st ON st.run_id=b.run_id
                 JOIN poc_runs r ON r.run_id=b.run_id
                 JOIN poc_attempts a ON a.attempt_id=st.attempt_id
                 JOIN poc_executions e ON e.execution_id=st.execution_id
                 WHERE b.run_id=%s AND st.attempt_id=%s""",
                       (request["run_id"],stage["attempt_id"])).fetchone()
        frozen={k:request[k] for k in
                ("native_workflow_id","frozen_workflow_version","frozen_image_digest")}
        frozen.update({k:stage[k] for k in
                       ("step_id","execution_id","ordinal","provider")})
        if not row or any(row[k]!=v for k,v in frozen.items()):
            raise ValueError("C11 frozen Run/Provider/Execution mismatch")
        if any(row[k]!="RUNNING" for k in ("run_state","attempt_state","execution_state")):
            raise ValueError("C11 Sandbox dispatch to inactive stage")

    def record_artifact(self,request:dict,stage:dict,digest:str,size:int,ref:str)->str:
        self.frozen(request,stage)
        if size<131072 or not ref.startswith("s3://"):
            raise ValueError("C11 expected real object store large artifact")
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            row=db.execute("""SELECT payload_id,sha256_hex,size_bytes,storage_ref
                  FROM poc_c11_payload_metadata WHERE execution_id=%s AND kind='ARTIFACT'""",
                  (stage["execution_id"],)).fetchone()
            if row:
                if (row["sha256_hex"],row["size_bytes"],row["storage_ref"])!=(digest,size,ref):
                    raise ValueError("Artifact re-dispatch content mismatch")
                return row["payload_id"]
            pid=uid("artifact")
            db.execute("""INSERT INTO poc_c11_payload_metadata
                     (payload_id,run_id,step_id,attempt_id,execution_id,kind,
                      media_type,sha256_hex,size_bytes,storage_ref)
                     VALUES(%s,%s,%s,%s,%s,'ARTIFACT','application/octet-stream',%s,%s,%s)""",
                       (pid,request["run_id"],stage["step_id"],stage["attempt_id"],
                        stage["execution_id"],digest,size,ref))
            self.event(db,request["run_id"],"artifact.created",
                       {"artifact_id":pid,"step_id":stage["step_id"],
                        "attempt_id":stage["attempt_id"],"execution_id":stage["execution_id"],
                        "storage_ref":ref,"sha256":digest,"size_bytes":size})
            return pid

    def artifact(self,request:dict,stage:dict)->dict:
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            row=db.execute("""SELECT payload_id,sha256_hex,size_bytes,storage_ref,payload_status
              FROM poc_c11_payload_metadata WHERE run_id=%s AND execution_id=%s
              AND kind='ARTIFACT'""",
              (request["run_id"],stage["execution_id"])).fetchone()
        if not row or row["payload_status"]!="AVAILABLE":
            raise ValueError("C11 Artifact missing or purged")
        return dict(row)

    def verification(self,request:dict,stage:dict,artifact_id:str,evidence_ref:str,
                     evidence_digest:str,evidence_size:int)->str:
        self.frozen(request,stage)
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            existing=db.execute("""SELECT payload_id,storage_ref
              FROM poc_c11_payload_metadata WHERE execution_id=%s AND kind='EVIDENCE'""",
              (stage["execution_id"],)).fetchone()
            if existing:
                if existing["storage_ref"]!=evidence_ref:
                    raise ValueError("C11 evidence collision")
                return existing["payload_id"]
            obj=db.execute("""SELECT payload_id FROM poc_c11_payload_metadata
                    WHERE execution_id=%s AND kind='ARTIFACT'""",
                           (stage["execution_id"],)).fetchone()
            if not obj or obj["payload_id"]!=artifact_id:
                raise ValueError("C11 Artifact ID mismatch")
            pid=uid("evidence")
            db.execute("""INSERT INTO poc_c11_payload_metadata
                     (payload_id,run_id,step_id,attempt_id,execution_id,kind,
                      media_type,sha256_hex,size_bytes,storage_ref)
                     VALUES(%s,%s,%s,%s,%s,'EVIDENCE','application/json',%s,%s,%s)""",
                       (pid,request["run_id"],stage["step_id"],stage["attempt_id"],
                        stage["execution_id"],evidence_digest,evidence_size,evidence_ref))
            db.execute("""INSERT INTO poc_verifications
                    (verification_id,execution_id,passed,evidence_ref)
                    VALUES(%s,%s,TRUE,%s)""",(uid("verify"),stage["execution_id"],pid))
            db.execute("UPDATE poc_attempts SET state='SUCCEEDED' WHERE attempt_id=%s",
                       (stage["attempt_id"],))
            db.execute("UPDATE poc_executions SET state='SUCCEEDED' WHERE execution_id=%s",
                       (stage["execution_id"],))
            self.event(db,request["run_id"],"verification.passed",
                       {"artifact_id":artifact_id,"evidence_id":pid,
                        "execution_id":stage["execution_id"],"passed":True})
            return pid

    def complete(self,run_id:str):
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            r=db.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                         (run_id,)).fetchone()
            if not r or r["state"]!="RUNNING":
                raise ValueError("Run inactive or already completed")
            stages=db.execute("""SELECT a.state FROM poc_c11_sandbox_stages s
                       JOIN poc_attempts a ON a.attempt_id=s.attempt_id
                       WHERE s.run_id=%s ORDER BY s.ordinal""",(run_id,)).fetchall()
            if len(stages)!=2 or any(x["state"]!="SUCCEEDED" for x in stages):
                raise ValueError("Both sandbox providers need independent verification")
            db.execute("UPDATE poc_runs SET state='COMPLETED',terminal_at=now() "
                       "WHERE run_id=%s",(run_id,))
            self.event(db,run_id,"run.terminal",{"status":"COMPLETED"})

    def rows(self,run_id:str)->list[dict]:
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            return [dict(r) for r in db.execute("""SELECT * FROM poc_c11_payload_metadata
                          WHERE run_id=%s ORDER BY created_at,payload_id""",(run_id,))]

    def release_pin(self,payload_id:str):
        with psycopg.connect(self.dsn) as db:
            db.execute("""UPDATE poc_c11_payload_metadata
                   SET recovery_pinned=FALSE WHERE payload_id=%s
                   AND payload_status='AVAILABLE'""",(payload_id,))

    def purge(self,payload_id:str):
        with psycopg.connect(self.dsn) as db:
            db.execute("""UPDATE poc_c11_payload_metadata
                   SET payload_status='PURGED',storage_ref=NULL,purged_at=now()
                   WHERE payload_id=%s""",(payload_id,))
