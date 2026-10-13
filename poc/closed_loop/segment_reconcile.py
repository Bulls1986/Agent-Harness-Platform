"""DEV-M4 limited ACK-loss reconciliation against persisted Harness PG facts.

When a segment create was dispatched and the response was lost, NEVER retry
workflow creation automatically. A trusted Provider query may enumerate
native Runs by frozen command metadata. Exactly one fully correlated match
can restore the existing binding. Absent, conflicting, mismatched or
unavailable evidence stays BLOCKED_UNKNOWN. This is not a generic Receipt
or consumer-supplied workflow-id acceptance API.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from poc.closed_loop.facts import PgFacts, UnsafeDispatch


@dataclass(frozen=True)
class ProviderMatch:
    workflow_run_id: str
    command_key: str
    run_id: str
    plan_version: int


class SegmentReconciler:
    def __init__(self, facts: PgFacts):
        if not isinstance(facts, PgFacts):
            raise ValueError("Authoritative PostgreSQL facts required")
        self.facts = facts

    def reconcile_unknown(
        self,
        command_key: str,
        find_existing: Callable[[str], Sequence[ProviderMatch]],
    ) -> str:
        """Find exactly one native, correlated WorkflowRun; never trigger one.

        find_existing is a server-side trusted Process/Durable adapter that
        applies an actual native metadata query. It must never be sourced
        from client headers, model output, or unverified Workflow payload.
        """
        if not isinstance(command_key, str) or not command_key:
            raise UnsafeDispatch("Missing persisted command key")
        with self.facts.tx() as c:
            row = c.execute(
                "SELECT s.run_id,s.state,s.provider_workflow_id,"
                "s.from_provider_workflow_id,r.plan_version,r.state "
                "FROM harness_replan_segment_v2 AS s "
                "JOIN harness_run AS r ON r.id=s.run_id "
                "WHERE s.command_key=%s", (command_key,),
            ).fetchone()
        if not row:
            raise UnsafeDispatch("Unknown segment command")
        rid, state, bound, old, version, run_state = row
        if state == "CONFIRMED" and bound:
            # Idempotent repeat, never repeat the external lookup or creation.
            return bound
        if state != "BLOCKED_UNKNOWN" or bound is not None or version != 2 or run_state != "RUNNING":
            raise UnsafeDispatch("Reconciliation requires unresolved v2 command")

        try:
            matches = find_existing(command_key)
        except Exception:
            raise UnsafeDispatch("Provider metadata lookup unavailable; stay UNKNOWN") from None
        if (not isinstance(matches, (tuple, list)) or len(matches) != 1
                or not isinstance(matches[0], ProviderMatch)):
            raise UnsafeDispatch("Provider match is absent, ambiguous or unverified")
        evidence = matches[0]
        if (evidence.command_key != command_key or evidence.run_id != rid
                or evidence.plan_version != 2
                or not isinstance(evidence.workflow_run_id, str)
                or not evidence.workflow_run_id.strip()
                or evidence.workflow_run_id == old):
            raise UnsafeDispatch("Native Provider metadata mismatches frozen segment")

        with self.facts.tx() as c:
            # Lock Run before Segment, matching M3 Claim/Bind/Cancel and
            # avoiding opposing row lock order during late ACK reconciliation.
            c.execute("SELECT id FROM harness_run WHERE id=%s FOR UPDATE", (rid,))
            current = c.execute(
                "SELECT s.run_id,s.state,s.provider_workflow_id,"
                "s.from_provider_workflow_id,r.plan_version,r.state "
                "FROM harness_replan_segment_v2 AS s "
                "JOIN harness_run AS r ON r.id=s.run_id "
                "WHERE s.command_key=%s FOR UPDATE OF s", (command_key,),
            ).fetchone()
            if current and current[1] == "CONFIRMED" and current[2] == evidence.workflow_run_id:
                return evidence.workflow_run_id
            if current != (rid, "BLOCKED_UNKNOWN", None, old, 2, "RUNNING"):
                raise UnsafeDispatch("Concurrent owner/segment revision; do not alter binding")
            # Also require the frozen Plan and Provider lineage; a callback
            # result cannot promote a stale version or corrupt frozen facts.
            plan = c.execute(
                "SELECT recipe_digest,provider_workflow_id FROM harness_plan_snapshot "
                "WHERE run_id=%s AND version=2 FOR UPDATE", (rid,),
            ).fetchone()
            digest = c.execute(
                "SELECT intended_recipe_digest FROM harness_replan_intent "
                "WHERE run_id=%s AND from_version=1", (rid,),
            ).fetchone()
            if not plan or plan[1] is not None or not digest or plan[0] != digest[0]:
                raise UnsafeDispatch("Frozen Plan v2 facts are inconsistent")
            c.execute(
                "UPDATE harness_replan_segment_v2 SET state='CONFIRMED', "
                "provider_workflow_id=%s WHERE command_key=%s",
                (evidence.workflow_run_id, command_key),
            )
            c.execute(
                "UPDATE harness_plan_snapshot SET provider_workflow_id=%s "
                "WHERE run_id=%s AND version=2 AND provider_workflow_id IS NULL",
                (evidence.workflow_run_id, rid),
            )
            self.facts.event(c, rid, "workflow.segment.reconciled", {
                "version": 2, "command_key": command_key,
                "provider_workflow_run_id": evidence.workflow_run_id,
                "source": "native_provider_metadata_unique",
            })
        return evidence.workflow_run_id