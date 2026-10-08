"""C15 G3: Harness PostgreSQL is the single source for Run/Events/Token SSE.

Native Temporal History receives only a digest + character count, never
provider token payload. No framework-internal SDK/scheduler duplication.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import json
import psycopg
from psycopg.rows import dict_row

from platform_facts import TemporalTaskFacts

VERSION="temporal-c15-g3-v1"
QUEUE="poc-c15-g3-v1"
TERMINAL={"COMPLETED","FAILED","CANCELLED","ABORTED"}

def uid(prefix):
    return prefix+"-"+uuid4().hex

class LiveFacts:
    def __init__(self,dsn):
        if not dsn:raise ValueError("Harness DB required")
        self.dsn=dsn

    def initialize(self):
        TemporalTaskFacts(self.dsn).initialize()
        with psycopg.connect(self.dsn) as db:
            db.execute((Path(__file__).parent/"sql"/"004_live_protocol.sql").read_text())

    def event(self,db,run,kind,payload):
        row=db.execute("SELECT COALESCE(MAX(seq),0)+1 AS seq FROM poc_events WHERE run_id=%s",
                       (run,)).fetchone()
        db.execute("""INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
            VALUES(%s,%s,%s,%s,%s::jsonb)""",
                   (uid("event"),run,row["seq"],kind,json.dumps(payload)))

    def prepare(self,prompt,model):
        if not isinstance(prompt,str) or not 1<=len(prompt)<=500 or not prompt.strip():
            raise ValueError("Bounded nonblank prompt required")
        if not isinstance(model,str) or not model or len(model)>100:
            raise ValueError("Missing/invalid model")
        ids={name:uid(name) for name in
             ("run","conversation","turn","plan","step","attempt","execution")}
        ids["native_workflow_id"]=uid("native-g3")
        ids["frozen_workflow_version"]=VERSION
        ids["model"]=model
        ids["prompt"]=prompt
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            db.execute("INSERT INTO poc_conversations(conversation_id) VALUES(%s)",
                       (ids["conversation"],))
            db.execute("INSERT INTO poc_turns(turn_id,conversation_id) VALUES(%s,%s)",
                       (ids["turn"],ids["conversation"]))
            db.execute("""INSERT INTO poc_runs(run_id,turn_id,initiator_principal_id,
                runtime_type,recipe_version,state)
                VALUES(%s,%s,'poc-c-internal','temporal',%s,'RUNNING')""",
                       (ids["run"],ids["turn"],VERSION))
            db.execute("INSERT INTO poc_runtime_bindings(run_id,runtime_type) VALUES(%s,'temporal')",(ids["run"],))
            db.execute("INSERT INTO poc_plans(plan_id,run_id,version,reason) VALUES(%s,%s,1,'real model streaming')",
                       (ids["plan"],ids["run"]))
            db.execute("INSERT INTO poc_steps(step_id,plan_id,ordinal,intent) VALUES(%s,%s,1,'bounded model response')",
                       (ids["step"],ids["plan"]))
            db.execute("INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state) VALUES(%s,%s,1,'RUNNING')",
                       (ids["attempt"],ids["step"]))
            db.execute("INSERT INTO poc_executions(execution_id,attempt_id,side_effect_class,state) VALUES(%s,%s,'PURE','RUNNING')",
                       (ids["execution"],ids["attempt"]))
            db.execute("""INSERT INTO poc_c15_runs(run_id,native_workflow_id,model,
                frozen_workflow_version,prompt,step_id,attempt_id,execution_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                       tuple(ids[x] for x in ("run","native_workflow_id","model","frozen_workflow_version",
                                              "prompt","step","attempt","execution")))
            self.event(db,ids["run"],"run.started",{"step_id":ids["step"],"attempt_id":ids["attempt"],"execution_id":ids["execution"]})
            self.event(db,ids["run"],"plan.created",{"step_id":ids["step"],"version":1})

            db.execute("""INSERT INTO poc_recovery_points(recovery_point_id,run_id,step_id,
                 attempt_id,runtime_checkpoint_ref) VALUES(%s,%s,%s,%s,%s)""",
                 (uid("recovery"),ids["run"],ids["step"],ids["attempt"],
                  "temporal-workflow-id://"+ids["native_workflow_id"]))
        return ids

    def require(self,req,*,active=True):
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            row=db.execute("""SELECT b.*,r.state FROM poc_c15_runs b
                JOIN poc_runs r ON r.run_id=b.run_id WHERE b.run_id=%s""",
                (req["run"],)).fetchone()
        if not row or any(row[name]!=req[name] for name in
            ("native_workflow_id","model","frozen_workflow_version","prompt")):
            raise ValueError("Frozen G3 Run/Workflow/Model mismatch")
        if any(row[k]!=req[k2] for k,k2 in
               (("step_id","step"),("attempt_id","attempt"),("execution_id","execution"))):
            raise ValueError("Frozen G3 Step/Attempt/Execution mismatch")
        if active and row["state"]!="RUNNING":
            raise ValueError("G3 Run not active")
        return row

    def ack(self,run,expected):
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            db.execute("""UPDATE poc_c15_runs SET start_state='ACKED'
                WHERE run_id=%s AND native_workflow_id=%s""",(run,expected))


    def mark_start_uncertain(self,run):
        """Native Start request may be accepted even when its ACK is lost."""
        with psycopg.connect(self.dsn) as db:
            db.execute("""UPDATE poc_c15_runs SET start_state='START_UNKNOWN'
                         WHERE run_id=%s AND start_state='PREPARED'""",(run,))

    def recovery_reference(self,run):
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            return db.execute("""SELECT p.recovery_point_id,p.run_id,p.step_id,
                 p.attempt_id,p.runtime_checkpoint_ref
                 FROM poc_recovery_points p JOIN poc_c15_runs b ON b.run_id=p.run_id
                 WHERE p.run_id=%s""",(run,)).fetchone()

    def append(self,req,kind,data):
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            state=db.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                             (req["run"],)).fetchone()
            self.require(req,active=False)
            if state["state"]!="RUNNING":
                return False
            allowed={"activity.started","response.output_text.delta","response.output_text.done"}
            if kind not in allowed:raise ValueError("Unknown G3 event")
            self.event(db,req["run"],kind,data)
            return True

    def verify(self,req,digest,count):
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            r=db.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                         (req["run"],)).fetchone()
            if r["state"]=="CANCELLED":return False
            if r["state"]!="RUNNING":raise ValueError("Terminal/invalid Run")
            rows=db.execute("""SELECT event_type,payload FROM poc_events
                WHERE run_id=%s AND event_type IN ('response.output_text.delta',
                'response.output_text.done') ORDER BY seq""",(req["run"],)).fetchall()
            text="".join(e["payload"]["delta"] for e in rows if e["event_type"]=="response.output_text.delta")
            done=[e for e in rows if e["event_type"]=="response.output_text.done"]
            passed=(len(done)==1 and len(text)==count and len(text)>0 and
                    sha256(text.encode()).hexdigest()==digest and
                    done[0]["payload"]["sha256"]==digest)
            if not passed:raise ValueError("Independent token/PG digest validation failed")
            db.execute("UPDATE poc_executions SET state='SUCCEEDED' WHERE execution_id=%s",(req["execution"],))
            db.execute("UPDATE poc_attempts SET state='SUCCEEDED' WHERE attempt_id=%s",(req["attempt"],))
            db.execute("INSERT INTO poc_verifications(verification_id,execution_id,passed,evidence_ref) VALUES(%s,%s,TRUE,%s)",
                       (uid("verification"),req["execution"],"poc-g3://sha256/"+digest))
            self.event(db,req["run"],"verification.passed",{"execution_id":req["execution"],"sha256":digest})
            return True

    def terminal(self,req,state):
        if state not in ("COMPLETED","FAILED"):raise ValueError("Invalid state")
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            r=db.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                         (req["run"],)).fetchone()
            if r["state"]=="CANCELLED":return "CANCELLED"
            if r["state"]==state:return state
            if r["state"]!="RUNNING":raise ValueError("Unexpected terminal transition")
            if state=="COMPLETED":
                row=db.execute("SELECT state FROM poc_attempts WHERE attempt_id=%s",
                               (req["attempt"],)).fetchone()
                if row["state"]!="SUCCEEDED":raise ValueError("Cannot complete unverified Run")
            else:
                db.execute("UPDATE poc_executions SET state='FAILED' WHERE execution_id=%s AND state='RUNNING'",(req["execution"],))
                db.execute("UPDATE poc_attempts SET state='FAILED' WHERE attempt_id=%s AND state='RUNNING'",(req["attempt"],))
            db.execute("UPDATE poc_runs SET state=%s,terminal_at=now() WHERE run_id=%s",(state,req["run"]))
            self.event(db,req["run"],"run.terminal",{"state":state})
            return state

    def cancel(self,run):
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            row=db.execute("""SELECT r.state,b.attempt_id,b.execution_id
                FROM poc_c15_runs b JOIN poc_runs r ON r.run_id=b.run_id
                WHERE b.run_id=%s FOR UPDATE OF r""",(run,)).fetchone()
            if not row:raise KeyError(run)
            if row["state"] in TERMINAL:return row["state"]
            db.execute("UPDATE poc_attempts SET state='CANCELLED' WHERE attempt_id=%s AND state='RUNNING'",(row["attempt_id"],))
            db.execute("UPDATE poc_executions SET state='CANCELLED' WHERE execution_id=%s AND state='RUNNING'",(row["execution_id"],))
            db.execute("UPDATE poc_runs SET state='CANCELLED',terminal_at=now() WHERE run_id=%s",(run,))
            self.event(db,run,"run.terminal",{"state":"CANCELLED"})
            return "CANCELLED"

    def snapshot(self,run,after=0,limit=10000):
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            row=db.execute("""SELECT r.run_id,r.state,b.model,b.native_workflow_id,
                b.step_id,b.attempt_id,b.execution_id,b.start_state
                FROM poc_runs r JOIN poc_c15_runs b ON b.run_id=r.run_id
                WHERE r.run_id=%s""",(run,)).fetchone()
            if not row:raise KeyError(run)
            ev=db.execute("""SELECT seq,event_id,event_type,payload,created_at FROM poc_events
                WHERE run_id=%s AND seq>%s ORDER BY seq LIMIT %s""",
                (run,after,limit)).fetchall()
            return dict(row),[dict(e) for e in ev]
