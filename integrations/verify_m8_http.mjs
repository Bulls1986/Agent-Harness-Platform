/**
 * DEV-M8 live network smoke: separate Node consumer against actual M7 FastAPI
 * + Harness PG + Hatchet. All identities, inputs and project scopes synthetic.
 * Does NOT claim an enterprise IdP or production provider cancellation.
 */
import assert from "node:assert/strict";
import { SyntheticHarnessConsumer } from "./synthetic_consumer.mjs";
const baseUrl=process.env.M8_SYNTHETIC_API_URL;
if(!baseUrl)throw new Error("M8_SYNTHETIC_API_URL required");
const c=new SyntheticHarnessConsumer({baseUrl,identity:()=>"synthetic-m8-primary"});
const other=new SyntheticHarnessConsumer({baseUrl,identity:()=>"synthetic-m8-other"});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const conv=await c.createConversation("M8 synthetic public API integration");
const selection={conversationId:conv,agentRef:"m8-test-agent@v1",recipeRef:"m8-test-recipe@v1"};
const turn=await c.createTurn({...selection,message:"Review a synthetic acceptance scenario"});
const key="m8-native-"+Date.now();
const started=await c.startRun({turnId:turn,idempotencyKey:key});
const replay=await c.startRun({turnId:turn,idempotencyKey:key});
assert.equal(started.run_id,replay.run_id);
assert.equal(replay.replayed,true);
let result;
for(let i=0;i<200;i++){
 result=await c.getRun(started.run_id);
 if(["COMPLETED","FAILED","CANCELLED","BLOCKED_UNKNOWN"].includes(result.state))break;
 await sleep(500);
}
assert.equal(result?.state,"COMPLETED","Native Run must actually complete");
assert(result?.provider_workflow_run_id,"Native workflow identity is required");
assert(result?.outbox==="CONFIRMED","Native dispatch receipt must be confirmed");
const events=await c.getEvents(started.run_id,{after:0,limit:250});
assert(events.events.length>0,"Persisted events required");
const stream=await c.getStreamEvents(started.run_id,{after:0});
assert(stream.events.length>0,"Authorized SSE events required");
const resumed=await c.getStreamEvents(started.run_id,{after:stream.cursor});
assert.equal(resumed.events.length,0,"SSE cursor resume must not replay");
await assert.rejects(()=>other.getRun(started.run_id),/404/);
await assert.rejects(()=>other.getEvents(started.run_id),/404/);
await assert.rejects(()=>other.getStreamEvents(started.run_id),/404/);
const cancelTurn=await c.createTurn({...selection,message:"M8 synthetic cancellation in progress"});
const cancelStart=await c.startRun({turnId:cancelTurn,idempotencyKey:key+"-cancel"});
const intent=await c.requestCancel(cancelStart.run_id);
assert.equal(intent.state,"CANCEL_REQUESTED");
assert.equal(intent.provider_terminated,false);
assert.equal((await c.getRun(cancelStart.run_id)).state,"CANCEL_REQUESTED");
console.log(JSON.stringify({
 gate:"DEV_M8_GENERIC_EXTERNAL_CLIENT_REAL_HTTP",
 result:"PASS",runtime:"REAL_HATCHET_TWO_SDK",
 public_api:"REAL_HTTP_FASTAPI",storage:"REAL_POSTGRESQL",
 identity:"SYNTHETIC_TRUST_ADAPTER_NOT_ENTERPRISE_IAM",
 cancel:"REAL_PG_INTENT_SYNTHETIC_HELD_PROVIDER_NOT_NATIVE_TERMINATION",
 workflow_run_id:result.provider_workflow_run_id,
 run_id:started.run_id,events:events.events.length,
}));
