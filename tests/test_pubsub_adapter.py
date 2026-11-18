import os
import unittest
from unittest.mock import Mock, patch

from google.api_core.exceptions import DeadlineExceeded

from webhook_service.adapters.pubsub import PubSubBroker
from webhook_service.models import PublishUnavailable


class PubSubAdapterTests(unittest.TestCase):
    def test_publishes_exact_UTF8_bytes_and_waits_for_acceptance_with_deadline(self):
        client = Mock()
        client.topic_path.return_value = "projects/local/topics/deliveries"
        client.publish.return_value.message_ids = ["message-id"]
        broker = PubSubBroker("local", "deliveries", client=client, timeout_seconds=3)
        self.assertEqual(broker.publish('{"value":"é"}'), "message-id")
        client.publish.assert_called_once_with(
            request={"topic": "projects/local/topics/deliveries", "messages": [{"data": '{"value":"é"}'.encode("utf-8")}]},
            retry=None, timeout=3,
        )

    def test_timeout_reports_unknown_acceptance_as_retryable(self):
        client = Mock()
        client.publish.side_effect = DeadlineExceeded("Response not confirmed")
        with self.assertRaises(PublishUnavailable):
            PubSubBroker("local", "deliveries", client=client).publish("{}")

    def test_local_entrypoint_requires_emulator_selection(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "PUBSUB_EMULATOR_HOST"):
                PubSubBroker("local", "deliveries")
