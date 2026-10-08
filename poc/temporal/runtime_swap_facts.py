"""C09 Harness PostgreSQL facts for two actual Agent Runtime Activities.

One vendor-neutral Run, two Step/Attempt/Execution identities, immutable
Temporal/adapter/version binding and persisted verification/event sequence.
No raw model answer, key or provider URL persisted.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row

from platform_facts import TemporalTaskFacts

VERSIONS={
    "maf-harness":"maf-core-1.20.0/openai-1.15.0",
    "openai-agents":"openai-agents-0.22.2",
}

def uid(prefix: str) -> str:
    return prefix+"-"+uuid4().hex

@dataclass(frozen=True)
class RuntimeStage:
    adapter: str
    step_id: str
    attempt_id: str
    execution_id: str
    ordinal: int

@dataclass(frozen=True)
class RuntimeRun:
    run_id: str
    plan_id: str
    native_workflow_id: str
    expected_marker: str
    frozen_workflow_version: str
    stages: tuple[RuntimeStage,...]

    @classmethod
    def build(cls):
        return cls(uid("run"),uid("plan"),uid("temporal-c09"),
                   "C09-"+uuid4().hex[:8].upper(),
                   "temporal-c09-runtime-swap-v1",
                   tuple(RuntimeStage(adapter,uid("step"),uid("attempt"),
                                      uid("execution"),i)
                         for i,adapter in enumerate(VERSIONS,1)))

    def request(self) -> dict:
        return {"run_id":self.run_id,"native_workflow_id":self.native_workflow_id,
                "expected_marker":self.expected_marker,
                "frozen_workflow_version":self.frozen_workflow_version,
                "stages":[vars(x) | {"frozen_runtime_version":VERSIONS[x.adapter]}
                          for x in self.stages]}


class RuntimeFacts:
    def __init__(self,dsn: str):
        if not dsn: raise ValueError("Harness PG required")
        self.dsn=dsn

    def initialize(self):
        TemporalTaskFacts(self.dsn).initialize()
        with psycopg.connect(self.dsn) as db:
            db.execute((Path(__file__).resolve().parent/"sql"/
                        "002_real_runtime_swap.sql").read_text(encoding="utf-8"))

    def prepare(self,run:RuntimeRun):
        if len(run.stages)!=2 or tuple(x.adapter for x in run.stages)!=tuple(VERSIONS):
            raise ValueError("C09 requires two distinct frozen real SDK runtimes")
        with psycopg.connect(self.dsn) as db:
            conversation,turn=uid("conversation"),uid("turn")
            db.execute("INSERT INTO poc_conversations(conversation_id) VALUES(%s)",(conversation,))
            db.execute("INSERT INTO poc_turns(turn_id,conversation_id) VALUES(%s,%s)",
                       (turn,conversation))
            db.execute("""INSERT INTO poc_runs(run_id,turn_id,initiator_principal_id,
                      runtime_type,recipe_version,state)
                      VALUES(%s,%s,'poc-c-internal','temporal','c09-agent-runtime-v1','RUNNING')""",
                       (run.run_id,turn))
            db.execute("INSERT INTO poc_runtime_bindings(run_id,runtime_type) VALUES(%s,'temporal')",
                       (run.run_id,))
            db.execute("INSERT INTO poc_plans(plan_id,run_id,version,reason) "
                       "VALUES(%s,%s,1,'compare real agent runtime adapters')",
                       (run.plan_id,run.run_id))
            db.execute("""INSERT INTO poc_c09_run_bindings
                          (run_id,native_workflow_id,frozen_workflow_version,expected_marker)
                          VALUES(%s,%s,%s,%s)""",
                       (run.run_id,run.native_workflow_id,
                        run.frozen_workflow_version,run.expected_marker))
            for stage in run.stages:
                db.execute("INSERT INTO poc_steps(step_id,plan_id,ordinal,intent) "
                           "VALUES(%s,%s,%s,'real agent runtime semantic probe')",
                           (stage.step_id,run.plan_id,stage.ordinal))
                db.execute("INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state) "
                           "VALUES(%s,%s,1,'RUNNING')",
                           (stage.attempt_id,stage.step_id))
                db.execute("""INSERT INTO poc_executions
                              (execution_id,attempt_id,side_effect_class,state)
                              VALUES(%s,%s,'PURE','RUNNING')""",
                           (stage.execution_id,stage.attempt_id))
                db.execute("""INSERT INTO poc_c09_runtime_stages
                              (attempt_id,run_id,step_id,execution_id,ordinal,adapter,
                               frozen_runtime_version)
                              VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                           (stage.attempt_id,run.run_id,stage.step_id,
                            stage.execution_id,stage.ordinal,stage.adapter,
                            VERSIONS[stage.adapter]))
            self._event(db,run.run_id,"run.started",{"plan_version":1})

    @staticmethod
    def _event(db,run_id: str,kind: str,data:dict):
        db.execute("""INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
          VALUES(%s,%s,(SELECT coalesce(max(seq),0)+1 FROM poc_events WHERE run_id=%s),
                 %s,%s::jsonb)""",(uid("event"),run_id,run_id,kind,json.dumps(data)))

    def require_frozen(self,request:dict,stage:dict) -> None:
        """Read-only trusted stage freeze before an actual model request."""
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            row=db.execute("""SELECT b.native_workflow_id,b.frozen_workflow_version,
                             b.expected_marker,r.state AS run_state,p.plan_id,
                             s.step_id,stage.execution_id,stage.ordinal,stage.adapter,
                             stage.frozen_runtime_version,a.state AS attempt_state,
                             e.state AS execution_state
                FROM poc_c09_runtime_stages stage
                JOIN poc_c09_run_bindings b ON b.run_id=stage.run_id
                JOIN poc_runs r ON r.run_id=b.run_id
                JOIN poc_steps s ON s.step_id=stage.step_id
                JOIN poc_plans p ON p.plan_id=s.plan_id
                JOIN poc_attempts a ON a.attempt_id=stage.attempt_id
                JOIN poc_executions e ON e.execution_id=stage.execution_id
                WHERE stage.run_id=%s AND stage.attempt_id=%s AND p.version=1
                """,(request["run_id"],stage["attempt_id"])).fetchone()
        frozen={"native_workflow_id":request["native_workflow_id"],
                "frozen_workflow_version":request["frozen_workflow_version"],
                "expected_marker":request["expected_marker"]}
        for field in ("step_id","execution_id","ordinal","adapter",
                      "frozen_runtime_version"):
            frozen[field]=stage[field]
        if not row or any(row[f]!=v for f,v in frozen.items()):
            raise ValueError("C09 frozen Native Workflow or Runtime stage mismatch")
        if any(row[field]!="RUNNING" for field in ("run_state","attempt_state","execution_state")):
            raise ValueError("C09 frozen platform stage not active")

    def verify(self,run_id: str,stage:dict,observed_marker:str,output_chars:int) -> dict:
        """Trusted independent Verify Activity. Idempotent after committed ACK gap."""
        if not isinstance(output_chars,int) or output_chars<1:
            raise ValueError("Missing actual model output")
        if not isinstance(observed_marker,str) or len(observed_marker)>32:
            raise ValueError("Malformed model observation")
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            row=db.execute("""SELECT b.expected_marker,b.native_workflow_id,
                        b.frozen_workflow_version,r.state AS run_state,
                        a.state AS attempt_state,e.state AS execution_state,
                        s.step_id, s.ordinal,
                        stage.adapter,stage.frozen_runtime_version,
                        stage.execution_id
                FROM poc_c09_runtime_stages stage
                JOIN poc_c09_run_bindings b ON b.run_id=stage.run_id
                JOIN poc_runs r ON r.run_id=b.run_id
                JOIN poc_attempts a ON a.attempt_id=stage.attempt_id
                JOIN poc_executions e ON e.execution_id=stage.execution_id
                JOIN poc_steps s ON s.step_id=stage.step_id
                WHERE stage.attempt_id=%s AND stage.run_id=%s
                FOR UPDATE OF a,e,r""",
                (stage["attempt_id"],run_id)).fetchone()
            required=("step_id","execution_id","adapter","ordinal","frozen_runtime_version")
            if not row or any(row[f]!=stage.get(f) for f in required):
                raise ValueError("Frozen C09 stage identity/runtime mismatch")
            if row["attempt_state"] in ("SUCCEEDED","FAILED"):
                return {"passed":row["attempt_state"]=="SUCCEEDED",
                        "attempt_id":stage["attempt_id"],
                        "adapter":row["adapter"],"idempotent_read":True}
            if row["run_state"]!="RUNNING" or row["attempt_state"]!="RUNNING" or row["execution_state"]!="RUNNING":
                raise ValueError("C09 execution not dispatchable")
            passed=observed_marker==row["expected_marker"]
            state="SUCCEEDED" if passed else "FAILED"
            db.execute("UPDATE poc_executions SET state=%s WHERE execution_id=%s",
                       (state,row["execution_id"]))
            db.execute("UPDATE poc_attempts SET state=%s WHERE attempt_id=%s",
                       (state,stage["attempt_id"]))
            data={"attempt_id":stage["attempt_id"],
                  "execution_id":row["execution_id"],
                  "step_id":row["step_id"],"adapter":row["adapter"],
                  "output_chars":output_chars}
            self._event(db,run_id,"activity.completed",data)
            self._event(db,run_id,
                        "verification.passed" if passed else "verification.failed",
                        data|{"passed":passed})
            return {"passed":passed,"attempt_id":stage["attempt_id"],
                    "adapter":row["adapter"],"idempotent_read":False}

    def fail(self,run_id:str) -> dict:
        """Trusted verifier failure, not an inferred model/Temporal success."""
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            row=db.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                           (run_id,)).fetchone()
            if not row: raise ValueError("Run missing")
            if row["state"]=="FAILED":
                return {"state":"FAILED","idempotent_read":True}
            if row["state"]!="RUNNING":
                raise ValueError("Cannot fail terminal/non-active Run")
            attempts=db.execute("""SELECT a.attempt_id,a.state,e.execution_id,e.state AS execution_state
                FROM poc_c09_runtime_stages st
                JOIN poc_attempts a ON a.attempt_id=st.attempt_id
                JOIN poc_executions e ON e.execution_id=st.execution_id
                WHERE st.run_id=%s FOR UPDATE OF a,e""",(run_id,)).fetchall()
            if not any(a["state"]=="FAILED" for a in attempts):
                raise ValueError("Cannot mark Run FAILED without persisted verification failure")
            for a in attempts:
                if a["state"]=="RUNNING":
                    db.execute("UPDATE poc_attempts SET state='CANCELLED' WHERE attempt_id=%s",
                               (a["attempt_id"],))
                    db.execute("UPDATE poc_executions SET state='CANCELLED' WHERE execution_id=%s",
                               (a["execution_id"],))
            db.execute("UPDATE poc_runs SET state='FAILED',terminal_at=now() WHERE run_id=%s",(run_id,))
            self._event(db,run_id,"run.terminal",
                        {"status":"FAILED","verification":"FAILED"})
            return {"state":"FAILED","idempotent_read":False}

    def complete(self,run_id:str) -> dict:
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            row=db.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                           (run_id,)).fetchone()
            if not row: raise ValueError("Missing Run")
            if row["state"]=="COMPLETED":
                return {"state":"COMPLETED","idempotent_read":True}
            if row["state"]!="RUNNING":
                raise ValueError("Run is not active")
            attempts=db.execute("""SELECT a.state
                FROM poc_c09_runtime_stages b JOIN poc_attempts a ON a.attempt_id=b.attempt_id
                WHERE b.run_id=%s ORDER BY b.ordinal""",(run_id,)).fetchall()
            if len(attempts)!=2 or any(r["state"]!="SUCCEEDED" for r in attempts):
                raise ValueError("Both independent real runtimes must Verify PASS")
            db.execute("UPDATE poc_runs SET state='COMPLETED',terminal_at=now() WHERE run_id=%s",(run_id,))
            self._event(db,run_id,"run.terminal",{"status":"COMPLETED","verification":"PASSED"})
            return {"state":"COMPLETED","idempotent_read":False}

    def snapshot(self,run_id:str) -> dict:
        with psycopg.connect(self.dsn,row_factory=dict_row) as db:
            run=db.execute("SELECT run_id,state FROM poc_runs WHERE run_id=%s",(run_id,)).fetchone()
            stages=db.execute("""SELECT stage.adapter,stage.ordinal,stage.attempt_id,a.state,
                   stage.step_id,stage.execution_id
                 FROM poc_c09_runtime_stages stage
                 JOIN poc_attempts a ON a.attempt_id=stage.attempt_id
                 WHERE stage.run_id=%s ORDER BY stage.ordinal""",(run_id,)).fetchall()
            events=db.execute("SELECT seq,event_type,payload FROM poc_events "
                              "WHERE run_id=%s ORDER BY seq",(run_id,)).fetchall()
        return {"run":dict(run) if run else None,
                "stages":[dict(x) for x in stages],
                "events":[dict(x) for x in events]}
