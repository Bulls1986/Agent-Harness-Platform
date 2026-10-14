/**
 * DEV-M8 generic, synthetic consumer of the published Harness /api/v1 HTTP
 * boundary. No platform imports, internal DB/queue access or private business
 * identifiers. Token must be supplied by a trusted external test Gateway.
 */
const REF=/^[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}$/;
const KEY=/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const check=(x,name,pat=REF)=>{
 if(typeof x!=="string"||!pat.test(x)) throw new TypeError("invalid "+name);
 return x;
};
export class UnknownSubmissionOutcome extends Error {
 constructor(){super("Harness submission outcome unknown; reconcile by durable Turn and Idempotency-Key before retry");this.name="UnknownSubmissionOutcome";}
}
export class SyntheticHarnessConsumer {
 constructor({baseUrl,identity,transport=fetch,timeoutMs=30000}={}) {
  if(typeof baseUrl!=="string"||typeof identity!=="function"||typeof transport!=="function")
    throw new TypeError("public base URL, trusted identity and HTTP transport required");
  const url=new URL(baseUrl);
  if(url.username||url.password||url.search||url.hash||url.pathname!=="/")
    throw new TypeError("Harness base URL must not include credentials, path, query or fragment");
  const local=["localhost","127.0.0.1","[::1]","::1"].includes(url.hostname);
  if(url.protocol!=="https:"&&!(local&&url.protocol==="http:"))
    throw new Error("Harness consumer requires HTTPS except loopback tests");
  if(!Number.isSafeInteger(timeoutMs)||timeoutMs<1)throw new TypeError("invalid timeout");
  this.baseUrl=url.origin;this.identity=identity;this.transport=transport;this.timeoutMs=timeoutMs;
 }
 async #request(method,path,{body,key,submission=false}={}) {
  const token=await this.identity();
  if(typeof token!=="string"||!token.trim()||/[\r\n]/.test(token))
    throw new Error("trusted identity required; no anonymous fallback");
  const headers={Accept:"application/json",Authorization:"Bearer "+token};
  if(body!==undefined)headers["Content-Type"]="application/json";
  if(key!==undefined)headers["Idempotency-Key"]=check(key,"Idempotency-Key",KEY);
  let resp;
  try {
   resp=await this.transport(this.baseUrl+"/api/v1"+path,{
    method,headers,signal:AbortSignal.timeout(this.timeoutMs),
    ...(body===undefined?{}:{body:JSON.stringify(body)}),
   });
  }catch(e){if(submission)throw new UnknownSubmissionOutcome();throw new Error("Harness transport unavailable");}
  if(!resp?.ok) {
   if(submission&&resp?.status>=500)throw new UnknownSubmissionOutcome();
   throw new Error("Harness rejected request with status "+(resp?.status??"unknown"));
  }
  try{return await resp.json();}
  catch {if(submission)throw new UnknownSubmissionOutcome();throw new Error("invalid public API response");}
 }
 async createConversation(title) {
  if(typeof title!=="string"||!title.trim()||title.length>200)throw new TypeError("invalid title");
  const r=await this.#request("POST","/conversations",{body:{title}});
  return check(r?.conversation_id,"conversation binding");
 }
 async createTurn({conversationId,message,agentRef,recipeRef}={}) {
  check(conversationId,"conversationId");
  check(agentRef,"agentRef");
  check(recipeRef,"recipeRef");
  if(typeof message!=="string"||!message.trim()||message.length>8192)throw new TypeError("invalid message");
  const r=await this.#request("POST","/conversations/"+conversationId+"/turns",{
    body:{message,agent_ref:agentRef,recipe_ref:recipeRef},
  });
  if(r?.conversation_id!==conversationId)throw new Error("Conversation binding mismatch");
  return check(r?.turn_id,"turn binding");
 }
 async startRun({turnId,idempotencyKey}={}) {
  check(turnId,"turnId");check(idempotencyKey,"Idempotency-Key",KEY);
  const r=await this.#request("POST","/turns/"+turnId+"/runs",{key:idempotencyKey,submission:true});
  if(r?.turn_id!==turnId)throw new UnknownSubmissionOutcome();
  check(r?.run_id,"runId");
  return r;
 }
 async getRun(runId) {
  check(runId,"runId");
  const r=await this.#request("GET","/runs/"+runId);
  if(r?.run_id!==runId)throw new Error("Run binding mismatch");
  return r;
 }
 async getEvents(runId,{after=0,limit=250}={}) {
  check(runId,"runId");
  if(!Number.isSafeInteger(after)||after<0||!Number.isSafeInteger(limit)||limit<1||limit>250)
    throw new TypeError("invalid event cursor or page limit");
  const r=await this.#request("GET","/runs/"+runId+"/events?after="+after+"&limit="+limit);
  if(r?.run_id!==runId||!Array.isArray(r.events)||!Number.isSafeInteger(r.cursor))
    throw new Error("Run event binding/cursor mismatch");
  let cursor=after;
  for(const event of r.events) {
   if(!Number.isSafeInteger(event?.seq)||event.seq<=cursor)
    throw new Error("non-monotonic event cursor");
   cursor=event.seq;
  }
  if(r.cursor!==cursor)throw new Error("event cursor mismatch");
  return r;
 }
 async getStreamEvents(runId,{after=0}={}) {
  check(runId,"runId");
  if(!Number.isSafeInteger(after)||after<0)throw new TypeError("invalid SSE cursor");
  const token=await this.identity();
  if(typeof token!=="string"||!token.trim()||/[\r\n]/.test(token))
   throw new Error("trusted identity required");
  const response=await this.transport(this.baseUrl+"/api/v1/runs/"+runId+"/stream",{
   method:"GET",signal:AbortSignal.timeout(this.timeoutMs),
   headers:{Accept:"text/event-stream",Authorization:"Bearer "+token,"Last-Event-ID":runId+":"+after},
  });
  if(!response?.ok)throw new Error("Harness SSE rejected request: status "+(response?.status??"unknown"));
  const raw=await response.text();
  if(typeof raw!=="string"||raw.length>1_000_000)throw new Error("invalid SSE response size");
  let cursor=after;
  const events=[];
  for(const block of raw.replace(/\r\n/g,"\n").split("\n\n")) {
   if(!block.trim())continue;
   const lines=block.split("\n");
   const id=lines.find(l=>l.startsWith("id: "))?.slice(4);
   const eventType=lines.find(l=>l.startsWith("event: "))?.slice(7);
   const json=lines.find(l=>l.startsWith("data: "))?.slice(6);
   const match=id?.match(/^([^:]+):([0-9]+)$/);
   const n=match?Number(match[2]):NaN;
   if(!match||match[1]!==runId||!Number.isSafeInteger(n)||n<=cursor||!eventType||!json)
    throw new Error("SSE binding/cursor mismatch");
   let data;
   try{data=JSON.parse(json);}catch{throw new Error("invalid SSE JSON");}
   if(data?.seq!==n||data?.type!==eventType)throw new Error("SSE binding/type mismatch");
   events.push({id,type:eventType,data});cursor=n;
  }
  return {runId,events,cursor};
 }
 async requestCancel(runId) {
  check(runId,"runId");
  const r=await this.#request("POST","/runs/"+runId+"/cancel");
  if(r?.run_id!==runId||r.state!=="CANCEL_REQUESTED"||r.provider_terminated!==false)
    throw new Error("cancellation acknowledgement mismatch");
  return r;
 }
}
