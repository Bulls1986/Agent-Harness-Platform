"""DEV-M7 minimal PostgreSQL Conversation/Turn/Run and ArtifactRef facts.

No model history parsing, OSS signing, identity provider, or task scheduler.
SecurityContext comes only from the injected trusted Gateway adapter.
"""
from __future__ import annotations
import re
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.platform_access.authorized_reads import RunBinding


class PgConversationStore:
    def __init__(self, facts: PgFacts):
        if not isinstance(facts,PgFacts):
            raise ValueError("Harness PG required")
        self.facts=facts
        self.init_schema()

    def init_schema(self):
        with self.facts.tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_conversation (
                    id TEXT PRIMARY KEY,
                    project_scope TEXT NOT NULL,
                    creator_principal_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )""")
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_turn (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES harness_conversation(id),
                    ordinal INTEGER NOT NULL,
                    user_message TEXT NOT NULL,
                    agent_ref TEXT NOT NULL,
                    recipe_ref TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE(conversation_id,ordinal)
                )""")
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_turn_run (
                    turn_id TEXT NOT NULL REFERENCES harness_turn(id),
                    run_id TEXT PRIMARY KEY REFERENCES harness_run(id)
                )""")
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_artifact_ref (
                    artifact_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES harness_run(id),
                    object_ref TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    size_bytes BIGINT NOT NULL CHECK(size_bytes >= 0),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )""")

    @staticmethod
    def _string(value,max_chars:int=256):
        if (not isinstance(value,str) or not value or value!=value.strip()
                or len(value)>max_chars or any(ord(x)<32 for x in value)):
            raise ValueError("Invalid or oversized string")
        return value

    def create_conversation(self,project_scope:str,creator:str,title:str) -> str:
        for value in (project_scope,creator): self._string(value)
        self._string(title,200)
        cid="conversation-"+uuid4().hex
        with self.facts.tx() as c:
            c.execute("INSERT INTO harness_conversation(id,project_scope,creator_principal_id,title) "
                      "VALUES (%s,%s,%s,%s)",(cid,project_scope,creator,title))
        return cid

    def binding(self,cid:str)->dict:
        with self.facts.tx() as c:
            row=c.execute(
                "SELECT project_scope,creator_principal_id FROM harness_conversation WHERE id=%s",
                (cid,)).fetchone()
        if not row: raise KeyError(cid)
        return {"conversation_id":cid,"project_scope":row[0],"creator_principal_id":row[1]}

    def list_conversations(self,project_scope:str,creator:str)->list[dict]:
        with self.facts.tx() as c:
            rows=c.execute(
                "SELECT id,title,created_at FROM harness_conversation "
                "WHERE project_scope=%s AND creator_principal_id=%s "
                "ORDER BY created_at DESC,id DESC LIMIT 100",
                (project_scope,creator)).fetchall()
        return [{"conversation_id":cid,"title":title,"created_at":created.isoformat()}
                for cid,title,created in rows]

    def conversation(self,cid:str)->dict:
        with self.facts.tx() as c:
            row=c.execute(
                "SELECT id,project_scope,creator_principal_id,title,created_at "
                "FROM harness_conversation WHERE id=%s",(cid,)).fetchone()
            if not row: raise KeyError(cid)
            turns=c.execute(
                "SELECT id,ordinal,user_message,agent_ref,recipe_ref,created_at "
                "FROM harness_turn WHERE conversation_id=%s ORDER BY ordinal",
                (cid,)).fetchall()
            linked=c.execute(
                "SELECT r.turn_id,r.run_id FROM harness_turn_run r "
                "JOIN harness_turn t ON t.id=r.turn_id WHERE t.conversation_id=%s "
                "ORDER BY r.run_id",(cid,)).fetchall()
        byturn={}
        for tid,rid in linked:byturn.setdefault(tid,[]).append(rid)
        return {"conversation_id":row[0],"project_scope":row[1],
                "creator_principal_id":row[2],"title":row[3],
                "created_at":row[4].isoformat(),
                "turns":[{"turn_id":tid,"ordinal":ordinal,
                          "message":message,"agent_ref":agent,"recipe_ref":recipe,
                          "created_at":dt.isoformat(),
                          "run_ids":byturn.get(tid,[])}
                         for tid,ordinal,message,agent,recipe,dt in turns]}

    def create_turn(self,cid:str,message:str,agent_ref:str,recipe_ref:str)->str:
        self._string(message,8192);self._string(agent_ref);self._string(recipe_ref)
        tid="turn-"+uuid4().hex
        with self.facts.tx() as c:
            row=c.execute("SELECT id FROM harness_conversation WHERE id=%s FOR UPDATE",
                          (cid,)).fetchone()
            if not row: raise KeyError(cid)
            ordinal=c.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM harness_turn "
                              "WHERE conversation_id=%s",(cid,)).fetchone()[0]
            c.execute("INSERT INTO harness_turn "
                      "(id,conversation_id,ordinal,user_message,agent_ref,recipe_ref) "
                      "VALUES (%s,%s,%s,%s,%s,%s)",
                      (tid,cid,ordinal,message,agent_ref,recipe_ref))
        return tid

    def turn_binding(self,tid:str)->dict:
        with self.facts.tx() as c:
            row=c.execute("SELECT c.id,c.project_scope,c.creator_principal_id "
                          "FROM harness_turn t JOIN harness_conversation c "
                          "ON c.id=t.conversation_id WHERE t.id=%s",(tid,)).fetchone()
        if not row:raise KeyError(tid)
        return {"conversation_id":row[0],"project_scope":row[1],
                "creator_principal_id":row[2]}

    def link_run(self,tid:str,rid:str):
        # Even if a compromised API adapter attempts a different conversation
        # scope, the Run and Turn associations must match frozen PG owners.
        with self.facts.tx() as c:
            row=c.execute(
                "SELECT c.project_scope,c.creator_principal_id "
                "FROM harness_turn t JOIN harness_conversation c ON c.id=t.conversation_id "
                "WHERE t.id=%s",(tid,)).fetchone()
            run=c.execute("SELECT project_scope,initiator_principal_id "
                          "FROM harness_run WHERE id=%s FOR UPDATE",(rid,)).fetchone()
            if not row or not run or row!=run or not all(row):
                raise UnsafeDispatch("Run/Turn immutable ownership mismatch")
            prior=c.execute("SELECT turn_id FROM harness_turn_run WHERE run_id=%s",
                            (rid,)).fetchone()
            if prior:
                if prior[0]!=tid:raise UnsafeDispatch("Run already belongs to another Turn")
                return
            c.execute("INSERT INTO harness_turn_run(turn_id,run_id) VALUES (%s,%s)",
                      (tid,rid))

    def register_artifact(self,artifact_id:str,rid:str,object_ref:str,digest:str,
                          media_type:str,size_bytes:int):
        # Trusted Storage adapter only. Public API does not allow arbitrary
        # client object_ref injection or sign/download storage URLs.
        for value in (artifact_id,rid,object_ref,media_type):self._string(value,512)
        if not re.fullmatch("[0-9a-f]{64}",digest):
            raise ValueError("Digest SHA-256 required")
        if type(size_bytes) is not int or size_bytes<0:
            raise ValueError("Invalid artifact size")
        with self.facts.tx() as c:
            run=c.execute("SELECT project_scope,initiator_principal_id "
                          "FROM harness_run WHERE id=%s FOR UPDATE",(rid,)).fetchone()
            if not run or not all(run):
                raise UnsafeDispatch("Unscoped/unknown Run cannot publish ArtifactRef")
            existing=c.execute("SELECT run_id,object_ref,digest,media_type,size_bytes "
                               "FROM harness_artifact_ref WHERE artifact_id=%s",
                               (artifact_id,)).fetchone()
            frozen=(rid,object_ref,digest,media_type,size_bytes)
            if existing:
                if existing!=frozen:raise UnsafeDispatch("Conflicting ArtifactRef")
                return
            c.execute("INSERT INTO harness_artifact_ref "
                      "(artifact_id,run_id,object_ref,digest,media_type,size_bytes) "
                      "VALUES (%s,%s,%s,%s,%s,%s)",
                      (artifact_id,*frozen))

    def artifact(self,artifact_id:str)->dict:
        with self.facts.tx() as c:
            row=c.execute("SELECT artifact_id,run_id,digest,media_type,size_bytes "
                          "FROM harness_artifact_ref WHERE artifact_id=%s",
                          (artifact_id,)).fetchone()
        if not row:raise KeyError(artifact_id)
        return dict(zip(("artifact_id","run_id","digest","media_type","size_bytes"),row))

    def artifacts_for_run(self,rid:str)->list[dict]:
        with self.facts.tx() as c:
            ids=c.execute("SELECT artifact_id FROM harness_artifact_ref "
                          "WHERE run_id=%s ORDER BY created_at,artifact_id",(rid,)).fetchall()
        return [self.artifact(i[0]) for i in ids]