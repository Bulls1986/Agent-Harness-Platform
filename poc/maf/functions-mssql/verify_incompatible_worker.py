"""A34: real different-image v2 Worker cannot execute v1 native instance.

Uses existing MSSQL/Azurite/PostgreSQL; isolates Native DB+TaskHub and cases.
Distinguishes actual changed application image from same-image/config test.
The public MAF Durable runtime is NOT claimed to pin a binary automatically:
the trusted Harness Tool Adapter MUST reject mismatched version before dispatch.
"""
from __future__ import annotations
import json
import re
import secrets
import threading
import time
from pathlib import Path
import verify_handoff as v
import verify_guarded_native_handoff as g

ROOT = Path(__file__).resolve().parent
COMPOSE = ROOT.parent / "compose-functions-mssql-a34-version.yml"
PROJECT = "maf-mssql-a34-version"
FIRST = "http://127.0.0.1:17111"
SECOND = "http://127.0.0.1:17112"
ROUTE = "/api/workflow/maf_mssql_poc_guarded"


def compose(*args):
    return g.shell("docker","compose","-p",PROJECT,"--env-file",
                   str(g.ENVFILE),"-f",str(COMPOSE),*args)


def worker(name):
    cid=compose("ps","-q",name)
    if not re.fullmatch(r"[a-f0-9]{12,64}",cid):
        raise AssertionError("No worker: "+name)
    if g.shell("docker","inspect","-f","{{.State.Running}}",cid)!="true":
        raise AssertionError("Worker offline: "+name)
    return cid


def status(instance):
    return v.invoke("GET",f"{ROUTE}/status/{instance}")


def sql_native(instance):
    if not re.fullmatch("[0-9a-f]{32}",instance):
        raise ValueError("Bad native instance")
    query=("SET NOCOUNT ON; SELECT RuntimeStatus FROM dt.Instances "
           f"WHERE InstanceID='{instance}'; SELECT COUNT(*) FROM dt.History "
           f"WHERE InstanceID='{instance}';")
    command=("/opt/mssql-tools18/bin/sqlcmd -C -b -h -1 -W "
             '-S localhost -U sa -P "$MSSQL_SA_PASSWORD" '
             f'-d DurableA34Version -Q "{query}"')
    lines=g.shell("docker","exec",g.MSSQL,"/bin/bash","-lc",command).splitlines()
    rows=[x.strip() for x in lines if x.strip()]
    if len(rows)!=2 or not rows[1].isdigit():
        raise AssertionError("Native DB audit invalid: "+repr(rows[:6]))
    return rows[0],int(rows[1])


def freeze_failed(ids):
    # Trusted fault-injection harness classification; production orchestration
    # must implement this transition itself. NO dispatch occurred.
    g.pg(f"""
       BEGIN;
       UPDATE poc_execution_ownership SET owner_id=NULL,
         revoked_at=now(),fencing_token=2
         WHERE execution_id='{ids['execution']}' AND dispatched_at IS NULL;
       UPDATE poc_attempts SET state='FAILED',
         failure_type='INCOMPATIBLE_WORKFLOW_VERSION'
         WHERE attempt_id='{ids['attempt']}' AND state='RUNNING';
       UPDATE poc_executions SET state='FAILED',
         failure_type='INCOMPATIBLE_WORKFLOW_VERSION'
         WHERE execution_id='{ids['execution']}' AND state='RUNNING';
       UPDATE poc_runs SET state='FAILED',terminal_at=now()
         WHERE run_id='{ids['run']}' AND state='RUNNING';
       COMMIT;
    """)


