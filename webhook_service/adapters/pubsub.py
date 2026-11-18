"""Google's Pub/Sub client behind the application's small publication contract."""

import os

import grpc
from google.api_core.exceptions import GoogleAPIError
from google.pubsub_v1 import PublisherClient
from google.pubsub_v1.services.publisher.transports.grpc import PublisherGrpcTransport

from ..models import PublishUnavailable


def require_emulator():
    host = os.environ.get("PUBSUB_EMULATOR_HOST")
    if not host:
        raise ValueError("Set PUBSUB_EMULATOR_HOST for this local-only checkpoint")
    return host


class PubSubBroker:
    def __init__(self, project_id, topic_id, *, client=None, timeout_seconds=5):
        if timeout_seconds <= 0:
            raise ValueError("Publish timeout must be positive")
        if client is None:
            host = require_emulator()
            # One bounded synchronous RPC; batching and SDK retries are unnecessary
            # because the outbox already owns per-delivery publication and recovery.
            transport = PublisherGrpcTransport(channel=grpc.insecure_channel(host))
            client = PublisherClient(transport=transport)
        self.client = client
        self.topic = client.topic_path(project_id, topic_id)
        self.timeout_seconds = timeout_seconds

    def publish(self, message_json):
        try:
            response = self.client.publish(
                request={"topic": self.topic, "messages": [{"data": message_json.encode("utf-8")}]},
                retry=None, timeout=self.timeout_seconds,
            )
            return response.message_ids[0]
        except (GoogleAPIError, TimeoutError, OSError) as exc:
            raise PublishUnavailable("Pub/Sub acceptance was not confirmed") from exc

    def close(self):
        self.client.transport.close()
