import copy
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

from webhook_service.adapters.seeded import SeededEndpointResolver
from webhook_service.adapters.sqlite import SQLiteRepository
from webhook_service.ingress import EventIngressService
from webhook_service.models import (
    Endpoint, EventConflict, EventTooLarge, InvalidEvent, RoutingSnapshot, RoutingUnavailable,
    StorageUnavailable,
)


def example_event():
    return {
        "event_id": "E1", "customer_id": "C1", "category": "billing",
        "event_type": "invoice_paid", "schema_version": 1,
        "occurred_at": "2026-11-17T17:00:00Z",
        "payload": {"invoice_id": "INV-42"},
    }


class IngressFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "webhooks.db"
        self.repository = SQLiteRepository(self.path)
        self.snapshot = RoutingSnapshot("policy-v1", (
            Endpoint("A", "C1", "1", "https://a.example/webhooks", "secrets/A"),
            Endpoint("B", "C1", "1", "https://b.example/webhooks", "secrets/B"),
        ))
        self.resolver = SeededEndpointResolver({
            ("C1", "billing", "invoice_paid"): self.snapshot,
        })
        self.service = EventIngressService(self.repository, self.resolver, clock_ms=lambda: 1000)

    def rows(self, table):
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(f"SELECT * FROM {table}")]

    def assert_empty(self):
        for table in ("events", "deliveries", "outbox"):
            self.assertEqual(self.rows(table), [], table)


class IngressTests(IngressFixture):
    def test_acceptance_saves_event_two_pending_deliveries_and_two_unpublished_messages(self):
        accepted = self.service.accept(example_event())
        events, deliveries, outbox = [self.rows(t) for t in ("events", "deliveries", "outbox")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["routing_status"], "routed")
        self.assertEqual(json.loads(events[0]["payload_json"]), {"invoice_id": "INV-42"})
        self.assertEqual({d["endpoint_id"] for d in deliveries}, {"A", "B"})
        self.assertEqual(set(accepted.delivery_ids), {d["delivery_id"] for d in deliveries})
        self.assertEqual(len(outbox), 2)
        for delivery in deliveries:
            self.assertEqual(delivery["status"], "pending")
            self.assertEqual(delivery["attempt_count"], 0)
        for row in outbox:
            self.assertIsNone(row["published_at"])
            self.assertEqual(row["next_publish_at"], 1000)
            envelope = json.loads(row["message_json"])
            self.assertEqual(envelope["delivery_id"], row["delivery_id"])
            self.assertEqual(envelope["signing_secret_ref"], f"secrets/{envelope['endpoint_id']}")
            self.assertEqual(envelope["body"], events[0]["serialized_body"])
            self.assertEqual(json.loads(envelope["body"])["type"], "billing.invoice_paid")

    def test_retry_after_restart_reuses_original_ids_without_policy_lookup(self):
        first = self.service.accept(example_event())
        unavailable = Mock()
        unavailable.resolve.side_effect = RoutingUnavailable("Unavailable")
        restarted = EventIngressService(SQLiteRepository(self.path), unavailable)
        duplicate = example_event()
        duplicate["occurred_at"] = "2026-11-17T18:00:00+01:00"
        self.assertEqual(restarted.accept(duplicate), first)
        unavailable.resolve.assert_not_called()
        self.assertEqual([len(self.rows(t)) for t in ("events", "deliveries", "outbox")], [1, 2, 2])

    def test_conflicting_duplicate_is_rejected_without_new_work(self):
        self.service.accept(example_event())
        changed = example_event()
        changed["payload"] = {"invoice_id": "DIFFERENT"}
        with self.assertRaises(EventConflict):
            self.service.accept(changed)
        self.assertEqual([len(self.rows(t)) for t in ("events", "deliveries", "outbox")], [1, 2, 2])

    def test_event_identity_is_scoped_to_customer(self):
        first = self.service.accept(example_event())
        other = example_event()
        other["customer_id"] = "C2"
        second = self.service.accept(other)
        self.assertNotEqual(first.customer_id, second.customer_id)
        self.assertEqual(len(self.rows("events")), 2)

    def test_valid_empty_policy_is_accepted_without_delivery_work(self):
        event = example_event()
        event["event_type"] = "invoice_voided"
        accepted = self.service.accept(event)
        self.assertEqual(accepted.delivery_ids, ())
        self.assertEqual(self.rows("events")[0]["routing_status"], "no_targets")
        self.assertEqual(self.rows("deliveries"), [])
        self.assertEqual(self.rows("outbox"), [])

    def test_invalid_input_is_rejected_before_persistence(self):
        for field, value in (
            ("event_id", ""), ("customer_id", None), ("payload", []),
            ("schema_version", True), ("schema_version", 2**63),
            ("occurred_at", "2026-11-17T17:00:00"),
            ("occurred_at", "not-a-date"), ("category", "billing.invoice"),
            ("payload", {"amount": float("nan")}),
        ):
            with self.subTest(field=field, value=value):
                event = example_event()
                event[field] = value
                with self.assertRaises(InvalidEvent):
                    self.service.accept(event)
        self.assert_empty()

    def test_oversized_event_is_rejected_without_persistence(self):
        service = EventIngressService(self.repository, self.resolver, max_event_bytes=100)
        with self.assertRaises(EventTooLarge):
            service.accept(example_event())
        self.assert_empty()

    def test_policy_failure_does_not_accept_event(self):
        resolver = Mock()
        resolver.resolve.side_effect = RoutingUnavailable("Unavailable")
        with self.assertRaises(RoutingUnavailable):
            EventIngressService(self.repository, resolver).accept(example_event())
        self.assert_empty()

    def test_invalid_routing_snapshot_cannot_create_partial_or_cross_customer_work(self):
        bad_snapshots = [
            RoutingSnapshot("v1", (self.snapshot.endpoints[0], self.snapshot.endpoints[0])),
            RoutingSnapshot("v1", (Endpoint("X", "OTHER", "1", "https://x.example", "secrets/X"),)),
        ]
        for snapshot in bad_snapshots:
            with self.subTest(snapshot=snapshot):
                resolver = Mock()
                resolver.resolve.return_value = snapshot
                with self.assertRaises(RoutingUnavailable):
                    EventIngressService(self.repository, resolver).accept(example_event())
                self.assert_empty()

    def test_outbox_failure_rolls_back_event_and_every_delivery(self):
        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TRIGGER fail_second_outbox BEFORE INSERT ON outbox
                WHEN (SELECT COUNT(*) FROM outbox) = 1
                BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END;
            """)
        with self.assertRaises(StorageUnavailable):
            self.service.accept(example_event())
        self.assert_empty()
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER fail_second_outbox")
        self.assertEqual(len(self.service.accept(example_event()).delivery_ids), 2)

    def test_simultaneous_duplicate_requests_commit_only_one_fanout(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.service.accept(copy.deepcopy(example_event())), range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual([len(self.rows(t)) for t in ("events", "deliveries", "outbox")], [1, 2, 2])


if __name__ == "__main__":
    unittest.main()
