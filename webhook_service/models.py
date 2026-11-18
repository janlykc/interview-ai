"""Ingress contracts and immutable, serialized delivery work."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone


class IngressError(Exception):
    status = 400
    code = "invalid_event"


class InvalidEvent(IngressError):
    pass


class EventTooLarge(IngressError):
    status = 413
    code = "event_too_large"


class EventConflict(IngressError):
    status = 409
    code = "event_conflict"


class RoutingUnavailable(IngressError):
    status = 503
    code = "routing_unavailable"


class StorageUnavailable(IngressError):
    status = 503
    code = "storage_unavailable"


class PublishUnavailable(Exception):
    """Broker acceptance failed or could not be confirmed before the deadline."""


def encode_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def fingerprint(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def required_text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise InvalidEvent(f"{field} must be a nonempty string of at most 200 characters")
    return value


@dataclass(frozen=True)
class Event:
    event_id: str
    customer_id: str
    category: str
    event_type: str
    schema_version: int
    occurred_at: str
    payload_json: str
    serialized_body: str
    content_hash: str

    @classmethod
    def parse(cls, value, max_bytes=262144):
        if not isinstance(value, dict):
            raise InvalidEvent("Event must be a JSON object")
        fields = ("event_id", "customer_id", "category", "event_type", "schema_version", "occurred_at", "payload")
        if set(value) != set(fields):
            raise InvalidEvent("Event must contain exactly the documented producer fields")
        normalized = {key: value[key] for key in fields}
        for key in ("event_id", "customer_id", "category", "event_type"):
            required_text(value[key], key)
        for key in ("category", "event_type"):
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", value[key]):
                raise InvalidEvent(f"{key} must be a lowercase name with optional digits and underscores")
        if type(value["schema_version"]) is not int or not 1 <= value["schema_version"] <= 2**63 - 1:
            raise InvalidEvent("schema_version must be a positive signed 64-bit integer")
        if not isinstance(value["payload"], dict):
            raise InvalidEvent("payload must be a JSON object")
        try:
            occurred = datetime.fromisoformat(required_text(value["occurred_at"], "occurred_at"))
            if occurred.tzinfo is None:
                raise ValueError("Timezone required")
            normalized["occurred_at"] = occurred.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            content = encode_json(normalized)
            if len(content.encode("utf-8")) > max_bytes:
                raise EventTooLarge("Event exceeds configured size")
            body = encode_json({
                "event_id": normalized["event_id"],
                "type": f"{normalized['category']}.{normalized['event_type']}",
                "schema_version": normalized["schema_version"],
                "occurred_at": normalized["occurred_at"], "data": normalized["payload"],
            })
            return cls(
                normalized["event_id"], normalized["customer_id"], normalized["category"],
                normalized["event_type"], normalized["schema_version"], normalized["occurred_at"],
                encode_json(normalized["payload"]), body, fingerprint(content),
            )
        except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError) as exc:
            raise InvalidEvent("Event must contain valid JSON and a timezone-aware ISO timestamp") from exc


@dataclass(frozen=True)
class Endpoint:
    endpoint_id: str
    customer_id: str
    version: str
    url: str
    signing_secret_ref: str


@dataclass(frozen=True)
class RoutingSnapshot:
    version: str
    endpoints: tuple[Endpoint, ...]


@dataclass(frozen=True)
class Delivery:
    delivery_id: str
    endpoint: Endpoint
    message_json: str


@dataclass(frozen=True)
class OutboxEntry:
    delivery_id: str
    message_json: str
    next_publish_at: int
    published_at: int | None = None


@dataclass(frozen=True)
class PublishBatchResult:
    published: int = 0
    failed: int = 0


@dataclass(frozen=True)
class Acceptance:
    event_id: str
    customer_id: str
    delivery_ids: tuple[str, ...]

    def as_dict(self):
        return {"event_id": self.event_id, "customer_id": self.customer_id, "delivery_ids": list(self.delivery_ids)}