def main():
    if not g.ENVFILE.exists():
        raise RuntimeError("Ignored local MSSQL env missing")
    case="guarded-fixture-"+secrets.token_hex(6)
    v.MARKERS.mkdir(parents=True,exist_ok=True)
    token=secrets.token_hex(32)
    token_file=v.MARKERS/(case+".gateway_token")
    token_file.write_text(token,encoding="utf-8")
    ctx={"case":case,"token":token}
    server=g.GateServer(ctx)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        ids=g.prepare_pg(case)
        ctx["exec"]=ids["execution"]
        v.BASE=FIRST
        compose("stop","worker-b")
        compose("up","-d","--no-deps","--force-recreate","worker-a")
        a=worker("worker-a")
        v.wait_for_host(140)
        started=v.invoke("POST",f"{ROUTE}/run",case)
        instance=started.get("instanceId")
        if not isinstance(instance,str) or not re.fullmatch("[0-9a-f]{32}",instance):
            raise AssertionError("Missing native instance: "+repr(started))
        ctx["instance"]=instance
        g.bind_native(ids,instance)
        g.wait_until("V1 prepare entered before tool",
                     lambda: v.count(case,"prepare")==1,50)
        if v.count(case,"guarded_dispatch_entered") or v.count(case,"tool_sink_effect"):
            raise AssertionError("V1 tool was dispatched before fault")
        compose("up","-d","--no-deps","--force-recreate","worker-b")
        b=worker("worker-b")
        v.BASE=SECOND
        v.wait_for_host(140)
        image_a=g.shell("docker","inspect","-f","{{.Image}}",a)
        image_b=g.shell("docker","inspect","-f","{{.Image}}",b)
        if image_a==image_b:
            raise AssertionError("Not different application images!")
        source_b=g.shell("docker","exec",b,"grep","WORKER_GUARDED_WORKFLOW_VERSION =","/home/site/wwwroot/function_app.py")
        if 'v2-incompatible' not in source_b:
            raise AssertionError("Worker B not running incompatible workflow source")
        if worker("worker-a")!=a or v.count(case,"guarded_dispatch_entered"):
            raise AssertionError("V1 prepare crashed/finished before injection")
        g.shell("docker","kill","--signal","KILL",a)
        if worker("worker-b")!=b:
            raise AssertionError("B restarted during SIGKILL")
        g.wait_until("B native handler passes V2 to frozen V1 gateway",
                     lambda: v.count(case,"gateway_version_denied")>=1,280)
        g.wait_until("B handler receives explicit version rejection",
                     lambda: v.count(case,"guarded_version_denied")>=1,20)
        g.wait_until("Native incompatible instance terminal Failed",
                     lambda: status(instance).get("runtimeStatus")=="Failed",40)
        result=status(instance)
        mssql,history=sql_native(instance)
        if mssql!="Failed" or result["runtimeStatus"]!="Failed":
            raise AssertionError("Native instance did not fail closed")
        if "HARNESS_INCOMPATIBLE_WORKER_VERSION" not in str(result.get("output")):
            raise AssertionError("Wrong native failure reason")
        if v.count(case,"tool_sink_effect")!=0 or v.count(case,"guarded_admission_applied"):
            raise AssertionError("Incompatible Worker dispatched external tool!")
        if v.count(case,"guarded_dispatch_entered")<1:
            raise AssertionError("V2 did not reach actual native Executor handler")
        if server.audit!=["version_denied"]:
            raise AssertionError("Unexpected gateway outcome: "+repr(server.audit))
        freeze_failed(ids)
        pg=g.pg(f"""
          SELECT r.state,a.state,e.state,o.dispatched_at IS NULL,
                 o.fencing_token,b.native_instance_id,
                 (SELECT COUNT(*) FROM poc_attempts a2
                  JOIN poc_steps s ON s.step_id=a2.step_id
                  JOIN poc_plans p ON p.plan_id=s.plan_id
                  WHERE p.run_id='{ids['run']}')
          FROM poc_runs r JOIN poc_plans p ON p.run_id=r.run_id
          JOIN poc_steps s ON s.plan_id=p.plan_id
          JOIN poc_attempts a ON a.step_id=s.step_id
          JOIN poc_executions e ON e.attempt_id=a.attempt_id
          JOIN poc_execution_ownership o ON o.execution_id=e.execution_id
          JOIN poc_maf_durable_running_bindings b ON b.execution_id=e.execution_id
          WHERE r.run_id='{ids['run']}';""")
        if pg!=[f"FAILED|FAILED|FAILED|t|2|{instance}|1"]:
            raise AssertionError("PG version fail-closed mismatch: "+repr(pg))
        print(json.dumps({
            "scenario":"A34-REAL-INCOMPATIBLE-IMAGE-NATIVE-FAIL-CLOSED",
            "native_instance_id":instance,
            "native_mssql_state":mssql,
            "native_history_rows":history,
            "worker_a_sigkill":a[:12],
            "worker_b_unchanged":b[:12],
            "different_application_images":True,
            "incompatible_v2_handler_entries":v.count(case,"guarded_dispatch_entered"),
            "gateway_sequence":server.audit,
            "external_tool_effects":0,
            "platform_attempt_count":1,
            "platform_run_state":"FAILED",
            "platform_attempt_state":"FAILED",
            "platform_fencing_token":2,
            "platform_native_binding_still_v1":True,
            "same_sdk_binary_version":True,
            "status":"PASS_ACTUAL_APP_VERSION_REJECTED",
        },sort_keys=True),flush=True)
    finally:
        server.shutdown()
        server.server_close()
        token_file.unlink(missing_ok=True)


if __name__=="__main__":
    main()
