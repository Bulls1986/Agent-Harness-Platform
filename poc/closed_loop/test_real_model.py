"""Contract-first tests for opt-in live provider and structured business handoff."""
import os
import unittest
from unittest.mock import patch
from pydantic import ValidationError

from poc.closed_loop.real_model import (
    ModelConfiguration, parse_requirements, parse_review, render_business_report,
)


class RealModelContractTests(unittest.TestCase):
    def test_local_default_needs_no_secret(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = ModelConfiguration.from_env()
        self.assertEqual(cfg.mode, "deterministic_local_model")
        self.assertIsNone(cfg.model_id)
        self.assertIsNone(cfg.api_key)

    def test_live_requires_explicit_endpoint_secret_and_model(self):
        for missing in ("HARNESS_MODEL_API_KEY", "HARNESS_MODEL_BASE_URL", "HARNESS_MODEL_NAME"):
            env = {
                "HARNESS_MODEL_MODE": "live",
                "HARNESS_MODEL_API_KEY": "fake-test-only",
                "HARNESS_MODEL_BASE_URL": "https://example.invalid/v1",
                "HARNESS_MODEL_NAME": "example-model",
            }
            del env[missing]
            with self.subTest(missing=missing), patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ValueError):
                    ModelConfiguration.from_env()

    def test_valid_draft_review_and_readable_report(self):
        draft = parse_requirements('{"feature":"企业用户注册","summary":"注册并认证企业",'
                                   '"capabilities":["邮箱注册","企业认证"],'
                                   '"business_rules":["邮箱唯一"],'
                                   '"acceptance_criteria":["邮箱重复注册时拒绝创建"]}')
        review = parse_review('{"decision":"NEEDS_WORK",'
                              '"issues":["缺少验证码重试限制"],"risks":["邮箱滥用"],'
                              '"recommendations":["增加限流"],"summary":"需要补充安全控制"}')
        report = render_business_report(draft, review)
        self.assertIn("企业用户注册", report)
        self.assertIn("邮箱重复注册时拒绝创建", report)
        self.assertIn("缺少验证码重试限制", report)
        self.assertIn("NEEDS_WORK", report)

    def test_invalid_or_incomplete_model_outputs_fail_closed(self):
        for invalid in ("not-json", "{}", '{"feature":"x","summary":"",'
                        '"capabilities":[],"business_rules":[],"acceptance_criteria":[]}'):
            with self.subTest(invalid=invalid), self.assertRaises((ValueError, ValidationError)):
                parse_requirements(invalid)
        with self.assertRaises((ValueError, ValidationError)):
            parse_review('{"decision":"PASS","issues":[]}')
        with self.assertRaises((ValueError, ValidationError)):
            parse_review('{"decision":"GOOD","issues":[],"risks":[],"recommendations":[],"summary":"ok"}')

    def test_trailing_or_invalid_content_not_repaired_silently(self):
        with self.assertRaises((ValueError, ValidationError)):
            parse_requirements("leading-text " + '{"feature":"bad"}')
        with self.assertRaises((ValueError, ValidationError)):
            parse_review('{"decision":"PASS","issues":[],"risks":[],"recommendations":[],"summary":"OK"} EXTRA')


if __name__ == "__main__":
    unittest.main()