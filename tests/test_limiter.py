import unittest
from unittest.mock import Mock

from src.limiter import RateLimitingComponent
from src.models import GateResult, TenantPolicy


class TokenBucketTests(unittest.TestCase):
    def setUp(self):
        self.clock = Mock(return_value=0.0)
        self.limiter = RateLimitingComponent(clock=self.clock)
        self.policy = TenantPolicy("a.example", rate_limit=2, burst_limit=2)

    def check(self):
        return self.limiter.check(self.policy.tenant_id, self.policy)

    def test_full_bucket_allows_burst_then_denies(self):
        for _ in range(4):
            self.assertEqual(self.check(), GateResult.SUCCESS)
        self.assertEqual(self.check(), GateResult.RATE_LIMITED)

    def test_partial_refill_survives_denied_request(self):
        for _ in range(4):
            self.check()
        self.clock.return_value = 0.25
        self.assertEqual(self.check(), GateResult.RATE_LIMITED)
        self.clock.return_value = 0.5
        self.assertEqual(self.check(), GateResult.SUCCESS)
        self.assertEqual(self.check(), GateResult.RATE_LIMITED)

    def test_idle_refill_is_capped_at_rate_plus_burst(self):
        for _ in range(4):
            self.check()
        self.clock.return_value = 100
        for _ in range(4):
            self.assertEqual(self.check(), GateResult.SUCCESS)
        self.assertEqual(self.check(), GateResult.RATE_LIMITED)

    def test_tenants_have_independent_buckets(self):
        for _ in range(4):
            self.check()
        other = TenantPolicy("b.example", rate_limit=2, burst_limit=2)
        self.assertEqual(self.limiter.check(other.tenant_id, other), GateResult.SUCCESS)
        self.assertEqual(self.check(), GateResult.RATE_LIMITED)

    def test_invalid_policy_is_rejected(self):
        for rate, burst in [(0, 2), (-1, 2), (1, -1), (float("nan"), 2)]:
            with self.subTest(rate=rate, burst=burst), self.assertRaises(ValueError):
                self.limiter.check("a.example", TenantPolicy("a.example", rate, burst))

    def test_zero_extra_burst_uses_rate_capacity(self):
        policy = TenantPolicy("zero.example", rate_limit=2, burst_limit=0)
        self.assertEqual(self.limiter.check(policy.tenant_id, policy), GateResult.SUCCESS)
        self.assertEqual(self.limiter.check(policy.tenant_id, policy), GateResult.SUCCESS)
        self.assertEqual(self.limiter.check(policy.tenant_id, policy), GateResult.RATE_LIMITED)
