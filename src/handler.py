"""Resolve tenant policy and route requests according to the gate result."""

from typing import Callable, Mapping

from .limiter import RateLimitingComponent
from .models import GateResult, Request, Response, TenantPolicy
from .policy import PolicyRegistry


class InMemoryPolicyRegistry:
    def __init__(
        self,
        load_policies: Callable[[], Mapping[str, TenantPolicy]] | None = None,
    ):
        # Load once at startup; request handling only reads this local snapshot.
        self.policies: dict[str, TenantPolicy] = (
            dict(load_policies()) if load_policies is not None else {}
        )

    def get(self, tenant_id: str) -> TenantPolicy:
        return self.policies[tenant_id]


class RateLimitHandler:
    def __init__(
        self,
        registry: PolicyRegistry,
        limiter: RateLimitingComponent,
        forward: Callable[[Request], Response],
    ):
        self.registry = registry
        self.limiter = limiter
        self.forward = forward

    def handle(self, request: Request) -> Response:
        tenant_id = request.hostname
        policy = self.registry.get(tenant_id)
        result = self.limiter.check(tenant_id, policy)

        if result is GateResult.SUCCESS:
            return self.forward(request)
        if result is GateResult.RATE_LIMITED:
            return Response(429, "Too Many Requests")
        raise ValueError(f"Unexpected gate result: {result!r}")
