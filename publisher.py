"""Run the outbox publisher as a separate periodic local process."""

import argparse
import logging
import os
import time

from webhook_service.adapters.pubsub import PubSubBroker
from webhook_service.adapters.sqlite import SQLiteRepository
from webhook_service.models import StorageUnavailable
from webhook_service.outbox import OutboxPublisher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.environ.get("WEBHOOK_DB_PATH", "var/webhooks.db"))
    parser.add_argument("--project", default="auger-webhooks-local")
    parser.add_argument("--topic", default="webhook-deliveries")
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--once", action="store_true", help="Publish one due batch and exit")
    args = parser.parse_args()
    if args.interval <= 0 or args.batch_size < 1:
        parser.error("Interval and batch size must be positive")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        broker = PubSubBroker(args.project, args.topic)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        service = OutboxPublisher(SQLiteRepository(args.db), broker)
        while True:
            try:
                result = service.publish_due_batch(args.batch_size)
            except StorageUnavailable:
                logging.warning("outbox_storage_unavailable")
                if args.once:
                    return 1
            else:
                if args.once or result.published or result.failed:
                    logging.info("batch published=%d failed=%d", result.published, result.failed)
                if args.once:
                    return int(result.failed > 0)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
    finally:
        broker.close()


if __name__ == "__main__":
    raise SystemExit(main())
