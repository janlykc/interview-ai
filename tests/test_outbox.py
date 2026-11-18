import json
import sqlite3
from unittest.mock import Mock

from test_ingress import IngressFixture, example_event
from webhook_service.models import PublishUnavailable
from webhook_service.outbox import OutboxPublisher


class OutboxTests(IngressFixture):
    def setUp(self):
        super().setUp()
        self.service.accept(example_event())
        self.now = 1000
        self.broker = Mock()
        self.publisher = OutboxPublisher(self.repository, self.broker, clock_ms=lambda: self.now)

    def outbox_by_endpoint(self):
        return {json.loads(row["message_json"])["endpoint_id"]: row for row in self.rows("outbox")}

    def test_marks_each_outbox_only_after_acceptance_and_leaves_deliveries_pending(self):
        def accepted(message_json):
            envelope = json.loads(message_json)
            self.assertIsNone(self.outbox_by_endpoint()[envelope["endpoint_id"]]["published_at"])
            return "broker-id"
        self.broker.publish.side_effect = accepted
        result = self.publisher.publish_due_batch()
        self.assertEqual((result.published, result.failed), (2, 0))
        self.assertTrue(all(row["published_at"] == 1000 for row in self.rows("outbox")))
        self.assertTrue(all(row["status"] == "pending" and row["attempt_count"] == 0 for row in self.rows("deliveries")))
        self.assertEqual(self.publisher.publish_due_batch().published, 0)
        self.assertEqual(self.broker.publish.call_count, 2)

    def test_failed_A_does_not_block_B_and_is_retried_only_when_due(self):
        def unavailable_A(message_json):
            if json.loads(message_json)["endpoint_id"] == "A":
                raise PublishUnavailable("Unavailable")
            return "broker-id"
        self.broker.publish.side_effect = unavailable_A
        result = self.publisher.publish_due_batch()
        self.assertEqual((result.published, result.failed), (1, 1))
        rows = self.outbox_by_endpoint()
        self.assertIsNone(rows["A"]["published_at"])
        self.assertEqual(rows["A"]["next_publish_at"], 6000)
        self.assertEqual(rows["B"]["published_at"], 1000)
        self.now = 5999
        self.assertEqual(self.publisher.publish_due_batch().published, 0)
        self.broker.publish.side_effect = None
        self.now = 6000
        self.assertEqual(self.publisher.publish_due_batch().published, 1)
        self.assertEqual(self.outbox_by_endpoint()["A"]["published_at"], 6000)
        self.assertEqual(self.broker.publish.call_count, 3)

    def test_ambiguous_acceptance_can_republish_the_same_delivery_and_bytes(self):
        observed = []
        def ambiguous(message_json):
            observed.append(message_json)
            raise PublishUnavailable("Response lost after broker acceptance")
        self.broker.publish.side_effect = ambiguous
        self.assertEqual(self.publisher.publish_due_batch().failed, 2)
        self.assertTrue(all(row["published_at"] is None for row in self.rows("outbox")))
        self.now = 6000
        self.broker.publish.side_effect = lambda message: observed.append(message) or "accepted"
        self.assertEqual(self.publisher.publish_due_batch().published, 2)
        self.assertEqual(sorted(observed[:2]), sorted(observed[2:]))

    def test_failure_saving_broker_acceptance_leaves_recoverable_work(self):
        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TRIGGER fail_publication_update BEFORE UPDATE ON outbox
                WHEN NEW.published_at IS NOT NULL
                BEGIN SELECT RAISE(ABORT, 'simulated database failure'); END;
            """)
        result = self.publisher.publish_due_batch()
        self.assertEqual((result.published, result.failed), (0, 2))
        self.assertTrue(all(row["published_at"] is None for row in self.rows("outbox")))
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER fail_publication_update")
        self.assertEqual(self.publisher.publish_due_batch().published, 2)
        self.assertEqual(self.broker.publish.call_count, 4)

    def test_stale_failure_cannot_reschedule_or_undo_success(self):
        row = self.rows("outbox")[0]
        self.repository.mark_published(row["delivery_id"], 2000)
        self.repository.schedule_publish_retry(row["delivery_id"], 9000)
        self.repository.mark_published(row["delivery_id"], 3000)
        saved = next(item for item in self.rows("outbox") if item["delivery_id"] == row["delivery_id"])
        self.assertEqual(saved["published_at"], 2000)
        self.assertEqual(saved["next_publish_at"], 1000)

    def test_batch_size_bounds_publication(self):
        self.assertEqual(self.publisher.publish_due_batch(limit=1).published, 1)
        self.assertEqual(self.publisher.publish_due_batch(limit=1).published, 1)
        self.assertEqual(self.publisher.publish_due_batch(limit=1).published, 0)
