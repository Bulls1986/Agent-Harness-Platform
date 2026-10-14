"""Static front-end regression for live product requirement design and independent review."""
import unittest
from pathlib import Path

HTML = Path(__file__).with_name("inspector.html").read_text(encoding="utf-8")

class InspectorLiveCopyTests(unittest.TestCase):
    def test_live_entry_identifies_product_and_reviewer(self):
        self.assertIn("真实 LLM · 产品需求设计与独立评审", HTML)
        self.assertIn("产品 Agent（Pydantic AI）", HTML)
        self.assertIn("评审 Agent（OpenAI Agents SDK）", HTML)
        self.assertIn("调用真实 LLM · 开始需求分析与评审", HTML)

    def test_live_example_only_replaces_untouched_placeholder(self):
        self.assertIn("请设计一个企业成员邀请", HTML)
        self.assertIn("initialPrompt", HTML)
        self.assertIn("cfg.mode==='live'", HTML)

    def test_deterministic_mode_never_claims_real_analysis(self):
        self.assertIn("双 Agent SDK 接力 · 固定输出", HTML)
        self.assertIn("当前模式：确定性本地模型", HTML)
        self.assertIn("textContent", HTML)
        self.assertNotIn("innerHTML", HTML)

if __name__ == "__main__":
    unittest.main()
