"""A34 P1 real native MSSQL endpoints + real PostgreSQL crash-gap observations.

Use the pre-existing healthy A34 Worker B, avoiding image rebuilding and
110-second SIGKILL. Fault injection intentionally OMITS PG binding and HTTP
acknowledgement, respectively. PostgreSQL transition below is the trusted
test driver equivalent; separate CI tests exercise Python domain adapters.
NO production side effect, no TaskHub SQL mutation, no re-submit of /run
or /respond on an uncertain instance.
"""
from __future__ import annotations
import json
import re
import secrets
import time
import verify_handoff as v
import verify_guarded_native_handoff as g

v.BASE="http://127.0.0.1:17082"
RUN_NAME="maf_mssql_poc_hitl"


def poll_done(instance: str, expected: list[str]) -> dict:
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        status=v.invoke("GET",f"{v.ROUTE}/status/{instance}")
        if status.get("runtimeStatus")=="Completed":
            if status.get("output")!=expected:
                raise AssertionError("Native completed with wrong output")
            return status
        if status.get("runtimeStatus") in ("Failed","Terminated"):
            raise AssertionError("Native failed unexpectedly")
        time.sleep(1)
    raise TimeoutError("Native response did not complete")


def native_start(case: str) -> tuple[str,str]:
    started=v.invoke("POST",f"{v.ROUTE}/run",case)
    instance=started.get("instanceId")
    if not isinstance(instance,str) or not re.fullmatch("[a-f0-9]{32}",instance):
        raise AssertionError("Official MAF instance missing")
    return instance,v.pending(instance,55)


def pg_start_fact(label: str):
    n=secrets.token_hex(12)
    ids={name:label+name+"-"+n for name in
         ("conversation","turn","run","plan","step","attempt","execution")}
    g.pg(f"""
       BEGIN;
       INSERT INTO poc_conversations(conversation_id) VALUES ('{ids['conversation']}');
       INSERT INTO poc_turns(turn_id,conversation_id)
         VALUES ('{ids['turn']}','{ids['conversation']}');
       INSERT INTO poc_runs(run_id,turn_id,initiator_principal_id,runtime_type,
                            recipe_version,state)
         VALUES ('{ids['run']}','{ids['turn']}','gap-fixture','maf','gap-v1','RUNNING');
       INSERT INTO poc_plans(plan_id,run_id,version,reason)
         VALUES ('{ids['plan']}','{ids['run']}',1,'native start crash window');
       INSERT INTO poc_steps(step_id,plan_id,ordinal,intent)
         VALUES ('{ids['step']}','{ids['plan']}',1,'gap-fixture');
       INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state)
         VALUES ('{ids['attempt']}','{ids['step']}',1,'RUNNING');
       INSERT INTO poc_executions(execution_id,attempt_id,side_effect_class,state)
         VALUES ('{ids['execution']}','{ids['attempt']}','NON_RETRYABLE','RUNNING');
       INSERT INTO poc_maf_durable_launch_intents
         (execution_id,run_id,step_id,attempt_id,native_workflow_name,
          frozen_workflow_version,frozen_runtime_version)
         VALUES ('{ids['execution']}','{ids['run']}','{ids['step']}',
                 '{ids['attempt']}','{RUN_NAME}','gap-v1','sdk-fixture-v1');
       COMMIT;
    """)
    return ids


def orphan():
    # PG intent committed before calling official native /run.
    ids=pg_start_fact("gap-")
    case="approved-fixture-"+secrets.token_hex(6)
    instance,request_id=native_start(case)
    if v.count(case,"action")!=0:
        raise AssertionError("Orphan performed an unsafe action")
    binding_count=g.pg(f"SELECT count(*) FROM poc_maf_durable_running_bindings "
                       f"WHERE execution_id='{ids['execution']}';")
    if binding_count!=["0"]:
        raise AssertionError("Crash-gap fixture unexpectedly committed Native binding")
    # Deliberately simulate the process crash after native /run but before PG bind.
    # This is NOT auto-completion: domain adapter has separate real-PG CI tests.
    g.pg(f"""
      BEGIN;
      UPDATE poc_attempts SET state='UNKNOWN',failure_type='NATIVE_START_UNCERTAIN'
        WHERE attempt_id='{ids['attempt']}' AND state='RUNNING';
      UPDATE poc_executions SET state='UNKNOWN',failure_type='NATIVE_START_UNCERTAIN'
        WHERE execution_id='{ids['execution']}' AND state='RUNNING';
      INSERT INTO poc_reconciliations(execution_id,run_id,state,failure_type)
        VALUES ('{ids['execution']}','{ids['run']}','PENDING','NATIVE_START_UNCERTAIN');
      COMMIT;
    """)
    state=g.pg(f"""
      SELECT a.state,e.state,rc.state,
             (SELECT count(*) FROM poc_maf_durable_launch_intents
              WHERE execution_id='{ids['execution']}')
      FROM poc_attempts a JOIN poc_executions e ON e.attempt_id=a.attempt_id
      JOIN poc_reconciliations rc ON rc.execution_id=e.execution_id
      WHERE e.execution_id='{ids['execution']}';
    """)
    if state!=["UNKNOWN|UNKNOWN|PENDING|1"]:
        raise AssertionError("Orphan platform quarantine not committed")
    if v.pending(instance,10)!=request_id:
        raise AssertionError("Orphan provider request disappeared")
    if v.count(case,"action")!=0:
        raise AssertionError("Orphan tool effect")
    return {"native_instance":instance,"native_request_pending":True,
            "native_bindings":0,"launch_intents":1,"attempts":1,
            "platform_outcome":"UNKNOWN_RECONCILIATION","tool_effects":0}


