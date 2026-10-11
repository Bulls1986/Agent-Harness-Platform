"""Portable fail-closed adapter contracts for native Hatchet list metadata."""
import unittest
from types import SimpleNamespace

from poc.closed_loop.facts import UnsafeDispatch
from poc.closed_loop.hatchet_segment_lookup import HatchetSegmentLookup


def row(workflow_id, key, run, version="2"):
    return SimpleNamespace(
        metadata=SimpleNamespace(id=workflow_id),
        additional_metadata={"harness_command_key":key,
                             "harness_run_id":run,
                             "harness_plan_version":version},
    )


class HatchetNativeMetadataTests(unittest.TestCase):
    def test_ignored_provider_filter_is_locally_rechecked(self):
        pages=[]
        def list_native(**kwargs):
            pages.append(kwargs)
            return [row("unrelated","other","other-run"),
                    row("true","command-v2","run-a")]
        matches=HatchetSegmentLookup(list_native).find("command-v2","run-a")
        self.assertEqual([m.workflow_run_id for m in matches],["true"])
        self.assertEqual(len(pages),1)
        self.assertEqual(pages[0]["additional_metadata"]["harness_command_key"],"command-v2")

    def test_wrong_scope_and_version_rejected(self):
        bad=[
            row("wrong-project","command-v2","run-b"),
            row("wrong-version","command-v2","run-a",version="1"),
            SimpleNamespace(metadata=SimpleNamespace(id="none"),additional_metadata=None),
        ]
        self.assertEqual(HatchetSegmentLookup(lambda **_:bad).find("command-v2","run-a"),[])

    def test_pagination_ambiguity_not_hidden_by_first_page(self):
        listing=[row("first","command-v2","run-a"),
                 row("other","other","other"),
                 row("second","command-v2","run-a")]
        def native(**kwargs):
            s=kwargs["offset"];n=kwargs["limit"]
            return listing[s:s+n]
        results=HatchetSegmentLookup(native,page_size=2,max_pages=3).find(
            "command-v2","run-a")
        self.assertEqual(len(results),2)

    def test_incomplete_or_bad_native_listing_stays_unknown(self):
        repeating=lambda **kwargs:[row("one","command-v2","run-a")]*2
        with self.assertRaises(UnsafeDispatch):
            HatchetSegmentLookup(repeating,page_size=2,max_pages=2).find(
                "command-v2","run-a")
        with self.assertRaises(UnsafeDispatch):
            HatchetSegmentLookup(lambda **_:None).find("command-v2","run-a")
        with self.assertRaises(UnsafeDispatch):
            HatchetSegmentLookup(
                lambda **_: (_ for _ in ()).throw(TimeoutError())
            ).find("command-v2","run-a")
        missing=[SimpleNamespace(metadata=SimpleNamespace(id=None),
                                 additional_metadata=row("x","command-v2","run-a").additional_metadata)]
        with self.assertRaises(UnsafeDispatch):
            HatchetSegmentLookup(lambda **_:missing).find("command-v2","run-a")


if __name__=="__main__":
    unittest.main()
