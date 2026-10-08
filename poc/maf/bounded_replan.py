"""A13/A17 bounded deterministic Replan with *real* MAF Workflow and PG facts.

Trusted fixed Document fixture: Plan v1 fails independent Verification; one
new immutable Plan v2 and Step/Attempt are created atomically. A second actual
MAF Workflow verifies the reference candidate and closes the original Run.
This tests platform state/Plan semantics, NOT autonomous model planning, shell,
Sandbox, OSS payload, or a production Replan scheduler.
"""
from __future__ import annotations

import json
from dataclasses import replace
from uuid import uuid4

import psycopg

from document_workflow import run_document_case
from task_ledger import TaskFactConflict, TaskLedger
from workflow_probe import VerificationFact


def _id(kind: str) -> str:
    return f"{kind}-{uuid4().hex}"


def commit_verification_failure_and_replan(
    ledger: TaskLedger, fact: VerificationFact, execution_id: str,
    *,
    passed: bool, evidence_ref: str | None,
) -> tuple[VerificationFact, str]:
    """Single PG transaction; bounded to one replan, NEVER reuse old Attempt."""
    if passed or not evidence_ref or fact.plan_version != 1:
        raise TaskFactConflict("Replan requires trusted failed v1 verification with Evidence")
    new_fact=replace(fact,plan_id=_id("plan"),step_id=_id("step"),
                     attempt_id=_id("attempt"),plan_version=2,
                     passed=False,evidence_ref=None)
    second_exec=_id("execution")
    with psycopg.connect(ledger.dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",(fact.run_id,))
            row=cur.fetchone()
            if row is None or row[0]!="RUNNING":
                raise TaskFactConflict("Cannot replan an inactive Run")
            cur.execute("SELECT MAX(version) FROM poc_plans WHERE run_id=%s",(fact.run_id,))
            if cur.fetchone()[0]!=1:
                raise TaskFactConflict("POC limit: exactly one replan")
            cur.execute(
                """SELECT 1 FROM poc_executions e
                   JOIN poc_attempts a ON a.attempt_id=e.attempt_id
                   JOIN poc_steps s ON s.step_id=a.step_id
                   JOIN poc_plans p ON p.plan_id=s.plan_id
                   WHERE e.execution_id=%s AND e.state='RUNNING'
                     AND a.attempt_id=%s AND a.state='RUNNING'
                     AND s.step_id=%s AND p.plan_id=%s AND p.run_id=%s""",
                (execution_id,fact.attempt_id,fact.step_id,fact.plan_id,fact.run_id),
            )
            if cur.fetchone() is None:
                raise TaskFactConflict("Cannot replan stale or wrong Attempt")
            cur.execute(
                "UPDATE poc_attempts SET state='FAILED',failure_type='VERIFICATION_FAILURE' "
                "WHERE attempt_id=%s",(fact.attempt_id,),
            )
            cur.execute(
                "UPDATE poc_executions SET state='FAILED',failure_type='VERIFICATION_FAILURE' "
                "WHERE execution_id=%s",(execution_id,),
            )
            cur.execute(
                """INSERT INTO poc_verifications
                   (verification_id,execution_id,passed,evidence_ref)
                   VALUES (%s,%s,false,%s)""",(_id("verification"),execution_id,evidence_ref),
            )
            cur.execute(
                """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                   VALUES (%s,%s,2,'verification.failed',%s::jsonb)""",
                (_id("event"),fact.run_id,json.dumps({
                    "attempt_id":fact.attempt_id,"step_id":fact.step_id,
                    "failure_type":"VERIFICATION_FAILURE","evidence_ref":evidence_ref,
                })),
            )
            cur.execute(
                """INSERT INTO poc_plans(plan_id,run_id,version,parent_plan_id,reason)
                   VALUES (%s,%s,2,%s,'independent verification failed')""",
                (new_fact.plan_id,fact.run_id,fact.plan_id),
            )
            cur.execute(
                "INSERT INTO poc_steps(step_id,plan_id,ordinal,intent) "
                "VALUES (%s,%s,1,'Re-evaluate reference document with independent verifier')",
                (new_fact.step_id,new_fact.plan_id),
            )
            cur.execute(
                "INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state) "
                "VALUES (%s,%s,1,'RUNNING')",(new_fact.attempt_id,new_fact.step_id),
            )
            cur.execute(
                """INSERT INTO poc_executions(execution_id,attempt_id,side_effect_class,state)
                   VALUES (%s,%s,'PURE','RUNNING')""",
                (second_exec,new_fact.attempt_id),
            )
            cur.execute(
                """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                   VALUES (%s,%s,3,'plan.replanned',%s::jsonb)""",
                (_id("event"),fact.run_id,json.dumps({
                    "plan_id":new_fact.plan_id,"version":2,
                    "parent_plan_id":fact.plan_id,
                    "step_id":new_fact.step_id,"attempt_id":new_fact.attempt_id,
                })),
            )
    return new_fact,second_exec


async def run_bounded_document_replan(ledger: TaskLedger) -> dict:
    fact=VerificationFact.example(passed=False,evidence_ref=None)
    execution_id=ledger.start(fact)
    failed=await run_document_case("buggy",fact)
    if failed.run_state!="FAILED" or failed.verification_state!="VERIFICATION_FAILURE":
        raise TaskFactConflict("Broken fixture was not independently rejected")
    replacement,second_exec=commit_verification_failure_and_replan(
        ledger,fact,execution_id,passed=False,evidence_ref=failed.evidence_ref)
    successful=await run_document_case("expected",replacement)
    if successful.run_state!="COMPLETED":
        raise TaskFactConflict("Second independent verification did not pass")
    ledger.finish(replacement,successful,second_exec)
    return ledger.read(fact.run_id)
