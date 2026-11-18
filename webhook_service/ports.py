from typing import Protocol

from .models import Acceptance, Delivery, Event, RoutingSnapshot


class EndpointResolver(Protocol):
    def resolve(self, customer_id: str, category: str, event_type: str) -> RoutingSnapshot: ...


class Repository(Protocol):
    def find_acceptance(self, event: Event) -> Acceptance | None: ...

    def accept_event_with_deliveries(
        self, event: Event, routing: RoutingSnapshot, deliveries: tuple[Delivery, ...], now_ms: int,
    ) -> Acceptance: ...