def response_ack_lost():
    case="approved-fixture-"+secrets.token_hex(6)
    instance,req=native_start(case)
    n=secrets.token_hex(12)
    ids={name:"resp"+name+"-"+n for name in
         ("conversation","turn","run","plan","step","attempt","approval","token")}
    # Approval + immutable native binding committed before decision, exactly
    # following platform schema. Delivery claim persisted BEFORE POST.
    g.pg(f"""
       BEGIN;
       INSERT INTO poc_conversations(conversation_id) VALUES ('{ids['conversation']}');
       INSERT INTO poc_turns(turn_id,conversation_id)
         VALUES ('{ids['turn']}','{ids['conversation']}');
       INSERT INTO poc_runs(run_id,turn_id,initiator_principal_id,runtime_type,
                            recipe_version,state)
         VALUES ('{ids['run']}','{ids['turn']}','fixture','maf','approval-v1','WAITING_APPROVAL');
       INSERT INTO poc_plans(plan_id,run_id,version,reason)
         VALUES ('{ids['plan']}','{ids['run']}',1,'native response');
       INSERT INTO poc_steps(step_id,plan_id,ordinal,intent)
         VALUES ('{ids['step']}','{ids['plan']}',1,'wait-for-approval');
       INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state)
         VALUES ('{ids['attempt']}','{ids['step']}',1,'CREATED');
       INSERT INTO poc_approvals(approval_id,run_id,step_id,attempt_id,
           action_ref,resource_ref,policy_ref,requester_principal_id,
           required_approver_principal_id,state)
         VALUES ('{ids['approval']}','{ids['run']}','{ids['step']}',
           '{ids['attempt']}','poc','poc','poc','fixture','approver','PENDING');
       INSERT INTO poc_maf_durable_approval_bindings(approval_id,run_id,step_id,
           attempt_id,native_instance_id,native_request_id,native_workflow_name,
           frozen_workflow_version,frozen_runtime_version)
         VALUES ('{ids['approval']}','{ids['run']}','{ids['step']}','{ids['attempt']}',
           '{instance}','{req}','{RUN_NAME}','gap-v1','sdk-fixture-v1');
       UPDATE poc_approvals SET state='APPROVED',decided_by_principal_id='approver',
           decided_at=now() WHERE approval_id='{ids['approval']}';
       UPDATE poc_runs SET state='RUNNING' WHERE run_id='{ids['run']}';
       INSERT INTO poc_maf_hitl_deliveries(approval_id,delivery_token,state)
         VALUES ('{ids['approval']}','{ids['token']}','IN_FLIGHT');
       COMMIT;
    """)
    # Exactly ONE actual native HTTP Response: the original delivery request.
    # Crash injection: skip PG acknowledgement after POST, as if the client died.
    v.invoke("POST",f"{v.ROUTE}/respond/{instance}/{req}","APPROVED")
    result=poll_done(instance,["SIMULATED_EXECUTION:"+case])
    if v.count(case,"action")!=1:
        raise AssertionError("External action count not one")
    # New worker observes native terminal state, PG was still IN_FLIGHT.
    observed=result["runtimeStatus"]
    old=g.pg(f"SELECT state FROM poc_maf_hitl_deliveries "
             f"WHERE approval_id='{ids['approval']}';")
    if old!=["IN_FLIGHT"] or observed!="Completed":
        raise AssertionError("Missing real HTTP acknowledgement-loss gap")
    # Manual P1 fixture reconciliation replicates read-only PG adapter transition.
    g.pg(f"""
      UPDATE poc_maf_hitl_deliveries SET state='APPLIED',
        output_kind='SIMULATED_EXECUTION',completed_at=now()
      WHERE approval_id='{ids['approval']}' AND state='IN_FLIGHT';
    """)
    final=g.pg(f"SELECT state,output_kind FROM poc_maf_hitl_deliveries "
               f"WHERE approval_id='{ids['approval']}';")
    if final!=["APPLIED|SIMULATED_EXECUTION"]:
        raise AssertionError("Native observed terminal cannot close delivery")
    return {"native_instance":instance,"native_http_responses":1,
            "native_state":observed,"platform_delivery_before":"IN_FLIGHT",
            "delivery_reconciled":"APPLIED","simulated_action_count":1}


def main():
    if g.pg("SELECT to_regclass('poc_maf_durable_launch_intents') IS NOT NULL;")!=["t"]:
        from pathlib import Path
        g.pg((Path(__file__).resolve().parents[1] / "sql" /
              "009_durable_launch_intent.sql").read_text(encoding="utf-8"))
    v.wait_for_host(12)
    first=orphan()
    second=response_ack_lost()
    print(json.dumps({"status":"PASS_REAL_NATIVE_CROSS_DB_TWO_GAPS",
                      "orphan":first,"response_ack_lost":second,
                      "platform_transition_driver":"explicit_test_SQL",
                      "native_provider":"official_MAF_AzureFunctions_MSSQL",
                      "production_cross_db_atomicity":False},sort_keys=True),flush=True)


if __name__=="__main__":
    main()
