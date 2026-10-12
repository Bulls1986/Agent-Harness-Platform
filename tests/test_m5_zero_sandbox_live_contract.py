"""Model-only isolation, including unchanged real-provider listing contract."""
import asyncio
import unittest
from unittest.mock import Mock

from poc.sandbox.verify_zero_sandbox_live import (
    ModelOnlyProof, _inventory, execute_model_only,
)


class ProviderInventoryTests(unittest.TestCase):
    def test_inventory_valid_and_non_mutating(self):
        sdk = Mock()
        sdk.list.return_value = [
            {"sandboxID": "before-a"}, {"sandboxID": "before-b"}]
        self.assertEqual(_inventory(sdk), {"before-a", "before-b"})
        sdk.list.assert_called_once_with()
        self.assertFalse(sdk.create.called)

    def test_missing_duplicate_or_non_native_list_cannot_count_as_pass(self):
        for bad in (None, {}, [{"id": "fake"}],
                    [{"sandboxID": "one"}, {"sandboxID": "one"}]):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                _inventory(Mock(list=Mock(return_value=bad)))

    def test_model_only_dispatch_does_not_construct_native_cube(self):
        adapter = ModelOnlyProof()
        asyncio.run(execute_model_only(adapter))
        self.assertEqual(adapter.invocations, 1)


if __name__ == "__main__":
    unittest.main()
