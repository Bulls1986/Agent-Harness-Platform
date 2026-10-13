"""DEV-M7 versioned public API facade, not the debug Inspector.

Trust identities only from external resolved Gateway state, receive current
Policy decisions by injection, own minimal PG Conversation/Turn metadata
and route READS of already persisted Run/TypedEvent/ArtifactRefs.
Actual Agent dispatch remains at existing Harness execution entrypoint.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time
from typing import Callable

from fastapi import Body, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from poc.closed_loop.facts import UnsafeDispatch
from poc.platform_access.authorized_reads import (
    RunBinding, RunReader, SecurityContext, create_read_app,
)
from poc.platform_access.conversation_pg import PgConversationStore


@dataclass(frozen=True)
class ConversationBinding:
    conversation_id: str
    project_scope: str
    initiator_principal_id: str


class NewConversation(BaseModel):
    title: str = Field(min_length=1,max_length=200)


class NewTurn(BaseModel):
    message: str = Field(min_length=1,max_length=8192)
    agent_ref: str = Field(min_length=1,max_length=256)
    recipe_ref: str = Field(min_length=1,max_length=256)


def create_platform_app(
    *,
    resolve_context: Callable,
    reader: RunReader,
    store: PgConversationStore,
    authorize: Callable,
    authorize_create: Callable,
    sse_max_polls: int = 20,
    cancel_run: Callable[[str],str] | None = None,
    start_run: Callable[[str,str,str],object] | None = None,
    model_binding: Callable[[],tuple[str,str|None]] | None = None,
    admit_recipe: Callable[[str,str],bool] | None = None,
):
    """Purely composed service-side adapters; no untrusted HTTP identity.

    External Gateway MUST perform real authentication/Policy; this layer only
    refuses missing/unscoped identities and enforces immutable PG ownership.
    """
    if (not isinstance(store,PgConversationStore)
            or not callable(authorize_create)
            or not 1 <= sse_max_polls <= 250):
        raise ValueError("Actual PG Conversation store and explicit Policy required")
    app=create_read_app(
        resolve_context=resolve_context,reader=reader,authorize=authorize,
    )
    app.title="Harness Public API (DEV-M7)"
    app.version="v1"
    require_run=app.state.require_run_access

    def identity(request:Request)->SecurityContext:
        try:ctx=resolve_context(request)
        except Exception:raise HTTPException(401,"Authentication required") from None
        if not isinstance(ctx,SecurityContext):
            raise HTTPException(401,"Authentication required")
        if not ctx.project_scope or not ctx.project_scope.strip():
            raise HTTPException(404,"Resource not found")
        return ctx

    def explicit(policy, *args):
        try:result=policy(*args)
        except Exception:raise HTTPException(503,"Authorization unavailable") from None
        if result is not True:
            raise HTTPException(404,"Resource not found")

    def check_run(request:Request,rid:str,action:str):
        ctx,binding=require_run(request,rid,action)
        # Even a compromised/careless project-wide adapter cannot release
        # another user's data. Cross-user service access must be deliberately
        # implemented in a separate, reviewed service-identity contract.
        if ctx.principal_type=="USER" and ctx.principal_id!=binding.initiator_principal_id:
            raise HTTPException(404,"Run not found")
        return ctx,binding

    def conversation_access(request:Request,cid:str,action:str)->ConversationBinding:
        ctx=identity(request)
        try:row=store.binding(cid)
        except KeyError:raise HTTPException(404,"Resource not found") from None
        except Exception:raise HTTPException(503,"Conversation unavailable") from None
        binding=ConversationBinding(cid,row["project_scope"],row["creator_principal_id"])
        if ctx.project_scope!=binding.project_scope or ctx.principal_id!=binding.initiator_principal_id:
            raise HTTPException(404,"Resource not found")
        explicit(authorize,ctx,binding,action)
        return binding

    @app.post("/api/v1/conversations",status_code=201)
    def new_conversation(body:NewConversation,request:Request):
        ctx=identity(request)
        explicit(authorize_create,ctx,"conversation.create")
        try:cid=store.create_conversation(ctx.project_scope,ctx.principal_id,body.title)
        except ValueError:raise HTTPException(422,"Invalid title") from None
        return {"conversation_id":cid}

    @app.get("/api/v1/conversations")
    def list_conversations(request:Request):
        ctx=identity(request)
        explicit(authorize_create,ctx,"conversation.list")
        return {"conversations":store.list_conversations(ctx.project_scope,ctx.principal_id)}

    @app.get("/api/v1/conversations/{conversation_id}")
    def conversation_detail(conversation_id:str,request:Request):
        conversation_access(request,conversation_id,"conversation.read")
        try:return store.conversation(conversation_id)
        except KeyError:raise HTTPException(404,"Resource not found") from None

    @app.post("/api/v1/conversations/{conversation_id}/turns",status_code=201)
    def new_turn(conversation_id:str,body:NewTurn,request:Request):
        conversation_access(request,conversation_id,"turn.create")
        try:tid=store.create_turn(conversation_id,body.message,body.agent_ref,body.recipe_ref)
        except ValueError:raise HTTPException(422,"Invalid Turn") from None
        return {"turn_id":tid,"conversation_id":conversation_id}

    @app.post("/api/v1/turns/{turn_id}/runs",status_code=202)
    def start_new_run(turn_id:str,request:Request,
                      idempotency_key:str|None=Header(None,alias="Idempotency-Key")):
        # The USER cannot choose raw Provider/Workflow IDs or rewrite a
        # previously frozen prompt/model. This reuses the M2/M3/M4 Run,
        # Outbox and real Hatchet execution entrypoint.
        ctx=identity(request)
        try:scope=store.turn_binding(turn_id)
        except KeyError:raise HTTPException(404,"Resource not found") from None
        conversation_access(request,scope["conversation_id"],"turn.run.create")
        if (not callable(start_run) or not callable(model_binding)
                or not callable(admit_recipe)):
            raise HTTPException(503,"Real Harness execution adapter unavailable")
        if (idempotency_key is None or len(idempotency_key)>128
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}",idempotency_key)):
            raise HTTPException(422,"Valid Idempotency-Key is required")
        try:agent_ref,recipe_ref=store.turn_selection(turn_id)
        except KeyError:raise HTTPException(404,"Resource not found") from None
        # A metadata label from the client is not execution authority. The
        # existing Runtime/Recipe adapter must explicitly support the frozen
        # Turn choice; otherwise do not allocate or dispatch any Run.
        explicit(admit_recipe,agent_ref,recipe_ref)
        try:
            mode,model_id=model_binding()
            rid,key,prompt,created=store.create_run_for_turn(
                turn_id,idempotency_key,project_scope=ctx.project_scope,
                principal_id=ctx.principal_id,model_mode=mode,model_id=model_id,
            )
        except KeyError:raise HTTPException(404,"Resource not found") from None
        except UnsafeDispatch:raise HTTPException(409,"Run binding conflict") from None
        except ValueError:raise HTTPException(422,"Invalid frozen Run model") from None
        except Exception:raise HTTPException(503,"Unable to persist Run") from None
        if created:
            try:
                start_run(rid,prompt,key)
            except Exception:
                # Submission ACK is uncertain. Return the durable Run ID,
                # then stop. Never dispatch again on HTTP retry.
                try:store.facts.report_execution_error(rid,"SUBMISSION_UNKNOWN")
                except Exception:pass
                raise HTTPException(503,detail={
                    "message":"Dispatch outcome uncertain; reconcile persisted Run",
                    "run_id":rid,
                }) from None
        state=store.facts.snapshot(rid)["state"]
        return {"run_id":rid,"turn_id":turn_id,"state":state,
                "replayed":not created,
                "needs_reconciliation":not created and state=="CREATED"}

    @app.post("/api/v1/turns/{turn_id}/runs/{run_id}")
    def attach_existing_run(turn_id:str,run_id:str,request:Request):
        ctx=identity(request)
        try:scope=store.turn_binding(turn_id)
        except KeyError:raise HTTPException(404,"Resource not found") from None
        conversation_access(request,scope["conversation_id"],"turn.run.attach")
        check_run(request,run_id,"run.attach")
        try:store.link_run(turn_id,run_id)
        except UnsafeDispatch as exc:
            if "already belongs" in str(exc):
                raise HTTPException(409,"Run already attached") from None
            raise HTTPException(404,"Resource not found") from None
        return {"turn_id":turn_id,"run_id":run_id}

    @app.get("/api/v1/runs/{run_id}")
    def versioned_run(run_id:str,request:Request):
        check_run(request,run_id,"run.read")
        try:return reader.snapshot(run_id)
        except KeyError:raise HTTPException(404,"Run not found") from None
        except Exception:raise HTTPException(503,"Run facts unavailable") from None

    @app.get("/api/v1/runs/{run_id}/events")
    def versioned_events(run_id:str,request:Request,
                         after:int=Query(0,ge=0),limit:int=Query(250,ge=1,le=250)):
        check_run(request,run_id,"run.events.read")
        try:events=reader.events_since(run_id,after,limit)
        except KeyError:raise HTTPException(404,"Run not found") from None
        except Exception:raise HTTPException(503,"Run events unavailable") from None
        return {"run_id":run_id,"events":events,
                "cursor":events[-1]["seq"] if events else after}

    @app.get("/api/v1/runs/{run_id}/stream")
    def authorized_stream(run_id:str,request:Request):
        # Validate both identity and cursor BEFORE streaming 200 response;
        # per-page revalidation handles Policy revocation during a live stream.
        check_run(request,run_id,"run.events.read")
        last=request.headers.get("last-event-id")
        if last is None:after=0
        elif (last.startswith(run_id+":")
              and re.fullmatch("[0-9]{1,18}",last[len(run_id)+1:])):
            after=int(last[len(run_id)+1:])
        else:raise HTTPException(422,"Invalid Last-Event-ID")
        def events():
            cursor=after
            for iteration in range(sse_max_polls):
                try:check_run(request,run_id,"run.events.read")
                except HTTPException:return
                try:batch=reader.events_since(run_id,cursor,250)
                except Exception:return
                for item in batch:
                    # Do not emit a new event if policy is revoked between
                    # batches. Payload is the PG-persisted typed Domain Event.
                    cursor=item["seq"]
                    yield ("id: "+run_id+":"+str(cursor)+"\n"
                           "event: "+str(item["type"])+"\n"
                           "data: "+json.dumps(item,ensure_ascii=False,
                                                separators=(",",":"))+"\n\n")
                if len(batch)<250 and iteration+1<sse_max_polls:
                    time.sleep(0.08)
        return StreamingResponse(events(),media_type="text/event-stream",
                                  headers={"Cache-Control":"no-store",
                                           "X-Accel-Buffering":"no"})

    @app.post("/api/v1/runs/{run_id}/cancel",status_code=202)
    def cancel_authorized_run(run_id:str,request:Request):
        check_run(request,run_id,"run.cancel")
        if not callable(cancel_run):
            raise HTTPException(503,"Cancel execution adapter unavailable")
        try:
            state=cancel_run(run_id)
        except UnsafeDispatch:
            raise HTTPException(409,"Run cannot be cancelled") from None
        except Exception:
            raise HTTPException(503,"Cancel request unavailable") from None
        if state!="CANCEL_REQUESTED":
            raise HTTPException(503,"Unexpected cancellation acknowledgement")
        # This API records the durable intent. Hatchet Worker/Cube physical
        # termination and domain CANCELLED require separate verified proof.
        return {"run_id":run_id,"state":"CANCEL_REQUESTED",
                "provider_terminated":False}

    @app.get("/api/v1/runs/{run_id}/artifacts")
    def artifacts(run_id:str,request:Request):
        check_run(request,run_id,"artifact.read")
        return {"run_id":run_id,"artifacts":store.artifacts_for_run(run_id)}

    @app.get("/api/v1/artifacts/{artifact_id}")
    def artifact(artifact_id:str,request:Request):
        # Read ONLY metadata. We never mint OSS URLs without a trusted
        # Storage Adapter plus independent identity/scope verification.
        try:info=store.artifact(artifact_id)
        except KeyError:raise HTTPException(404,"Resource not found") from None
        check_run(request,info["run_id"],"artifact.read")
        return info

    @app.get("/ui/conversations/{conversation_id}",response_class=HTMLResponse)
    def readable_conversation(conversation_id:str,request:Request):
        conversation_access(request,conversation_id,"conversation.read")
        # Static code only, with no untrusted text interpolated into HTML.
        # Browser uses same-origin cookies from the verified Gateway;
        # never reads principal or project values from request headers.
        cid=json.dumps(conversation_id)
        return HTMLResponse('''<!doctype html><html lang="zh"><meta charset="utf-8">
<title>Harness · 对话与执行结果</title>
<style>body{font:15px system-ui;max-width:940px;margin:3rem auto;color:#1d2433}
article{border:1px solid #ddd;border-radius:12px;padding:20px;margin:16px 0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f6f8;padding:12px}
small{color:#555}</style>
<h1>对话 · Agent 执行记录</h1><main id="timeline" aria-live="polite">正在读取授权会话…</main>
<script>
const cid='''+cid+''';
const root=document.querySelector("#timeline");
function node(tag,content,parent){const n=document.createElement(tag);
n.textContent=String(content??"");parent.appendChild(n);return n}
async function load(){
const response=await fetch("/api/v1/conversations/"+encodeURIComponent(cid),{credentials:"same-origin"});
if(!response.ok){root.textContent="会话不存在或没有访问权限";return}
const conversation=await response.json();root.replaceChildren();
node("h2",conversation.title,root);
for(const turn of conversation.turns){
 const a=node("article","",root);node("h3","第 "+turn.ordinal+" 轮 · "+turn.agent_ref,a);
 node("p",turn.message,a);node("small","执行配置："+turn.recipe_ref,a);
 for(const runId of turn.run_ids){
  const r=await fetch("/api/v1/runs/"+encodeURIComponent(runId),{credentials:"same-origin"});
  if(!r.ok){node("p","执行记录已不可访问",a);continue}
  const run=await r.json();node("h4","Run "+run.run_id+" · "+run.state,a);
  if(run.result){node("pre",run.result.final_output??JSON.stringify(run.result),a)}
  const ev=await fetch("/api/v1/runs/"+encodeURIComponent(runId)+"/events?limit=250",
   {credentials:"same-origin"});
  if(ev.ok){const list=await ev.json();for(const e of list.events){
    if(e.type==="response.output_text.delta")node("span",e.data.delta,a);
    if(e.type.startsWith("tool.")||e.type.startsWith("approval.")||
       e.type.startsWith("step."))node("p",e.type+" · "+JSON.stringify(e.data),a);
  }}
  const files=await fetch("/api/v1/runs/"+encodeURIComponent(runId)+"/artifacts",
   {credentials:"same-origin"});
  if(files.ok){const data=await files.json();for(const f of data.artifacts){
    node("p","附件："+f.artifact_id+" · "+f.media_type+" · "+f.size_bytes+" bytes",a);
  }}
 }
}}
load().catch(()=>{root.textContent="执行记录暂时不可用"});
</script></html>''')
    return app