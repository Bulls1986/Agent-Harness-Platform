"""Real PG contract for stream cursor, terminal and cancel command, not a mock durable engine."""
import os,unittest
from uuid import uuid4
from poc.closed_loop.facts import PgFacts,UnsafeDispatch
from poc.closed_loop.inspector import create_app
from fastapi.testclient import TestClient

@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),"Docker PG required")
class StreamFactsTests(unittest.TestCase):
    def setUp(self):
        self.db=PgFacts();self.rid="sse-"+uuid4().hex
        self.key=self.db.create(self.rid,prompt="test",model_mode="live",model_id="model")
        self.db.dispatch(self.key);self.db.bind(self.key,"wf-"+self.rid)
        self.db.start_step(self.rid,"pydantic","test")

    def test_real_chunks_are_pg_events_before_step_completed_and_cursor_is_stable(self):
        self.db.append_stream_delta(self.rid,"pydantic","测试","pydantic")
        self.db.append_stream_delta(self.rid,"pydantic","输入","pydantic")
        events=self.db.events_since(self.rid,0)
        tokens=[e for e in events if e["type"]=="response.output_text.delta"]
        self.assertEqual([e["data"]["delta"] for e in tokens],["测试","输入"])
        self.assertEqual([e["data"]["source"] for e in tokens],["provider_stream"]*2)
        self.assertEqual(self.db.events_since(self.rid,tokens[0]["seq"])[0]["seq"],tokens[1]["seq"])
        self.assertEqual(self.db.snapshot(self.rid)["steps"]["pydantic"]["state"],"RUNNING")

    def test_cancel_is_durable_idempotent_and_requires_worker_ack(self):
        self.assertEqual(self.db.request_cancel(self.rid), "CANCEL_REQUESTED")
        self.assertEqual(self.db.request_cancel(self.rid), "CANCEL_REQUESTED")
        self.assertTrue(self.db.cancel_requested(self.rid))
        self.assertEqual(self.db.snapshot(self.rid)["state"],"CANCEL_REQUESTED")
        with self.assertRaises(UnsafeDispatch):
            self.db.append_stream_delta(self.rid,"pydantic","too late","pydantic")
        self.db.acknowledge_cancel(self.rid)
        self.assertEqual(self.db.snapshot(self.rid)["state"],"CANCELLED")
        self.assertEqual(sum(x["type"]=="run.cancel.requested" for x in self.db.events_since(self.rid,0)),1)
        with self.assertRaises(UnsafeDispatch):self.db.request_cancel(self.rid)
        with self.assertRaises(UnsafeDispatch):self.db.complete(self.rid)

    def test_http_sse_replay_and_cross_run_cursor_validation(self):
        self.db.append_stream_delta(self.rid,"pydantic","第一段","pydantic")
        self.db.request_cancel(self.rid);self.db.acknowledge_cancel(self.rid)
        client=TestClient(create_app(submit=lambda *a:None))
        a=client.get("/api/runs/"+self.rid+"/stream")
        self.assertEqual(a.status_code,200,a.text)
        self.assertIn("text/event-stream",a.headers["content-type"])
        self.assertIn("第一段",a.text)
        last=next(x['seq'] for x in self.db.events_since(self.rid,0) if x['type']=='response.output_text.delta')
        b=client.get("/api/runs/"+self.rid+"/stream",headers={"Last-Event-ID":self.rid+":"+str(last)})
        self.assertEqual(b.status_code,200)
        self.assertNotIn("第一段",b.text)
        self.assertEqual(client.get("/api/runs/"+self.rid+"/stream",headers={"Last-Event-ID":"wrong:1"}).status_code,422)
        self.assertEqual(client.get("/api/runs/"+self.rid+"/stream",headers={"Last-Event-ID":self.rid+":-1"}).status_code,422)
        self.assertEqual(client.post("/api/runs/"+self.rid+"/cancel").status_code,409)

if __name__=="__main__": unittest.main()