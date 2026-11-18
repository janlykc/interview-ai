"""Publish committed work without holding a database transaction over the network."""

import logging
import time

from .models import PublishBatchResult, PublishUnavailable, StorageUnavailable
from .ports import MessageBroker, Repository

logger = logging.getLogger(__name__)


class OutboxPublisher:
    def __init__(self, repository: Repository, broker: MessageBroker, *, clock_ms=None,
                 retry_delay_ms=5000):
        self.repository = repository
        self.broker = broker
        self.clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self.retry_delay_ms = retry_delay_ms

    def publish_due_batch(self, limit=100):
        entries = self.repository.list_due_outbox(self.clock_ms(), limit)
        published = failed = 0
        for entry in entries:
            try:
                self.broker.publish(entry.message_json)
            except PublishUnavailable:
                failed += 1
                logger.warning("publication_retry delivery_id=%s", entry.delivery_id)
                try:
                    self.repository.schedule_publish_retry(
                        entry.delivery_id, self.clock_ms() + self.retry_delay_ms,
                    )
                except StorageUnavailable:
                    # The committed row remains recoverable even if scheduling fails.
                    logger.warning("retry_schedule_unavailable delivery_id=%s", entry.delivery_id)
                continue
            try:
                self.repository.mark_published(entry.delivery_id, self.clock_ms())
            except StorageUnavailable:
                # Broker may have accepted: retry can publish the same delivery again.
                failed += 1
                logger.warning("publication_record_unavailable delivery_id=%s", entry.delivery_id)
                continue
            published += 1
            logger.info("published delivery_id=%s", entry.delivery_id)
        return PublishBatchResult(published, failed)
