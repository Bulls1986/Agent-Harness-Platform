"""G2/G6 native MAF start ACK uncertainty: one dispatch and fail-closed.

The trusted Adapter passes a *single* official /run callback which returns
the provider's native_instance_id. This coordinator NEVER discovers an ID by
guessing TaskHub internals and NEVER invokes /run again after an uncertain ACK.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from durable_launch_intent import DurableLaunchIntentStore, NativeLaunchIntent
from durable_running_binding import DurableRunningBindingStore, RunningNativeBinding


@dataclass(frozen=True)
class NativeStartOutcome:
    state: str
    execution_id: str
    native_instance_id: str | None = None


class NativeStartAckCoordinator:
    def __init__(self, dsn: str):
        self.intents = DurableLaunchIntentStore(dsn)
        self.bindings = DurableRunningBindingStore(dsn)

    def start_once(self, intent: NativeLaunchIntent, *,
                   native_start: Callable[[], str]) -> NativeStartOutcome:
        """Persist-before-start. No exception path can authorize a second call.

        If the native instance was created but the response/bind ACK vanished,
        only a trusted provider GET/inspection can establish its true state.
        """
        self.intents.prepare(intent)  # durable PG fact precedes external POST
        try:
            instance_id = native_start()
            if not isinstance(instance_id,str) or not re.fullmatch("[0-9a-f]{32}",instance_id):
                raise ValueError("No valid official native instance ID")
            binding = RunningNativeBinding(
                run_id=intent.run_id, step_id=intent.step_id,
                attempt_id=intent.attempt_id, execution_id=intent.execution_id,
                native_instance_id=instance_id,
                native_workflow_name=intent.native_workflow_name,
                frozen_workflow_version=intent.frozen_workflow_version,
                frozen_runtime_version=intent.frozen_runtime_version,
            )
            self.bindings.bind(binding)
        except Exception:
            # The HTTP send or PG bind could have succeeded before the
            # exception. No blind replay, no new Attempt. Quarantine itself
            # must be committed; a PG outage is an explicit hard failure.
            self.intents.quarantine_unbound(intent)
            return NativeStartOutcome("UNKNOWN_RECONCILIATION_PENDING", intent.execution_id)
        return NativeStartOutcome("BOUND",intent.execution_id,instance_id)
