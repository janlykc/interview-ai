PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS events (
    customer_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    category TEXT NOT NULL,
    event_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    received_at INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    serialized_body TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    routing_snapshot_json TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    routing_status TEXT NOT NULL CHECK (routing_status IN ('routed', 'no_targets')),
    PRIMARY KEY (customer_id, event_id)
);

CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id TEXT PRIMARY KEY NOT NULL,
    customer_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    endpoint_id TEXT NOT NULL,
    endpoint_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    dispatch_envelope_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    replay_generation INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (customer_id, event_id) REFERENCES events(customer_id, event_id),
    UNIQUE (customer_id, event_id, endpoint_id)
);

CREATE TABLE IF NOT EXISTS outbox (
    delivery_id TEXT PRIMARY KEY NOT NULL REFERENCES deliveries(delivery_id),
    message_json TEXT NOT NULL,
    next_publish_at INTEGER NOT NULL,
    published_at INTEGER
);

CREATE INDEX IF NOT EXISTS outbox_due_idx
    ON outbox (next_publish_at) WHERE published_at IS NULL;
