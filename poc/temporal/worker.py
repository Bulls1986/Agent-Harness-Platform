"""Run real Temporal SDK Worker in an independent OS process."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from temporalio.client import Client
from temporalio.worker import Worker

sys.path.insert(0, str(Path(__file__).resolve().parent))
from activities import fixture_agent_execute, independent_document_verify
from workflow import DocumentReviewWorkflow


async def main() -> None:
    address=os.environ.get("POC_C_TEMPORAL_ADDRESS","127.0.0.1:17233")
    queue=os.environ["POC_C_TASK_QUEUE"]
    client=await Client.connect(address)
    if os.environ.get("POC_C_GUARDED")=="1":
        from guarded_workflow import GuardedNonRetryableWorkflow
        from guarded_tool import guarded_tool, pure_retry_probe
        workflows=[GuardedNonRetryableWorkflow]
        activities=[guarded_tool,pure_retry_probe]
    elif os.environ.get("POC_C_LIVE_PROTOCOL")=="1":
        from live_g3_workflow import LiveStreamWorkflow
        from live_g3_activities import (stream_model,write_s3_artifact,
                                        verify_s3_artifact,verify_tokens,finish)
        workflows=[LiveStreamWorkflow]
        activities=[stream_model,write_s3_artifact,verify_s3_artifact,verify_tokens,finish]
    elif os.environ.get("POC_C_REAL_SWAP")=="1":
        from runtime_swap_workflow import RealRuntimeSwapWorkflow
        from runtime_swap_activities import (run_real_agent,verify_runtime_model,
                                              finalize_runtime_swap)
        workflows=[RealRuntimeSwapWorkflow]
        activities=[run_real_agent,verify_runtime_model,finalize_runtime_swap]
    else:
        workflows=[DocumentReviewWorkflow]
        activities=[fixture_agent_execute,independent_document_verify]
    worker=Worker(client,task_queue=queue,workflows=workflows,activities=activities)
    # READY means the Worker has been constructed; successful dispatch and
    # query are checked independently by the controller, not inferred from it.
    print("TEMPORAL_WORKER_READY",flush=True)
    await worker.run()


if __name__=="__main__":
    asyncio.run(main())