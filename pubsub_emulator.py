"""Create local Pub/Sub resources and inspect messages without dispatching HTTP."""

import argparse
import json
import time

from google.api_core.exceptions import AlreadyExists, DeadlineExceeded
from google.cloud import pubsub_v1

from webhook_service.adapters.pubsub import require_emulator


def setup(project, topic, subscription):
    require_emulator()
    with pubsub_v1.PublisherClient() as publisher, pubsub_v1.SubscriberClient() as subscriber:
        topic_path = publisher.topic_path(project, topic)
        subscription_path = subscriber.subscription_path(project, subscription)
        try:
            publisher.create_topic(request={"name": topic_path}, retry=None, timeout=5)
        except AlreadyExists:
            pass
        try:
            subscriber.create_subscription(
                request={"name": subscription_path, "topic": topic_path, "ack_deadline_seconds": 30},
                retry=None, timeout=5,
            )
        except AlreadyExists:
            existing = subscriber.get_subscription(request={"subscription": subscription_path}, retry=None, timeout=5)
            if existing.topic != topic_path or existing.push_config.push_endpoint:
                raise ValueError("Existing subscription does not match this pull inspector")
        return topic_path, subscription_path


def pull_messages(project, subscription, *, count=2, timeout_seconds=15):
    require_emulator()
    if count < 1 or timeout_seconds <= 0:
        raise ValueError("Message count and timeout must be positive")
    deadline = time.monotonic() + timeout_seconds
    messages = []
    with pubsub_v1.SubscriberClient() as subscriber:
        subscription_path = subscriber.subscription_path(project, subscription)
        while len(messages) < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                response = subscriber.pull(
                    request={"subscription": subscription_path, "max_messages": count - len(messages)},
                    retry=None, timeout=min(remaining, 5),
                )
            except DeadlineExceeded:
                continue
            received = response.received_messages
            for item in received:
                messages.append({
                    "message_id": item.message.message_id,
                    "envelope": json.loads(item.message.data.decode("utf-8")),
                })
            if received:
                subscriber.acknowledge(
                    request={"subscription": subscription_path, "ack_ids": [item.ack_id for item in received]},
                    retry=None, timeout=5,
                )
    return messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "pull"))
    parser.add_argument("--project", default="auger-webhooks-local")
    parser.add_argument("--topic", default="webhook-deliveries")
    parser.add_argument("--subscription", default="webhook-deliveries-inspect")
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    try:
        require_emulator()
    except ValueError as exc:
        parser.error(str(exc))
    if args.command == "setup":
        topic, subscription = setup(args.project, args.topic, args.subscription)
        print(json.dumps({"topic": topic, "inspection_subscription": subscription}, indent=2))
        return 0
    if args.count < 1 or args.timeout <= 0:
        parser.error("Message count and timeout must be positive")
    messages = pull_messages(args.project, args.subscription, count=args.count, timeout_seconds=args.timeout)
    print(json.dumps(messages, indent=2, ensure_ascii=False))
    return int(len(messages) < args.count)


if __name__ == "__main__":
    raise SystemExit(main())
