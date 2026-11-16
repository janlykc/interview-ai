"""Compatibility imports; implementation lives in src."""

from src.handler import RateLimitHandler
from src.limiter import RateLimitingComponent
from src.models import GateResult, Request, Response, TenantPolicy
from src.policy import PolicyRegistry

__all__ = [
    "RateLimitHandler", "RateLimitingComponent", "GateResult",
    "Request", "Response", "TenantPolicy", "PolicyRegistry",
]
