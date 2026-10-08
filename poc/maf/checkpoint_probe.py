"""A25 public MAF Workflow FileCheckpointStorage capability probe.

File storage is official *single-machine/development* infrastructure only.
Never accept checkpoint IDs/paths from untrusted callers. Python checkpoint
stores may deserialize via restricted pickle; storage directory is private.
The platform never parses, translates or reimplements checkpoint data.
"""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
from typing import Never

from agent_framework import Executor, FileCheckpointStorage, WorkflowBuilder, WorkflowContext, handler


WORKFLOW_NAME = "maf-poc-a25-checkpoint-v1"
PREPARE_CALLS = 0


class PrepareExecutor(Executor):
    @handler
    async def prepare(self, value: str, ctx: WorkflowContext[str]) -> None:
        global PREPARE_CALLS
        PREPARE_CALLS += 1
        if value != "trusted-input":
            raise ValueError("bad fixture input")
        await ctx.send_message("prepared")


class CompleteExecutor(Executor):
    @handler
    async def complete(self, value: str, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output("done:" + value)


def build(storage: FileCheckpointStorage):
    a = PrepareExecutor(id="prepare")
    b = CompleteExecutor(id="complete")
    return (WorkflowBuilder(
        name=WORKFLOW_NAME, start_executor=a, checkpoint_storage=storage
    ).add_edge(a,b).build())


async def save(directory: Path) -> dict:
    storage = FileCheckpointStorage(str(directory / 'native-checkpoints'))
    workflow = build(storage)
    events = []
    async for event in workflow.run("trusted-input", stream=True):
        events.append(event.type)
    checkpoints = await storage.list_checkpoints(workflow_name=workflow.name)
    if len(checkpoints) < 3:
        raise RuntimeError(f"Expected entry, first-superstep and terminal checkpoints; got {len(checkpoints)}")
    # FileCheckpointStorage.list_checkpoints() is not ordered. Pick the unique
    # lineage tip and its predecessor using only PUBLIC checkpoint metadata.
    # Never guess ordering by array index, iteration_count, or filename.
    by_id = {cp.checkpoint_id: cp for cp in checkpoints}
    parents = {cp.previous_checkpoint_id for cp in checkpoints
               if cp.previous_checkpoint_id is not None}
    tips = [cp for cp in checkpoints if cp.checkpoint_id not in parents]
    if len(tips) != 1 or tips[0].previous_checkpoint_id not in by_id:
        raise RuntimeError("Checkpoint lineage incomplete or ambiguous")
    checkpoint = by_id[tips[0].previous_checkpoint_id]
    manifest = {"checkpoint_id":checkpoint.checkpoint_id, "workflow":WORKFLOW_NAME}
    (directory/"probe-manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
    return {"checkpoint_count":len(checkpoints),"streaming_events":len(events),"saved":True}


async def restore(directory: Path) -> dict:
    manifest = json.loads((directory/"probe-manifest.json").read_text(encoding="utf-8"))
    if manifest["workflow"] != WORKFLOW_NAME:
        raise ValueError("Workflow identity mismatch")
    storage = FileCheckpointStorage(str(directory / 'native-checkpoints'))
    known = await storage.list_checkpoints(workflow_name=WORKFLOW_NAME)
    if manifest["checkpoint_id"] not in {c.checkpoint_id for c in known}:
        raise ValueError("Checkpoint missing from provider storage")
    # Reconstruct the exact same workflow identity and let MAF rehydrate.
    workflow = build(storage)
    outputs = []
    async for event in workflow.run(
        checkpoint_id=manifest["checkpoint_id"], checkpoint_storage=storage, stream=True
    ):
        if event.type == "output":
            outputs.append(event.data)
    return {"resumed":outputs == ["done:prepared"],"outputs":len(outputs),
            "prepare_reexecuted": PREPARE_CALLS != 0,"checkpoint_native":True}


def main() -> int:
    parser=argparse.ArgumentParser()
    actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--save",type=Path)
    actions.add_argument("--restore",type=Path)
    args=parser.parse_args()
    if args.save:
        args.save.mkdir(parents=True,exist_ok=True)
    result=asyncio.run(save(args.save) if args.save else restore(args.restore))
    print(json.dumps(result,sort_keys=True))
    return 0 if (result.get("saved") or result.get("resumed")) and not result.get("prepare_reexecuted") else 1


if __name__=="__main__":
    raise SystemExit(main())
