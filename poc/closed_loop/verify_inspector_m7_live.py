"""Black-box Inspector Capability Tab M7 scenario against live Hatchet + PG.

Requires the real local Inspector server with HARNESS_INSPECTOR_M7_DEMO_ENABLED=1.
This deliberately uses actual HTTP routes mounted from DEV-M7 Public API,
rather than the original Inspector /api/runs debug-only launch endpoint.
"""
from __future__ import annotations
import json
import time
from uuid import uuid4
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def request(url: str, method: str="GET", payload: dict|None=None,
            headers: dict|None=None) -> tuple[int,dict]:
    encoded=(json.dumps(payload).encode("utf-8") if payload is not None else None)
    meta=dict(headers or {})
    if payload is not None:meta["Content-Type"]="application/json"
    try:
        with urlopen(Request(url,data=encoded,headers=meta,method=method),timeout=30) as res:
            return res.status,json.loads(res.read())
    except HTTPError as exc:
        return exc.code,json.loads(exc.read())


def verify(url: str="http://127.0.0.1:8765") -> dict:
    url=url.rstrip("/")
    cap_status,catalog=request(url+"/api/verification/scenarios")
    assert cap_status==200
    scenario=next(s for s in catalog["scenarios"] if s["id"]=="public-api-agent-run")
    assert scenario["availability"]=="EXECUTABLE_M7_CAPABILITY_TAB",catalog
    assert catalog["production_ready"] is False
    with urlopen(url+"/",timeout=10) as response:
        html=response.read().decode("utf-8")
    assert 'id="m7-capability-demo"' in html
    assert 'id="m7-start"' in html
    assert 'const m7Base="/m7-demo/api/v1"' in html
    assert html.count('role="tab"')==2

    base=url+"/m7-demo/api/v1"
    status,conv=request(base+"/conversations","POST",{
        "title":"Inspector M7 real public API "+uuid4().hex
    })
    assert status==201,conv
    cid=conv["conversation_id"]
    status,turn=request(base+f"/conversations/{cid}/turns","POST",{
        "message":"Review a synthetic product requirement using M7 real API",
        "agent_ref":"dual-sdk-requirements-review@v1",
        "recipe_ref":"requirements-review@v1",
    })
    assert status==201,turn
    tid=turn["turn_id"]
    key="inspector-m7-"+uuid4().hex
    path=base+f"/turns/{tid}/runs"
    status,first=request(path,"POST",headers={"Idempotency-Key":key})
    assert status==202,first
    status,repeated=request(path,"POST",headers={"Idempotency-Key":key})
    assert status==202 and repeated["run_id"]==first["run_id"]
    assert repeated["replayed"] is True
    rid=first["run_id"]

    deadline=time.monotonic()+210
    while time.monotonic()<deadline:
        status,run=request(base+"/runs/"+rid)
        assert status==200,run
        if run["state"]=="COMPLETED":
            break
        assert run["outbox"]!="BLOCKED_UNKNOWN",run
        assert not any(e["type"]=="workflow.observation_error" for e in run["events"]),run
        time.sleep(0.65)
    else:raise TimeoutError("Inspector M7 public API Native Run did not complete")
    assert run["provider_workflow_run_id"],run
    assert run["result"]["result_source_step"]=="openai",run
    assert run["steps"]["pydantic"]["state"]=="COMPLETED",run
    assert run["steps"]["openai"]["state"]=="COMPLETED",run
    assert run["steps"]["openai"]["input"]==run["steps"]["pydantic"]["output"],run
    assert run["result"]["final_output"]==run["steps"]["openai"]["output"],run
    assert run["outbox"]=="CONFIRMED",run
    assert run["model_mode"] in ("deterministic_local_model","live"),run
    if run["model_mode"]=="deterministic_local_model":
        assert run["steps"]["pydantic"]["output"]=="pydantic-sdk-real-run",run
        assert run["steps"]["openai"]["output"]=="openai-sdk-real-run",run

    status,conversation=request(base+"/conversations/"+cid)
    assert status==200 and conversation["turns"][0]["run_ids"]==[rid],conversation
    status,events=request(base+f"/runs/{rid}/events?after=0&limit=250")
    assert status==200
    assert events["cursor"]==run["events"][-1]["seq"],events
    assert [e["seq"] for e in events["events"]]==list(range(1,len(events["events"])+1))
    assert sum(e["type"]=="run.completed" for e in events["events"])==1
    with urlopen(base+f"/runs/{rid}/stream",timeout=30) as stream:
        payload=stream.read().decode("utf-8")
        assert stream.headers["Content-Type"].startswith("text/event-stream")
    assert "id: "+rid+":" in payload,payload[:200]
    # This is not a production IdP test. It proves fixed server identity did
    # not come from user headers and that the real M7 Public API is mounted.
    status,invalid=request(base+"/runs/"+rid,"GET",headers={
        "X-Principal-Id":"untrusted-user","X-Project-Scope":"another-project"
    })
    assert status==200,invalid # headers cannot change fixed server-side POC identity

    evidence={
        "outcome":"PASS",
        "gate":"INSPECTOR_CAPABILITIES_M7_PUBLIC_API_NATIVE",
        "run_id":rid,"conversation_id":cid,"turn_id":tid,
        "hatchet_workflow_id":run["provider_workflow_run_id"],
        "native_sdk_a":"pydantic","native_sdk_b":"openai",
        "native_runs_started_for_idempotent_request":1,
        "event_count":len(events["events"]),
        "run_state":run["state"],
        "public_api_mounted":True,
        "in_existing_capabilities_tab":True,
        "enterprise_gateway_idp":"NOT_TESTED",
        "external_real_llm":("NOT_TESTED" if run["model_mode"]=="deterministic_local_model"
                              else "CONFIGURED_LIVE_MODE"),
        "production_readiness":False,
    }
    print(json.dumps(evidence,ensure_ascii=False,sort_keys=True),flush=True)
    return evidence


if __name__=="__main__":
    verify()
