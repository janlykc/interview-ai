import http.client
import json
import os
import threading
import unittest
import uuid

from google.cloud import pubsub_v1
from werkzeug.serving import make_server

from app import create_app
from pubsub_emulator import pull_messages, setup
from test_ingress import IngressFixture, example_event
from webhook_service.adapters.pubsub import PubSubBroker
from webhook_service.outbox import OutboxPublisher


@unittest.skipUnless(os.environ.get("PUBSUB_EMULATOR_HOST"), "Set PUBSUB_EMULATOR_HOST for real emulator integration")
class EmulatorTests(IngressFixture):
    def setUp(self):
        super().setUp()
        suffix = uuid.uuid4().hex
        self.project = "auger-webhooks-local"
        self.topic = f"test-deliveries-{suffix}"
        self.subscription = f"test-inspect-{suffix}"
        self.addCleanup(self.delete_resources)
        self.broker = PubSubBroker(self.project, self.topic)
        self.addCleanup(self.broker.close)

    def delete_resources(self):
        from google.api_core.exceptions import NotFound
        with pubsub_v1.SubscriberClient() as subscriber, pubsub_v1.PublisherClient() as publisher:
            try:
                subscriber.delete_subscription(request={"subscription": subscriber.subscription_path(self.project, self.subscription)}, retry=None, timeout=5)
            except NotFound:
                pass
            try:
                publisher.delete_topic(request={"topic": publisher.topic_path(self.project, self.topic)}, retry=None, timeout=5)
            except NotFound:
                pass

    def test_real_HTTP_ingress_to_emulator_preserves_A_and_B_envelopes(self):
        setup(self.project, self.topic, self.subscription)
        app = create_app({"INGRESS_TOKEN": "test-token", "CUSTOMER_ID": "C1"}, service=self.service)
        server = make_server("127.0.0.1", 0, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request("POST", "/events", body=json.dumps(example_event()), headers={
                "Content-Type": "application/json", "Authorization": "Bearer test-token",
            })
            response = connection.getresponse()
            accepted = json.loads(response.read())
            connection.close()
            self.assertEqual(response.status, 202)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertTrue(all(row["published_at"] is None for row in self.rows("outbox")))
        result = OutboxPublisher(self.repository, self.broker).publish_due_batch()
        self.assertEqual((result.published, result.failed), (2, 0))
        messages = pull_messages(self.project, self.subscription)
        self.assertEqual({item["envelope"]["endpoint_id"] for item in messages}, {"A", "B"})
        self.assertEqual({item["envelope"]["delivery_id"] for item in messages}, set(accepted["delivery_ids"]))
        stored = {row["delivery_id"]: row for row in self.rows("outbox")}
        for item in messages:
            envelope = item["envelope"]
            self.assertEqual(envelope, json.loads(stored[envelope["delivery_id"]]["message_json"]))
            self.assertIsNotNone(stored[envelope["delivery_id"]]["published_at"])
        self.assertTrue(all(row["status"] == "pending" and row["attempt_count"] == 0 for row in self.rows("deliveries")))

    def test_real_broker_failure_keeps_work_until_resources_are_repaired(self):
        # Deliberately missing topic: actual Pub/Sub RPC failure, not a fake broker.
        self.service.accept(example_event())
        now = 1000
        publisher = OutboxPublisher(self.repository, self.broker, clock_ms=lambda: now)
        self.assertEqual(publisher.publish_due_batch().failed, 2)
        self.assertTrue(all(row["published_at"] is None and row["next_publish_at"] == 6000 for row in self.rows("outbox")))
        setup(self.project, self.topic, self.subscription)
        now = 6000
        self.assertEqual(publisher.publish_due_batch().published, 2)
        messages = pull_messages(self.project, self.subscription)
        self.assertEqual({item["envelope"]["endpoint_id"] for item in messages}, {"A", "B"})
