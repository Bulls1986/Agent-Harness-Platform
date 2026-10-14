"""External PostgreSQL test fixture for M6 actual bytes and digest.

This is explicitly NOT OSS, not platform artifact storage, and not a
production-ready Source of Truth. It is safe only for synthetic E2E fixtures
outside Harness's Domain database.
"""
from hashlib import sha256
import re
import psycopg

from poc.recipe.gates import ArtifactRef, RecipeBlocked


class SyntheticArtifactFixture:
    def __init__(self, url: str):
        if not url:
            raise ValueError("Independent external fixture PG URL required")
        self.url=url
        with psycopg.connect(url) as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS synthetic_m6_artifact (
                    object_ref TEXT PRIMARY KEY,
                    digest TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    body BYTEA NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)

    @staticmethod
    def _name(rid: str, step: str) -> str:
        if not isinstance(rid,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",rid):
            raise RecipeBlocked("Invalid synthetic Run identifier")
        if step not in ("plan","input","code","verify"):
            raise RecipeBlocked("Not an M6 frozen Step")
        return "oss://synthetic-m6/"+rid+"/"+step

    def put(self,rid: str,step: str,body: bytes,*,scope: str) -> ArtifactRef:
        name=self._name(rid,step)
        if (not isinstance(body,bytes) or not 0 < len(body) <= 262144
                or not isinstance(scope,str) or not scope
                or scope!=scope.strip()):
            raise RecipeBlocked("Invalid fixture content or scope")
        digest="sha256:"+sha256(body).hexdigest()
        with psycopg.connect(self.url) as c:
            c.execute(
                "INSERT INTO synthetic_m6_artifact (object_ref,digest,scope,body) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT(object_ref) DO NOTHING",
                (name,digest,scope,body))
            actual=c.execute(
                "SELECT digest,scope,body FROM synthetic_m6_artifact "
                "WHERE object_ref=%s FOR UPDATE",(name,)).fetchone()
            if actual!=(digest,scope,body):
                raise RecipeBlocked("Immutable synthetic Artifact payload mismatch")
        return ArtifactRef(name,digest,scope)

    def verified_bytes(self, artifact: ArtifactRef) -> bytes:
        artifact.validate(artifact.scope)
        with psycopg.connect(self.url) as c:
            actual=c.execute(
                "SELECT digest,scope,body FROM synthetic_m6_artifact "
                "WHERE object_ref=%s",(artifact.ref,)).fetchone()
        if not actual:
            raise RecipeBlocked("Artifact bytes not found")
        digest,scope,body=actual
        if (scope!=artifact.scope or digest!=artifact.digest
                or digest!="sha256:"+sha256(body).hexdigest()):
            raise RecipeBlocked("Artifact bytes/digest/scope verification failed")
        return body