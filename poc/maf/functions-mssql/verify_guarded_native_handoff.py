"""A34 real native MSSQL Durable Worker SIGKILL + Harness PostgreSQL admission.

The only synthetic tool is a host HTTP fixture sink. Its receipt is outside
MAF and written ONLY after committed PostgreSQL dispatch admission. The
gateway invokes local Docker postgres psql for the same A29 fencing predicate;
the PostgreSQL API adapter is independently covered by test_maf_guarded_dispatch_pg.
Never changes existing MSSQL TaskHub data or deletes existing PG records.

POC-only HTTP bound briefly to 0.0.0.0 for Docker Desktop host.docker.internal,
protected by a per-case random one-use fixture token; never expose in prod.
"""
from __future__ import annotations

import json
import re
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import verify_handoff as v

ROOT = Path(__file__).resolve().parent
COMPOSE_FILE = ROOT.parent / "compose-functions-mssql-a34-guarded.yml"
ENVFILE = ROOT / ".env.local"
MIGRATION = ROOT.parent / "sql" / "008_durable_running_binding.sql"
PROJECT = "maf-mssql-a34-guarded"
FIRST = "http://127.0.0.1:17101"
SECOND = "http://127.0.0.1:17102"
ROUTE = "/api/workflow/maf_mssql_poc_guarded"
POSTGRES = "maf-a34-postgres"
MSSQL = "maf-mssql-poc-mssql-1"
PORT = 17105


def shell(*argv: str) -> str:
    return subprocess.check_output(argv, text=True, stderr=subprocess.STDOUT).strip()


def compose(*args: str) -> str:
    return shell("docker", "compose", "-p", PROJECT, "--env-file",
                 str(ENVFILE), "-f", str(COMPOSE_FILE), *args)


def pg(sql: str) -> list[str]:
    proc = subprocess.run(
        ["docker", "exec", "-i", POSTGRES, "psql", "-U", "poc",
         "-d", "poc_harness", "-X", "-qAt", "-v", "ON_ERROR_STOP=1"],
        input=sql, text=True, capture_output=True, timeout=20,
    )
    if proc.returncode:
        raise AssertionError(f"PG query failed: {proc.stderr[-1800:]}")
    return [x.strip() for x in proc.stdout.splitlines() if x.strip()]


def worker(service: str) -> str:
    cid = compose("ps", "-q", service)
    if not re.fullmatch("[0-9a-f]{12,64}", cid):
        raise AssertionError("Worker container absent: " + service)
    if shell("docker", "inspect", "-f", "{{.State.Running}}", cid) != "true":
        raise AssertionError("Worker not live: " + service)
    return cid


def wait_until(what: str, check, seconds: float):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.45)
    raise TimeoutError("Timed out waiting for " + what)


def native_status(instance: str) -> dict:
    return v.invoke("GET", f"{ROUTE}/status/{instance}")


def native_history(instance: str) -> tuple[str, int]:
    if not re.fullmatch("[0-9a-f]{32}", instance):
        raise ValueError("Unexpected MSSQL native instance ID")
    query = (f"SET NOCOUNT ON; SELECT RuntimeStatus FROM dt.Instances "
             f"WHERE InstanceID='{instance}'; SELECT COUNT(*) FROM dt.History "
             f"WHERE InstanceID='{instance}';")
    command = ("/opt/mssql-tools18/bin/sqlcmd -C -b -h -1 -W "
               "-S localhost -U sa -P \"$MSSQL_SA_PASSWORD\" "
               f"-d DurableA34Guarded -Q \"{query}\"")
    lines = shell("docker", "exec", MSSQL, "/bin/bash", "-lc", command).splitlines()
    lines = [x.strip() for x in lines if x.strip()]
    if len(lines) != 2 or not lines[1].isdigit():
        raise AssertionError("Invalid native SQL audit: " + repr(lines[:5]))
    return lines[0], int(lines[1])


class GateServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, context: dict):
        self.context = context
        self.audit = []
        self.lock = threading.Lock()
        super().__init__(("0.0.0.0", PORT), GateHandler)


class GateHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return  # never log authentication tokens or request bodies

    def do_POST(self):
        ctx = self.server.context
        if self.path != "/admit" or self.headers.get("X-POC-Token") != ctx["token"]:
            self.send_error(403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 150 or length < 1:
                self.send_error(400)
                return
            supplied = json.loads(self.rfile.read(length).decode("utf-8"))
            if supplied != {"case": ctx["case"]}:
                self.send_error(403)
                return
            # Same exact trusted Execution and immutable native binding on A/B.
            # This is the A29 atomic fenced dispatch predicate, not a TaskHub lease.
            sql = f"""
            UPDATE poc_execution_ownership o SET dispatched_at=now()
            WHERE o.execution_id='{ctx['exec']}' AND o.owner_id='MAF-worker-A'
              AND o.fencing_token=1 AND o.revoked_at IS NULL
              AND o.dispatched_at IS NULL AND o.lease_expires_at>now()
              AND EXISTS (
                 SELECT 1 FROM poc_maf_durable_running_bindings b
                 JOIN poc_executions e ON e.execution_id=b.execution_id
                 JOIN poc_attempts a ON a.attempt_id=b.attempt_id
                 JOIN poc_runs r ON r.run_id=b.run_id
                 JOIN poc_steps s ON s.step_id=b.step_id
                 JOIN poc_plans p ON p.plan_id=s.plan_id
                 WHERE b.execution_id=o.execution_id
                   AND b.native_instance_id='{ctx['instance']}'
                   AND b.frozen_workflow_version='maf_mssql_poc_guarded:v1'
                   AND b.frozen_runtime_version='agent-framework-azurefunctions==1.0.0b260922'
                   AND e.state='RUNNING' AND a.state='RUNNING'
                   AND r.state='RUNNING' AND p.run_id=r.run_id
                   AND p.version=(SELECT MAX(version) FROM poc_plans
                                   WHERE run_id=r.run_id)
              ) RETURNING 1;
            """
            with self.server.lock:
                admitted = pg(sql)
                if admitted == ["1"]:
                    # Controlled *external tool sink* receipt, only after
                    # committed PostgreSQL admission; no duplicate from replay.
                    with (v.MARKERS / f"{ctx['case']}.tool_sink_effect").open(
                        "a", encoding="utf-8"
                    ) as f:
                        f.write("applied\n")
                    self.server.audit.append("admitted")
                    status = 200
                elif admitted == []:
                    with (v.MARKERS / f"{ctx['case']}.gateway_denied").open(
                        "a", encoding="utf-8"
                    ) as f:
                        f.write("denied\n")
                    self.server.audit.append("denied")
                    status = 409
                else:
                    raise AssertionError("Unexpected SQL admission result")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "admitted" if status == 200
                                         else "replay_blocked"}).encode("utf-8"))
        except Exception as exc:
            self.server.audit.append("gateway_error:" + type(exc).__name__)
            self.send_error(500)


def prepare_pg(case: str) -> dict:
    if pg("SELECT to_regclass('poc_maf_durable_running_bindings') IS NOT NULL;") != ["t"]:
        pg(MIGRATION.read_text(encoding="utf-8"))
    nonce = secrets.token_hex(16)
    ids = {name: name + "-" + nonce for name in (
        "conversation", "turn", "run", "plan", "step", "attempt", "execution")}
    rows = pg(f"""
        BEGIN;
        INSERT INTO poc_conversations(conversation_id)
          VALUES ('{ids['conversation']}');
        INSERT INTO poc_turns(turn_id,conversation_id)
          VALUES ('{ids['turn']}','{ids['conversation']}');
        INSERT INTO poc_runs(run_id,turn_id,initiator_principal_id,
                             runtime_type,recipe_version,state)
          VALUES ('{ids['run']}','{ids['turn']}','poc-a34-guarded',
                  'maf','guarded-v1','RUNNING');
        INSERT INTO poc_plans(plan_id,run_id,version,reason)
          VALUES ('{ids['plan']}','{ids['run']}',1,'guarded native SIGKILL');
        INSERT INTO poc_steps(step_id,plan_id,ordinal,intent)
          VALUES ('{ids['step']}','{ids['plan']}',1,'guarded tool fixture');
        INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state)
          VALUES ('{ids['attempt']}','{ids['step']}',1,'RUNNING');
        INSERT INTO poc_executions(execution_id,attempt_id,side_effect_class,state)
          VALUES ('{ids['execution']}','{ids['attempt']}','NON_RETRYABLE','RUNNING');
        INSERT INTO poc_execution_ownership
          (execution_id,owner_id,fencing_token,lease_expires_at)
          VALUES ('{ids['execution']}','MAF-worker-A',1,now()+interval '10 minutes');
        COMMIT;
    """)
    if rows:
        raise AssertionError("Unexpected PG fixture insert output")
    return ids


