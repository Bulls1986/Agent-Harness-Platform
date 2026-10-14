"""Bounded test-fixture artifact persistence outside Harness domain DB.

Not real OSS; never counts as a production Artifact Store gate.
"""
import hashlib
import os
import unittest
from uuid import uuid4
import psycopg

from poc.recipe.synthetic_artifacts import SyntheticArtifactFixture
from poc.recipe.gates import ArtifactRef, RecipeBlocked

@unittest.skipUnless(os.getenv("HARNESS_LEDGER_DATABASE_URL"), "independent fixture PG required")
class SyntheticArtifactFixtureTests(unittest.TestCase):
    def setUp(self):
        self.url=os.environ["HARNESS_LEDGER_DATABASE_URL"]
        self.fixture=SyntheticArtifactFixture(self.url)
        self.rid="m6-fixture-"+uuid4().hex
    def tearDown(self):
        with psycopg.connect(self.url) as c:
            c.execute("DELETE FROM synthetic_m6_artifact WHERE object_ref LIKE %s",
                      ("oss://synthetic-m6/"+self.rid+"/%",))
    def test_bytes_roundtrip_and_digest(self):
        content=b'{"feature":"synthetic","acceptance":"testable"}'
        ref=self.fixture.put(self.rid,"plan",content,scope="project-synthetic")
        self.assertEqual(ref.digest,"sha256:"+hashlib.sha256(content).hexdigest())
        self.assertEqual(self.fixture.verified_bytes(ref),content)
        self.assertEqual(self.fixture.put(self.rid,"plan",content,scope="project-synthetic"),ref)
    def test_scope_digest_and_conflict_block(self):
        ref=self.fixture.put(self.rid,"code",b'abc',scope="project-synthetic")
        with self.assertRaises(RecipeBlocked):
            self.fixture.verified_bytes(ArtifactRef(ref.ref,ref.digest,"foreign-project"))
        with self.assertRaises(RecipeBlocked):
            self.fixture.verified_bytes(ArtifactRef(ref.ref,"sha256:"+"a"*64,ref.scope))
        with self.assertRaises(RecipeBlocked):
            self.fixture.put(self.rid,"code",b'changed',scope=ref.scope)

if __name__=="__main__":
    unittest.main()