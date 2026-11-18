import time
import uuid
from urllib.parse import urlsplit

from .models import Delivery, Event, RoutingUnavailable, encode_json
from .ports import EndpointResolver, Repository


class EventIngressService:
    def __init__(self, repository: Repository, resolver: EndpointResolver, *, clock_ms=None,
                 new_id=None, max_event_bytes=262144, max_destinations=100):
        self.repository = repository
        self.resolver = resolver
        self.clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self.new_id = new_id or (lambda: str(uuid.uuid4()))
        self.max_event_bytes = max_event_bytes
        self.max_destinations = max_destinations

    def accept(self, value):
        event = Event.parse(value, self.max_event_bytes)
        existing = self.repository.find_acceptance(event)
        if existing is not None:
            return existing

        routing = self.resolver.resolve(event.customer_id, event.category, event.event_type)
        self._validate_routing(event, routing)
        deliveries = []
        for endpoint in routing.endpoints:
            delivery_id = self.new_id()
            message = {
                "schema_version": 1, "delivery_id": delivery_id,
                "event_id": event.event_id, "customer_id": event.customer_id,
                "replay_generation": 0, "endpoint_id": endpoint.endpoint_id,
                "endpoint_version": endpoint.version, "url": endpoint.url,
                "body": event.serialized_body, "signing_secret_ref": endpoint.signing_secret_ref,
            }
            deliveries.append(Delivery(delivery_id, endpoint, encode_json(message)))
        return self.repository.accept_event_with_deliveries(event, routing, tuple(deliveries), self.clock_ms())

    def _validate_routing(self, event, routing):
        if not routing.version or len(routing.endpoints) > self.max_destinations:
            raise RoutingUnavailable("Invalid routing snapshot")
        seen = set()
        for endpoint in routing.endpoints:
            try:
                parsed = urlsplit(endpoint.url)
                valid_url = parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and not parsed.fragment
                valid_url = valid_url and (parsed.port is None or 1 <= parsed.port <= 65535)
            except ValueError:
                valid_url = False
            if (endpoint.customer_id != event.customer_id or not endpoint.endpoint_id
                    or endpoint.endpoint_id in seen or not endpoint.version
                    or not endpoint.signing_secret_ref or not valid_url):
                raise RoutingUnavailable("Invalid routing snapshot")
            seen.add(endpoint.endpoint_id)