def bind_native(ids: dict, instance: str) -> None:
    pg(f"""
        INSERT INTO poc_maf_durable_running_bindings (
          execution_id,run_id,step_id,attempt_id,native_instance_id,
          native_workflow_name,frozen_workflow_version,frozen_runtime_version)
        VALUES ('{ids['execution']}','{ids['run']}','{ids['step']}',
                '{ids['attempt']}','{instance}','maf_mssql_poc_guarded',
                'maf_mssql_poc_guarded:v1',
                'agent-framework-azurefunctions==1.0.0b260922');
    """)
    got = pg(f"SELECT native_instance_id FROM poc_maf_durable_running_bindings "
             f"WHERE execution_id='{ids['execution']}';")
    if got != [instance]:
        raise AssertionError("Immutable PG/native Instance binding missing")


def set_unknown(ids: dict) -> None:
    # Equivalent bounded A28/A29 fail-closed platform outcome with trusted
    # fault injection of crashed Owner, not native Durable TaskHub manipulation.
    pg(f"""
       BEGIN;
       UPDATE poc_execution_ownership
         SET owner_id=NULL,fencing_token=fencing_token+1,revoked_at=now()
         WHERE execution_id='{ids['execution']}' AND dispatched_at IS NOT NULL;
       UPDATE poc_attempts SET state='UNKNOWN',failure_type='EXECUTOR_CRASH'
         WHERE attempt_id='{ids['attempt']}' AND state='RUNNING';
       UPDATE poc_executions SET state='UNKNOWN',failure_type='EXECUTOR_CRASH'
         WHERE execution_id='{ids['execution']}' AND state='RUNNING';
       INSERT INTO poc_reconciliations (execution_id,run_id,state,failure_type)
         VALUES ('{ids['execution']}','{ids['run']}','PENDING','EXECUTOR_CRASH');
       COMMIT;
    """)


def audit_pg(ids: dict, instance: str) -> list[str]:
    return pg(f"""
        SELECT o.dispatched_at IS NOT NULL, o.fencing_token,
               t.state,e.state, b.native_instance_id,
               (SELECT count(*) FROM poc_attempts a JOIN poc_steps s
                ON s.step_id=a.step_id JOIN poc_plans p ON p.plan_id=s.plan_id
                WHERE p.run_id='{ids['run']}'),
               (SELECT count(*) FROM poc_reconciliations rc
                WHERE rc.execution_id='{ids['execution']}' AND rc.state='PENDING')
        FROM poc_executions e
        JOIN poc_attempts t ON t.attempt_id=e.attempt_id
        JOIN poc_maf_durable_running_bindings b ON b.execution_id=e.execution_id
        JOIN poc_execution_ownership o ON o.execution_id=e.execution_id
        WHERE e.execution_id='{ids['execution']}'
          AND b.native_instance_id='{instance}';
    """)


