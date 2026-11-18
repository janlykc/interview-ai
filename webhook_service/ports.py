from typing import Protocol

from .models import Acceptance, Delivery, Event, OutboxEntry, RoutingSnapshot


class EndpointResolver(Protocol):
    def resolve(self, customer_id: str, category: str, event_type: str) -> RoutingSnapshot: ...


class Repository(Protocol):
    def find_acceptance(self, event: Event) -> Acceptance | None: ...

    def accept_event_with_deliveries(
        self, event: Event, routing: RoutingSnapshot, deliveries: tuple[Delivery, ...], now_ms: int,
    ) -> Acceptance: ...

    def list_due_outbox(self, now_ms: int, limit: int = 100) -> list[OutboxEntry]: ...

    def mark_published(self, delivery_id: str, published_at: int) -> None: ...

    def schedule_publish_retry(self, delivery_id: str, next_publish_at: int) -> None: ...


class MessageBroker(Protocol):
    def publish(self, message_json: str) -> str:
        """Return broker message ID after acceptance, or raise PublishUnavailable."""
        ...
