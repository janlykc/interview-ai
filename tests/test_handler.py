import unittest
from unittest.mock import Mock

from src.handler import RateLimitHandler
from src.models import GateResult, Request, Response, TenantPolicy


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.policy = TenantPolicy("tenant.example", rate_limit=100, burst_limit=200)
        self.registry = Mock()
        self.registry.get.return_value = self.policy
        self.limiter = Mock()
        self.forward = Mock(return_value=Response(201, "created"))
        self.handler = RateLimitHandler(self.registry, self.limiter, self.forward)
        self.request = Request(hostname="tenant.example")

    def test_success_supplies_policy_and_forwards_original_request_once(self):
        self.limiter.check.return_value = GateResult.SUCCESS

        response = self.handler.handle(self.request)

        self.registry.get.assert_called_once_with("tenant.example")
        self.limiter.check.assert_called_once_with("tenant.example", self.policy)
        self.forward.assert_called_once_with(self.request)
        self.assertIs(response, self.forward.return_value)

    def test_rate_limited_returns_429_without_forwarding(self):
        self.limiter.check.return_value = GateResult.RATE_LIMITED

        response = self.handler.handle(self.request)

        self.assertEqual(response.status_code, 429)
        self.forward.assert_not_called()


if __name__ == "__main__":
    unittest.main()
