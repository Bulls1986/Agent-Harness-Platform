"""C16 controlled ACTUAL non-idempotent external HTTP business effect.

Separate SQLite file represents independent Tool business truth; each POST
increments counter even with the same Execution ID (intentionally not safe
to retry). GET only reads committed receipt; restart retains durable proof.
POC-only loopback, not enterprise MCP authentication/receipt signatures.
"""
from __future__ import annotations
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import argparse
import json
import sqlite3
from uuid import uuid4

class Sink(BaseHTTPRequestHandler):
    path_to_db=None

    def database(self):
        db=sqlite3.connect(self.path_to_db,timeout=6)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS actual_effects(
          receipt_id TEXT PRIMARY KEY,
          execution_id TEXT NOT NULL,
          attempt_id TEXT NOT NULL,
          effect_delta INTEGER NOT NULL CHECK(effect_delta=1),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        db.commit()
        return db

    def do_POST(self):
        if self.path!="/receipt":return self.send_error(404)
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n>2048:raise ValueError
            data=json.loads(self.rfile.read(n))
            if set(data)!={"execution_id","attempt_id"}:raise ValueError
            if not all(isinstance(v,str) and v for v in data.values()):raise ValueError
        except (ValueError,TypeError):
            return self.send_error(422)
        with self.database() as db:
            receipt_id="receipt-"+uuid4().hex
            db.execute("""INSERT INTO actual_effects(receipt_id,execution_id,attempt_id,effect_delta)
                          VALUES(?,?,?,1)""",(receipt_id,data["execution_id"],data["attempt_id"]))
            count=db.execute("SELECT COUNT(*) FROM actual_effects WHERE execution_id=?",
                             (data["execution_id"],)).fetchone()[0]
        self.respond(200,{"accepted":True,"receipt_id":receipt_id,"effect_count":count})

    def do_GET(self):
        if not self.path.startswith("/receipt/"):return self.send_error(404)
        execution=self.path[len("/receipt/"):]
        with self.database() as db:
            rows=db.execute("""SELECT receipt_id,execution_id,attempt_id,effect_delta
                        FROM actual_effects WHERE execution_id=? ORDER BY created_at,receipt_id""",
                            (execution,)).fetchall()
        if not rows:return self.send_error(404)
        self.respond(200,{"execution_id":execution,
                          "effect_count":sum(r["effect_delta"] for r in rows),
                          "receipts":[dict(r) for r in rows]})

    def respond(self,status,value):
        raw=json.dumps(value,separators=(",",":")).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self,*args):pass

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--port",type=int,required=True)
    p.add_argument("--sqlite",required=True)
    a=p.parse_args()
    path=Path(a.sqlite).resolve()
    if path.exists() and path.is_symlink():raise RuntimeError("Unsafe receipt path")
    path.parent.mkdir(parents=True,exist_ok=True)
    Sink.path_to_db=str(path)
    server=ThreadingHTTPServer(("127.0.0.1",a.port),Sink)
    try:server.serve_forever()
    finally:server.server_close()
