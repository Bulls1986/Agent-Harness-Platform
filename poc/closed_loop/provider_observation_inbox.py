"""DEV-M4 HC-02: durable Provider Observation Inbox for the existing PG Run.

Not a Scheduler, tool runner, user-facing API or replacement for Hatchet.
Only a trusted Provider adapter may submit observations. Provider success
is evidence for reconciliation, NEVER authorization for Run.Completed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from poc.closed_loop.facts import PgFacts, UnsafeDispatch


@dataclass(frozen=True)
class Observation:
    run_id: str
    plan_version: int
    provider_workflow_id: str
    provider_task_ref: str
    native_event_key: str
    source_sequence: int
    provider_state: str
    result_digest: str


class ProviderObservationInbox:
    def __init__(self, facts: PgFacts):
        if not isinstance(facts, PgFacts):
            raise ValueError("Harness PostgreSQL authority is required")
        self.facts = facts
        self.init_schema()

    def init_schema(self):
        with self.facts.tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_provider_observation_inbox (
                    run_id TEXT NOT NULL REFERENCES harness_run(id),
                    plan_version INTEGER NOT NULL CHECK (plan_version >= 1),
                    provider_workflow_id TEXT NOT NULL,
                    provider_task_ref TEXT NOT NULL,
                    native_event_key TEXT NOT NULL,
                    source_sequence BIGINT NOT NULL CHECK (source_sequence >= 1),
                    provider_state TEXT NOT NULL,
                    result_digest TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (run_id, plan_version, provider_workflow_id,
                                 provider_task_ref, native_event_key),
                    UNIQUE (run_id, plan_version, provider_workflow_id,
                            provider_task_ref, source_sequence)
                )
            """)

    @staticmethod
    def _validate(o: Observation) -> None:
        if not isinstance(o, Observation):
            raise ValueError("Typed trusted Provider observation required")
        for value in (o.run_id,o.provider_workflow_id,o.provider_task_ref,
                      o.native_event_key,o.result_digest):
            if (not isinstance(value,str) or not value
                    or len(value) > 256 or value != value.strip()):
                raise ValueError("Incomplete or unbounded Provider observation")
        if (type(o.plan_version) is not int or o.plan_version < 1
                or type(o.source_sequence) is not int
                or not 1 <= o.source_sequence < 2**63
                or o.provider_state not in ("RUNNING","SUCCEEDED","FAILED","CANCELLED")):
            raise ValueError("Invalid Provider version, order or state")

    def observe(self, observation: Observation) -> str:
        self._validate(observation)
        o=observation
        payload=json.dumps({
            "run_id":o.run_id, "plan_version":o.plan_version,
            "provider_workflow_id":o.provider_workflow_id,
            "provider_task_ref":o.provider_task_ref,
            "native_event_key":o.native_event_key,
            "source_sequence":o.source_sequence,
            "provider_state":o.provider_state,
            "result_digest":o.result_digest,
        },sort_keys=True,separators=(",",":"))
        fingerprint=hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with self.facts.tx() as c:
            # The Run is the lock root shared by Cancel, Replan, Receipt
            # reconciliation and event sequencing. Never lock Inbox first.
            run=c.execute(
                "SELECT state,plan_version,provider_workflow_id "
                "FROM harness_run WHERE id=%s FOR UPDATE", (o.run_id,),
            ).fetchone()
            if not run:
                raise UnsafeDispatch("Unknown Platform Run")
            existing=c.execute(
                "SELECT payload_hash FROM harness_provider_observation_inbox "
                "WHERE run_id=%s AND plan_version=%s "
                "AND provider_workflow_id=%s AND provider_task_ref=%s "
                "AND native_event_key=%s",
                (o.run_id,o.plan_version,o.provider_workflow_id,
                 o.provider_task_ref,o.native_event_key),
            ).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise UnsafeDispatch("Conflicting native Provider event identity")
                return "ALREADY_APPLIED"

            if run[0] != "RUNNING" or run[1] != o.plan_version:
                raise UnsafeDispatch("Terminal or obsolete Run cannot project Provider event")
            if o.plan_version == 1:
                bound = run[2] == o.provider_workflow_id
            else:
                segment=c.execute(
                    "SELECT provider_workflow_id,state "
                    "FROM harness_replan_segment_v2 WHERE run_id=%s",
                    (o.run_id,),
                ).fetchone() if c.execute(
                    "SELECT to_regclass('harness_replan_segment_v2') IS NOT NULL"
                ).fetchone()[0] else None
                bound = segment == (o.provider_workflow_id,"CONFIRMED")
            if not bound:
                raise UnsafeDispatch("Unbound/stale Provider cannot project")

            last=c.execute(
                "SELECT MAX(source_sequence) FROM harness_provider_observation_inbox "
                "WHERE run_id=%s AND plan_version=%s "
                "AND provider_workflow_id=%s AND provider_task_ref=%s",
                (o.run_id,o.plan_version,o.provider_workflow_id,o.provider_task_ref),
            ).fetchone()[0]
            if last is not None and o.source_sequence <= last:
                raise UnsafeDispatch("Delayed or conflicting native Provider sequence")

            c.execute(
                "INSERT INTO harness_provider_observation_inbox "
                "(run_id,plan_version,provider_workflow_id,provider_task_ref,"
                "native_event_key,source_sequence,provider_state,result_digest,payload_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (o.run_id,o.plan_version,o.provider_workflow_id,o.provider_task_ref,
                 o.native_event_key,o.source_sequence,o.provider_state,
                 o.result_digest,fingerprint),
            )
            PgFacts.event(c,o.run_id,"provider.observed",{
                "plan_version":o.plan_version,
                "provider_workflow_run_id":o.provider_workflow_id,
                "provider_task_ref":o.provider_task_ref,
                "native_event_key":o.native_event_key,
                "source_sequence":o.source_sequence,
                "provider_state":o.provider_state,
                "result_digest":o.result_digest,
            })
        return "APPLIED"