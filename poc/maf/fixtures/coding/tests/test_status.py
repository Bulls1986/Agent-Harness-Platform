import unittest
from status import normalize_status

class NormalizeStatusTests(unittest.TestCase):
    def test_active(self):
        self.assertEqual(normalize_status("  active  "), "ACTIVE")
    def test_paused(self):
        self.assertEqual(normalize_status("\tpaused\n"), "PAUSED")
    def test_empty(self):
        self.assertEqual(normalize_status("  "), "")
if __name__ == "__main__":
    unittest.main()