def main() -> None:
    if not ENVFILE.is_file():
        raise RuntimeError("Missing existing ignored SQL fixture env file")
    case = "guarded-fixture-" + secrets.token_hex(6)
    v.MARKERS.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(32)
    token_file = v.MARKERS / (case + ".gateway_token")
    token_file.write_text(token, encoding="utf-8")
    ctx = {"case": case, "token": token}
    server = GateServer(ctx)
    runner = threading.Thread(target=server.serve_forever, daemon=True)
    runner.start()
    try:
        ids = prepare_pg(case)
        ctx["exec"] = ids["execution"]
        v.BASE = FIRST
        compose("stop", "worker-b")
        compose("up", "-d", "--no-deps", "--force-recreate", "worker-a")
        a = worker("worker-a")
        v.wait_for_host(130)
        start = v.invoke("POST", f"{ROUTE}/run", case)
        instance = start.get("instanceId")
        if not isinstance(instance,str) or not re.fullmatch("[0-9a-f]{32}",instance):
            raise AssertionError("Native Instance missing: " + repr(start))
        ctx["instance"] = instance
        bind_native(ids, instance)
        wait_until("A first committed gate admission",
                   lambda: v.count(case, "tool_sink_effect") == 1, 50)
        if v.count(case, "guarded_dispatch_entered") != 1:
            raise AssertionError("First native Executor entry not unique")
        if v.count(case, "guarded_completed_after_tool"):
            raise AssertionError("Interrupted worker finished too early")
        state = native_status(instance)
        if state.get("runtimeStatus") in ("Completed","Failed","Terminated"):
            raise AssertionError("Native workflow already terminal before kill")
        compose("up", "-d", "--no-deps", "--force-recreate", "worker-b")
        b = worker("worker-b")
        if a == b:
            raise AssertionError("Expected distinct Workers")
        v.BASE = SECOND
        v.wait_for_host(130)
        if worker("worker-a") != a or worker("worker-b") != b:
            raise AssertionError("Both workers must be online before crash")
        if v.count(case, "guarded_completed_after_tool"):
            raise AssertionError("The fault injection window elapsed")
        shell("docker", "kill", "--signal", "KILL", a)
        if worker("worker-b") != b:
            raise AssertionError("Worker B restarted")
        # Native Durable is free to retry its interrupted handler; the
        # persisted PostgreSQL dispatch gate MUST deny the second tool call.
        wait_until("native handler replay denied by PG admission",
                   lambda: v.count(case, "gateway_denied") >= 1, 280)
        wait_until("Worker B observed HTTP replay denial",
                   lambda: v.count(case, "guarded_admission_denied") >= 1, 20)
        if v.count(case, "tool_sink_effect") != 1:
            raise AssertionError("Duplicate external tool side effect observed")
        set_unknown(ids)
        postgres = audit_pg(ids, instance)
        if len(postgres)!=1 or postgres[0].split("|")[:4]!=["t","2","UNKNOWN","UNKNOWN"]:
            raise AssertionError("Postgres state/owner fence mismatch: " + repr(postgres))
        if postgres[0].split("|")[4:] != [instance,"1","1"]:
            raise AssertionError("Native binding/Attempt/reconciliation mismatch")
        wait_until("native Failed terminal after explicit replay denial",
                   lambda: native_status(instance).get("runtimeStatus") == "Failed", 30)
        native = native_status(instance)
        status = native.get("runtimeStatus")
        mssql_status, history = native_history(instance)
        if status != "Failed" or mssql_status != "Failed":
            raise AssertionError("Native must fail closed on unsafe replay")
        if "HARNESS_TOOL_REPLAY_DENIED" not in str(native.get("output")):
            raise AssertionError("Native failure reason did not reflect admission guard")
        result = {
            "scenario": "A34-NATIVE-MSSQL-PG-GUARDED-EXECUTOR-REPLAY",
            "native_instance": instance,
            "native_runtime_status_observed": status,
            "mssql_runtime_status_observed": mssql_status,
            "mssql_history_rows_at_observation": history,
            "worker_a_sigkill": a[:12],
            "worker_b_not_restarted": b[:12],
            "native_executor_entry_count": v.count(case,"guarded_dispatch_entered"),
            "native_executor_denial_count": v.count(case,"guarded_admission_denied"),
            "http_gateway_admission_sequence": server.audit,
            "tool_sink_effect_count": v.count(case,"tool_sink_effect"),
            "postgres_attempt_count": 1,
            "postgres_attempt_state": "UNKNOWN",
            "postgres_reconciliation_state": "PENDING",
            "postgres_fencing_token": 2,
            "native_binding_immutable": True,
            "production_exactly_once_proven": False,
            "status": "PASS_GUARDED_REPLAY_SINGLE_FAULT_CHAIN",
        }
        if result["native_executor_entry_count"] < 2:
            raise AssertionError("Native replay never observed")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    finally:
        server.shutdown()
        server.server_close()
        token_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
