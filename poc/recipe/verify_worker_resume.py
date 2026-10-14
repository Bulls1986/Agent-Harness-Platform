"""M6 physical Worker A kill during durable WAITING_INPUT; B resumes SAME Run.

Standalone synthetic-only fault gate; not another scheduler or agent recipe.
Engine and business facts remain Hatchet and Harness PostgreSQL respectively.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from uuid import uuid4

from poc.closed_loop.external_ledger_demo import ExternalLedger
from poc.closed_loop.facts import PgFacts
from poc.recipe import hatchet_three_agent as m6


def spawn(role: str) -> tuple[subprocess.Popen, str]:
    env = dict(os.environ, HARNESS_M6_WORKER_ROLE=role)
    path=os.path.join(tempfile.gettempdir(),"m6-worker-"+role+"-"+uuid4().hex+".log")
    with open(path,"w",encoding="utf8") as log:
        proc=subprocess.Popen(
            [sys.executable,"-B","-m","poc.recipe.hatchet_three_agent","--worker-only"],
            env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
            start_new_session=True)
    return proc,path


def wait_state(g: m6.RecipeGate, rid: str, target: str,
               worker: subprocess.Popen, timeout: float=85) -> dict:
    until=time.monotonic()+timeout
    latest=None
    while time.monotonic()<until:
        if worker.poll() is not None:
            raise RuntimeError("Worker exited before "+target+": "+str(worker.returncode))
        latest=g.snapshot(rid)
        if latest["state"]==target:
            return latest
        if latest["state"] in ("BLOCKED","FAILED","COMPLETED"):
            raise RuntimeError("Unexpected terminal before "+target+": "+repr(latest["state"]))
        time.sleep(.3)
    raise TimeoutError("Run did not reach "+target+"; last="+repr(latest["state"] if latest else None))


def verify_resume():
    if m6._cfg.mode!="deterministic_local_model":
        raise RuntimeError("Fault injection is restricted to deterministic synthetic mode")
    rid="m6recover-"+uuid4().hex
    g=m6.gate()
    db=PgFacts()
    g.freeze(rid,m6.FROZEN_RECIPE,scope="project-synthetic",
             principal="m6-synthetic-operator")
    key=rid+":segment-0:create:v1"
    db.dispatch(key)
    a=None
    b=None
    files=[]
    passed=False
    try:
        a,path=spawn("worker-A")
        files.append(path)
        time.sleep(6)
        if a.poll() is not None:
            raise RuntimeError("Worker A startup failed")
        try:
            ref=m6.workflow.run(m6.Input(
                run_id=rid,prompt="Build and independently verify the addition function."),
                wait_for_result=False)
        except Exception:
            db.unknown(key)
            raise
        db.bind(key,ref.workflow_run_id)
        before=wait_state(g,rid,"WAITING_INPUT",a)
        if before["steps"][0]["state"]!="VERIFIED":
            raise AssertionError("Plan was not verified before durable wait")
        if before["steps"][1]["state"]!="PENDING":
            raise AssertionError("Code executed before input approval")
        if len(before["inputs"])!=1 or before["inputs"][0]["state"]!="PENDING":
            raise AssertionError("Missing persisted original input wait")
        with db.tx() as c:
            native=c.execute(
                "SELECT provider_workflow_id FROM harness_run WHERE id=%s",(rid,)
            ).fetchone()[0]
        if native!=ref.workflow_run_id:
            raise AssertionError("Original Hatchet Provider ownership mismatch")
        os.killpg(a.pid,signal.SIGKILL)
        a.wait(timeout=10)
        if a.returncode!=-signal.SIGKILL:
            raise AssertionError("Worker A was not physically killed")
        after=g.snapshot(rid)
        if after["state"]!="WAITING_INPUT":
            raise AssertionError("Durable input state did not persist Worker crash")

        b,path=spawn("worker-B")
        files.append(path)
        time.sleep(7)
        if b.poll() is not None:
            raise RuntimeError("Worker B startup failed")
        external=m6.fixtures()
        input_ref=external.put(
            rid,"input",b"Confirmed synthetic input: add two integers.",
            scope="project-synthetic")
        external.verified_bytes(input_ref)
        g.answer_input(rid,"m6-independent-input-operator",
                       input_ref,"synthetic-fixture:"+input_ref.digest)
        m6._hatchet.event.push(m6.INPUT_EVENT,{"run_id":rid},scope=rid)
        wait_state(g,rid,"WAITING_APPROVAL",b)
        with db.tx() as c:
            count=c.execute(
                "SELECT count(*) FROM harness_tool_intent WHERE run_id=%s",
                (rid,)).fetchone()[0]
        if count!=0:
            raise AssertionError("Write occurred before authorization")
        g.decide_approval(rid,"code","m6-independent-approver","APPROVED")
        m6._hatchet.event.push(
            m6.APPROVAL_EVENT,{"run_id":rid,"decision":"APPROVED"},scope=rid)

        m6._hatchet.runs.get_run_ref(ref.workflow_run_id).result()
        state=g.snapshot(rid)
        effects=ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"]).find(
            rid+"-synthetic-effect")
        with db.tx() as c:
            attempts=c.execute(
                "SELECT step_id,count(*) FROM harness_step_attempt "
                "WHERE run_id=%s GROUP BY step_id",(rid,)).fetchall()
        if (state["state"]!="COMPLETED"
                or any(s["state"]!="VERIFIED" for s in state["steps"])
                or len(effects)!=1
                or sorted(attempts)!=[("code",1),("plan",1),("verify",1)]):
            raise AssertionError("Incomplete or duplicated M6 Recovery: "
                                 +repr((state["state"],effects,attempts)))
        passed=True
        return {
            "outcome":"PASS_PHYSICAL_WORKER_A_KILL_B_NATIVE_RESUME",
            "run_id":rid,"provider_run_id":ref.workflow_run_id,
            "worker_a_pid":a.pid,"worker_a_exit":a.returncode,
            "worker_b_pid":b.pid,
            "native_engine":"REAL_HATCHET_EMBEDDED_POSTGRESQL",
            "same_run":True,"same_provider":True,
            "input_resumed":True,"approval_resumed":True,
            "verified_steps":3,"nonidempotent_effects":len(effects),
            "attempts":dict(attempts),
            "cross_host":"NOT_TESTED", "real_oss":"NOT_TESTED",
        }
    finally:
        for proc in (a,b):
            if proc is not None and proc.poll() is None:
                try:
                    os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=10)
        if not passed:
            for path in files:
                try:
                    with open(path,encoding="utf8",errors="replace") as f:
                        lines=f.readlines()[-65:]
                    print("WORKER_DIAGNOSTIC",os.path.basename(path),
                          "".join(lines)[-6000:],flush=True)
                except OSError:
                    pass
        for path in files:
            try:
                os.remove(path)
            except OSError:
                pass


def main():
    status=0
    try:
        print(json.dumps(verify_resume(),sort_keys=True),flush=True)
    except Exception:
        status=1
        traceback.print_exc()
    finally:
        m6._hatchet.stop_embedded()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(status)


if __name__=="__main__":
    main()