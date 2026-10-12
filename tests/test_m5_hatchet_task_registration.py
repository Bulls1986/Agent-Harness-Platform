"""Hatchet resolves forward-reference hints against the module global namespace.

The live M5 workflow must register correctly with a real SDK; these tests
exercise the reflection contract with an offline stand-in and do not
constitute actual physical Worker takeover proof.
"""
import sys
import types
import typing
import unittest
from unittest.mock import patch

from poc.sandbox.verify_hatchet_cube_worker_takeover import build_workflow


class FakeHatchet:
    def __init__(self):
        self.seen_hints = None

    def workflow(self, *, name, input_validator):
        outer = self

        class FakeWorkflow:
            def task(self, **kwargs):
                def decorator(fn):
                    outer.seen_hints = typing.get_type_hints(fn)
                    return fn
                return decorator

        return FakeWorkflow()


class RealHatchetAnnotationContractTests(unittest.TestCase):
    def test_task_context_annotation_resolves_on_sdk_registration(self):
        fake_ctx = type("Context", (), {})
        sdk = types.ModuleType("hatchet_sdk")
        sdk.Context = fake_ctx
        with patch.dict(sys.modules, {"hatchet_sdk": sdk}):
            hatchet = FakeHatchet()
            build_workflow(hatchet)
            self.assertIs(hatchet.seen_hints["ctx"], fake_ctx)


if __name__ == "__main__":
    unittest.main()
