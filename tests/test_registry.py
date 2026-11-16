import unittest
from unittest.mock import Mock

from src.handler import InMemoryPolicyRegistry
from src.models import TenantPolicy


class RegistryTests(unittest.TestCase):
    def test_loads_once_and_resolves_each_tenant_from_memory(self):
        first = TenantPolicy("a.example", 10, 20)
        second = TenantPolicy("b.example", 30, 40)
        source = {first.tenant_id: first, second.tenant_id: second}
        loader = Mock(return_value=source)

        registry = InMemoryPolicyRegistry(loader)
        source.clear()

        self.assertEqual(registry.get("a.example"), first)
        self.assertEqual(registry.get("b.example"), second)
        self.assertEqual(registry.get("a.example"), first)
        loader.assert_called_once_with()

    def test_empty_registry_reports_unknown_tenant(self):
        registry = InMemoryPolicyRegistry()
        with self.assertRaises(KeyError):
            registry.get("unknown.example")
