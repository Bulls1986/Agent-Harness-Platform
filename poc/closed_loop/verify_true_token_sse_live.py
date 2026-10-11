"""Black-box LIVE provider-token SSE proof; requires actual LiteLLM/Hatchet/Postgres.
No API key is read or emitted by this verifier. Both upstream SDK streams must be observed.
"""
from __future__ import annotations
import argparse,json,time
from urllib.request import Request,urlopen

def req(url,method="GET",value=None,headers=None):
    payload=None if value is None else json.dumps(value).encode()
    h={"Content-Type":"application/json"} if payload is not None else {}
    h.update(headers or {})
    with urlopen(Request(url,data=payload,headers=h,method=method),timeout=25) as r:
        return json.load(r)

def collect(base,rid,*,cancel=False):
    runurl=base+"/api/runs/"+rid
    seen=set();deltas={"pydantic":[],"openai":[]};timeline=[]
    final=None; last=0; deadline=time.monotonic()+420;did_cancel=False
    while time.monotonic()<deadline:
        hdr={"Last-Event-ID":rid+":"+str(last)} if last else {}
        with urlopen(Request(runurl+"/stream",headers=hdr),timeout=38) as response:
            assert "text/event-stream" in response.headers["Content-Type"]
            typ=None;obj=None
            for raw in response:
                line=raw.decode("utf8").strip()
                if line.startswith("event:"):typ=line[6:].strip()
                elif line.startswith("data:"):obj=json.loads(line[5:].strip())
                elif not line and obj is not None:
                    seq=obj["seq"]
                    if seq <= last or seq in seen:raise AssertionError("SSE replay duplicate or reversed")
                    last=seq;seen.add(seq);timeline.append((seq,typ))
                    if typ=="response.output_text.delta":
                        data=obj["data"]
                        assert data.get("source")=="provider_stream",data
                        name=data["step_id"];deltas[name].append(data["delta"])
                        snap=req(runurl)
                        if not cancel and snap["state"]!="COMPLETED":
                            assert snap["steps"][name]["state"] in ("RUNNING","COMPLETED")
                        if cancel and not did_cancel:
                            response_cancel=req(runurl+"/cancel",method="POST")
                            assert response_cancel["state"]=="CANCEL_REQUESTED",response_cancel
                            did_cancel=True
                            print("cancel_command_accepted",rid,"at_seq",last,flush=True)
                    typ=None;obj=None
            snap=req(runurl)
            if snap["state"] in ("COMPLETED","CANCELLED"):
                final=snap;break
            if any(e["type"]=="workflow.observation_error" for e in snap["events"]):
                raise AssertionError("Execution failed: "+str([(e["type"],e["data"]) for e in snap["events"][-4:]]))
    if final is None:raise TimeoutError("Live SSE proof did not terminate")
    snapshot=req(runurl)
    assert snapshot==final or snapshot["run_id"]==final["run_id"]
    assert len(seen)==len(timeline)
    persisted={e["seq"] for e in snapshot["events"]}
    assert seen.issubset(persisted)
    if cancel:
        assert did_cancel and final["state"]=="CANCELLED",final["state"]
        assert final["result"] is None
        assert sum(e["type"]=="run.completed" for e in snapshot["events"])==0
        cancel_seq=next(e["seq"] for e in snapshot["events"] if e["type"]=="run.cancel.requested")
        assert not any(e["type"]=="response.output_text.delta" and e["seq"]>cancel_seq for e in snapshot["events"])
    else:
        assert final["state"]=="COMPLETED"
        for name in ("pydantic","openai"):
            assert len(deltas[name])>0,("SDK missing upstream token",name)
            first=min(e["seq"] for e in snapshot["events"] if e["type"]=="response.output_text.delta" and e["data"]["step_id"]==name)
            completed=min(e["seq"] for e in snapshot["events"] if e["type"]=="step.completed" and e["data"]["step_id"]==name)
            assert first<completed,(name,first,completed)
        assert snapshot["result"]["mode"]=="live"
        assert snapshot["steps"]["openai"]["input"]==snapshot["steps"]["pydantic"]["output"]
    # After-cursor replay must be exact, including events after last observed cursor.
    after=next(e["seq"] for e in snapshot["events"] if e["type"]=="response.output_text.delta")
    with urlopen(Request(runurl+"/stream",headers={"Last-Event-ID":rid+":"+str(after)}),timeout=38) as response:
        body=response.read().decode("utf8")
    assert "id: "+rid+":"+str(after)+"\n" not in body
    assert "id: "+rid+":"+str(after+1)+"\n" in body
    evidence={"outcome":"PASS","run_id":rid,"state":final["state"],
              "provider_workflow_id":final["provider_workflow_run_id"],
              "model_id":final["model_id"],"provider_deltas":{k:len(v) for k,v in deltas.items()},
              "last_sse_sequence":last,"cancel_ack":did_cancel,"real_provider_stream":True,
              "cursor_replay":"PASS","real_pg":True,"sdk_handoff":not cancel}
    print(json.dumps(evidence,ensure_ascii=False),flush=True)
    return evidence

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--url",default="http://127.0.0.1:8766")
    p.add_argument("--cancel",action="store_true")
    p.add_argument("--run-id")
    args=p.parse_args(); base=args.url.rstrip("/")
    if args.run_id: rid=args.run_id
    else:
        prompt=("制定20条企业认证、权限、账号状态及失败回退的详细验收条件，每条至少说明两个边界" if args.cancel
                else "设计企业注册与企业审核功能，包含邮箱唯一性、企业认证审核状态和角色权限，给出可测试的验收标准")
        rid=req(base+"/api/runs","POST",{"prompt":prompt})["run_id"]
    print("started_real_sse_run",rid,flush=True)
    collect(base,rid,cancel=args.cancel)

if __name__=="__main__":main()