import test from "node:test";
import assert from "node:assert/strict";
import { SyntheticHarnessConsumer, UnknownSubmissionOutcome } from "../integrations/synthetic_consumer.mjs";

function fixture(responses) {
  const calls=[];
  const transport=async (url, options)=>{
    calls.push({url,options});
    const next=responses.shift();
    if(next instanceof Error) throw next;
    return {ok:next.status>=200&&next.status<300,status:next.status,
      json:async()=>next.data,text:async()=>next.text??""};
  };
  return {calls,client:new SyntheticHarnessConsumer({
    baseUrl:"https://harness.example",identity:()=> "synthetic-gateway-token",transport,
  })};
}
const ok=(data,status=200)=>({status,data});
test("consumer uses only /api/v1 and authenticated scoped conversation -> turn -> Run",async()=>{
 const f=fixture([ok({conversation_id:"conv-1"},201),ok({turn_id:"turn-1",conversation_id:"conv-1"},201),ok({run_id:"run-1",turn_id:"turn-1",state:"CREATED"},202),ok({run_id:"run-1",state:"COMPLETED",result:{final_output:"ok"}})]);
 const cid=await f.client.createConversation("Synthetic example");
 const tid=await f.client.createTurn({conversationId:cid,message:"A synthetic request",agentRef:"test-agent@v1",recipeRef:"test-recipe@v1"});
 const r=await f.client.startRun({turnId:tid,idempotencyKey:"synthetic-key-1"});
 assert.equal(r.run_id,"run-1");
 assert.equal((await f.client.getRun("run-1")).state,"COMPLETED");
 assert.deepEqual(f.calls.map(c=>new URL(c.url).pathname),[
 "/api/v1/conversations","/api/v1/conversations/conv-1/turns","/api/v1/turns/turn-1/runs","/api/v1/runs/run-1"]);
 assert(f.calls.every(c=>c.options.headers.Authorization==="Bearer synthetic-gateway-token"));
 assert.equal(f.calls[2].options.headers["Idempotency-Key"],"synthetic-key-1");
});
test("event cursor and cancel only establish cancellation request",async()=>{
 const f=fixture([ok({run_id:"run-1",events:[{seq:4,type:"test.event"}],cursor:4}),
 ok({run_id:"run-1",state:"CANCEL_REQUESTED",provider_terminated:false},202)]);
 const page=await f.client.getEvents("run-1",{after:3,limit:2});
 assert.equal(page.cursor,4);
 assert.equal(f.calls[0].url,"https://harness.example/api/v1/runs/run-1/events?after=3&limit=2");
 const cancel=await f.client.requestCancel("run-1");
 assert.equal(cancel.state,"CANCEL_REQUESTED");
 assert.equal(cancel.provider_terminated,false);
});
test("fail closed on forged Run binding, bad version and missing scoped identity",async()=>{
 const f=fixture([ok({run_id:"other-run",state:"COMPLETED"})]);
 await assert.rejects(()=>f.client.getRun("run-1"),/binding/i);
 await assert.rejects(()=>f.client.getRun("../admin"),/invalid/i);
 assert.throws(()=>new SyntheticHarnessConsumer({baseUrl:"http://remote.example",identity:()=> "token"}),/HTTPS/);
 assert.throws(()=>new SyntheticHarnessConsumer({baseUrl:"https://harness.example/api/v2",identity:()=> "token"}),/base URL/i);
 const missing=new SyntheticHarnessConsumer({baseUrl:"https://harness.example",identity:()=>"",transport:()=>{throw new Error("must not execute");}});
 await assert.rejects(()=>missing.createConversation("Synthetic"),/identity/i);
});
test("cross-scope 404 and revoked 403 deny data, no response body leaks",async()=>{
 for(const status of [401,403,404]) {
  const f=fixture([ok({sensitive:"should not expose"},status)]);
  await assert.rejects(()=>f.client.getRun("run-1"),e=>e.message.includes(String(status))&&!e.message.includes("sensitive"));
 }
});
test("submission transport loss and 503 never silently retry or claim success",async()=>{
 const f=fixture([new Error("connection reset")]);
 await assert.rejects(()=>f.client.startRun({turnId:"turn-1",idempotencyKey:"retry-key-1"}),UnknownSubmissionOutcome);
 assert.equal(f.calls.length,1);
 const g=fixture([ok({detail:{message:"Dispatch outcome uncertain; reconcile persisted Run",run_id:"run-1"}},503)]);
 await assert.rejects(()=>g.client.startRun({turnId:"turn-1",idempotencyKey:"retry-key-1"}),UnknownSubmissionOutcome);
 assert.equal(g.calls.length,1);
});
test("bad response cursor and mismatched turn Run are never accepted",async()=>{
 const f=fixture([ok({run_id:"run-1",turn_id:"turn-other",state:"CREATED"},202)]);
 await assert.rejects(()=>f.client.startRun({turnId:"turn-1",idempotencyKey:"abc123"}),UnknownSubmissionOutcome);
 const g=fixture([ok({run_id:"run-1",events:[{seq:7}],cursor:6})]);
 await assert.rejects(()=>g.client.getEvents("run-1",{after:0}),/cursor/);
});

test("SSE stream follows persisted Last-Event-ID and validates each event binding",async()=>{
 const f=fixture([{status:200,text:'id: run-1:2\nevent: response.output_text.delta\ndata: {"seq":2,"type":"response.output_text.delta","data":{"delta":"hello"}}\n\n'}]);
 const page=await f.client.getStreamEvents("run-1",{after:1});
 assert.equal(page.cursor,2);
 assert.equal(page.events[0].data.data.delta,"hello");
 assert.equal(f.calls[0].options.headers["Last-Event-ID"],"run-1:1");
 const g=fixture([{status:200,text:'id: forged:3\nevent: a\ndata: {}\n\n'}]);
 await assert.rejects(()=>g.client.getStreamEvents("run-1",{after:2}),/SSE binding/);
});
