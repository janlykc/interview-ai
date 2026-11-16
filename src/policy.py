"""Tenant policy lookup contract; storage implementation is deferred."""

from typing import Protocol

from .models import TenantPolicy


class PolicyRegistry(Protocol):
    def get(self, tenant_id: str) -> TenantPolicy:
        """Resolve a registered tenant; unknown-tenant behavior is not yet defined."""
        ...


