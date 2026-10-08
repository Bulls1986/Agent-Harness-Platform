"""A40 MAF Workflow AgentExecutor + external SDK public-interface contract.

No real provider used here. Real model evidence comes ONLY from the live driver.
"""
import asyncio
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from agent_framework import AgentResponse,BaseAgent,Message
from maf_sdk_swap import (
    AgentSdkBridge,ComparisonOutcome,SwapContract,
    build_workflow,extract_marker,run_comparison,
)


class OfflineAgent(BaseAgent):
    def __init__(self,name:str, answer:str|None=None):
        super().__init__(id=name,name=name)
        self.answer=answer
        self.calls=0
    async def run(self,messages=None,*,stream=False,session=None,
                  function_invocation_kwargs=None,client_kwargs=None):
        if stream:raise NotImplementedError
        self.calls+=1
        text=(messages if isinstance(messages,str) else
              "\n".join(m.text for m in messages))
        result=self.answer if self.answer is not None else text
        return AgentResponse(messages=[Message(role="assistant",contents=[result])],
                             agent_id=self.id)


class AgentSdkSwapMAFTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_real_maf_agentexecutors_and_independent_verifiers(self):
        c=SwapContract.build()
        a=OfflineAgent("maf")
        b=OfflineAgent("external")
        outcome=await run_comparison(a,b,c)
        self.assertEqual(outcome.state,"COMPLETED")
        self.assertEqual([f.adapter for f in outcome.facts],["maf-harness","openai-agents"])
        self.assertEqual([f.attempt_id for f in outcome.facts],
                         [s.attempt_id for s in c.steps])
        self.assertEqual((a.calls,b.calls),(1,1))
        self.assertEqual([f.passed for f in outcome.facts],[True,True])

    async def test_first_verification_rejects_without_running_external_sdk(self):
        c=SwapContract.build()
        a=OfflineAgent("maf",answer="unrelated")
        b=OfflineAgent("external")
        with self.assertRaises(ValueError):
            await run_comparison(a,b,c)
        self.assertEqual(a.calls,1)
        self.assertEqual(b.calls,0)

    async def test_second_verification_rejects_no_success(self):
        c=SwapContract.build()
        a=OfflineAgent("maf")
        b=OfflineAgent("external",answer="unrelated")
        with self.assertRaises(ValueError):
            await run_comparison(a,b,c)
        self.assertEqual((a.calls,b.calls),(1,1))

    async def test_adapter_is_real_maf_protocol_and_has_explicit_stream_gap(self):
        c=SwapContract.build()
        external=AgentSdkBridge(model="fixture",endpoint="http://127.0.0.1:1/v1",
                                api_key="not-a-real-secret")
        self.assertEqual(external.name,"c09-openai-agents-sdk")
        with self.assertRaises(NotImplementedError):
            await external.run(c.prompt,stream=True)

    async def test_bad_marker_is_not_accepted(self):
        self.assertEqual(extract_marker("C09-1234"),"")
        self.assertEqual(extract_marker("C09-FFFFFFFF C09-AAAAAAAA"),"")
        self.assertEqual(extract_marker("C09-12345678"),"C09-12345678")


if __name__=="__main__":unittest.main()
