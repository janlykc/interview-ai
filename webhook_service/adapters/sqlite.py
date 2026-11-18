import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from ..models import Acceptance, EventConflict, OutboxEntry, StorageUnavailable, encode_json, fingerprint


class SQLiteRepository:
    """One connection per operation, with atomic event/delivery/outbox acceptance."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.executescript(Path(__file__).with_name("schema.sql").read_text())

    @contextmanager
    def _connection(self):
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            yield db
        except sqlite3.Error as exc:
            raise StorageUnavailable("Database operation failed") from exc
        finally:
            if db is not None:
                if db.in_transaction:
                    db.rollback()
                db.close()

    @staticmethod
    def _find(db, event):
        row = db.execute(
            "SELECT content_hash FROM events WHERE customer_id = ? AND event_id = ?",
            (event.customer_id, event.event_id),
        ).fetchone()
        if row is None:
            return None
        if row["content_hash"] != event.content_hash:
            raise EventConflict("Event ID already accepted with different content")
        ids = db.execute(
            "SELECT delivery_id FROM deliveries WHERE customer_id = ? AND event_id = ? ORDER BY endpoint_id",
            (event.customer_id, event.event_id),
        ).fetchall()
        return Acceptance(event.event_id, event.customer_id, tuple(row["delivery_id"] for row in ids))

    def find_acceptance(self, event):
        with self._connection() as db:
            # Keep event and delivery reads on the same committed snapshot.
            db.execute("BEGIN")
            result = self._find(db, event)
            db.commit()
            return result

    def list_due_outbox(self, now_ms, limit=100):
        if limit < 1:
            raise ValueError("Batch limit must be positive")
        with self._connection() as db:
            rows = db.execute("""
                SELECT delivery_id, message_json, next_publish_at, published_at
                FROM outbox WHERE published_at IS NULL AND next_publish_at <= ?
                ORDER BY next_publish_at, delivery_id LIMIT ?
            """, (now_ms, limit)).fetchall()
            return [OutboxEntry(**dict(row)) for row in rows]

    def mark_published(self, delivery_id, published_at):
        with self._connection() as db:
            db.execute("""
                UPDATE outbox SET published_at = ?
                WHERE delivery_id = ? AND published_at IS NULL
            """, (published_at, delivery_id))

    def schedule_publish_retry(self, delivery_id, next_publish_at):
        with self._connection() as db:
            db.execute("""
                UPDATE outbox SET next_publish_at = ?
                WHERE delivery_id = ? AND published_at IS NULL
            """, (next_publish_at, delivery_id))

    def accept_event_with_deliveries(self, event, routing, deliveries, now_ms):
        with self._connection() as db:
            # Serialize writers and recheck identity after policy resolution.
            db.execute("BEGIN IMMEDIATE")
            existing = self._find(db, event)
            if existing is not None:
                db.commit()
                return existing
            db.execute("""
                INSERT INTO events (
                    customer_id, event_id, category, event_type, schema_version,
                    occurred_at, received_at, payload_json, serialized_body, content_hash,
                    routing_snapshot_json, policy_version, routing_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.customer_id, event.event_id, event.category, event.event_type,
                event.schema_version, event.occurred_at, now_ms, event.payload_json,
                event.serialized_body, event.content_hash, encode_json(asdict(routing)),
                routing.version, "routed" if deliveries else "no_targets",
            ))
            for delivery in deliveries:
                endpoint = delivery.endpoint
                db.execute("""
                    INSERT INTO deliveries (
                        delivery_id, customer_id, event_id, endpoint_id, endpoint_version,
                        policy_version, dispatch_envelope_hash, status, attempt_count,
                        replay_generation, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0, 0, ?)
                """, (
                    delivery.delivery_id, event.customer_id, event.event_id, endpoint.endpoint_id,
                    endpoint.version, routing.version, fingerprint(delivery.message_json), now_ms,
                ))
                db.execute("""
                    INSERT INTO outbox (delivery_id, message_json, next_publish_at, published_at)
                    VALUES (?, ?, ?, NULL)
                """, (delivery.delivery_id, delivery.message_json, now_ms))
            db.commit()
            return Acceptance(event.event_id, event.customer_id, tuple(
                delivery.delivery_id for delivery in sorted(deliveries, key=lambda d: d.endpoint.endpoint_id)
            ))
