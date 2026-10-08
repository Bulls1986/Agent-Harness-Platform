"""C13: low-cardinality metric label and secret-safe tracing contract."""
import unittest
from pathlib import Path

class C13Contract(unittest.TestCase):
    def test_native_interceptor_and_platform_only_boundaries(self):
        source=(Path(__file__).resolve().parents[1]/"verify_c13_otel.py").read_text()
        self.assertIn("OpenTelemetryInterceptor(add_temporal_spans=True)",source)
        self.assertIn("harness.execution",source)
        self.assertIn("harness.run.id",source)
        self.assertIn("harness.execution.id",source)
        self.assertNotIn("JUSDA_LITELLM_API_KEY",source)
        self.assertNotIn("PrometheusMetricReader",source)

if __name__=="__main__":unittest.main()
