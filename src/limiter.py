"""In-process, per-tenant token buckets with lazy refill."""

from dataclasses import dataclass, field
from math import isfinite
from threading import Lock
from time import monotonic
from typing import Callable

from .models import GateResult, TenantPolicy


@dataclass
class _Bucket:
    tokens: float
    last_refill: float
    lock: Lock = field(default_factory=Lock)


class RateLimitingComponent:
    def __init__(self, clock: Callable[[], float] = monotonic):
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._creation_lock = Lock()

    def check(self, tenant_id: str, policy: TenantPolicy) -> GateResult:
        """Consume one token if available; each new tenant starts full."""
        if tenant_id != policy.tenant_id:
            raise ValueError("Policy does not belong to this tenant")
        if (
            not isfinite(policy.rate_limit) or policy.rate_limit <= 0
            or not isfinite(policy.burst_limit) or policy.burst_limit < 0
        ):
            raise ValueError("Rate must be positive and extra burst quota nonnegative")

        capacity = policy.rate_limit + policy.burst_limit
        if not isfinite(capacity):
            raise ValueError("Total bucket capacity must be finite")

        with self._creation_lock:
            if tenant_id not in self._buckets:
                self._buckets[tenant_id] = _Bucket(
                    float(capacity), self._clock()
                )
            bucket = self._buckets[tenant_id]

        with bucket.lock:
            now = max(self._clock(), bucket.last_refill)
            elapsed = now - bucket.last_refill
            bucket.tokens = min(
                capacity, bucket.tokens + elapsed * policy.rate_limit
            )
            bucket.last_refill = now
            if bucket.tokens < 1:
                return GateResult.RATE_LIMITED
            bucket.tokens -= 1
            return GateResult.SUCCESS


