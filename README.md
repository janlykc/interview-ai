# Auger webhook delivery

For the provided interview environment, [INTERVIEW_PROMPTS.md](INTERVIEW_PROMPTS.md)
contains copy/paste pairing prompts, the compact design, and one prompt per feature.
The full [design](design/spec.md) and [component view](design/component-architecture.svg)
are its companions. The prompt guide works without the local agent harness.

Current checkpoint: Flask ingress and atomic SQLite acceptance are implemented;
Pub/Sub publication, HTTP dispatch, and DLQ handling remain planned. The original
interview handout is kept locally and excluded from this public repository.

## Retrieve this checkpoint

```sh
git clone --branch question/auger-webhook-delivery --single-branch https://github.com/janlykc/interview-ai.git auger-webhooks
cd auger-webhooks
python3 -m venv .venv
```

For preparation notes, open `INTERVIEW_PROMPTS.md` and `design/spec.md`. To run the
implemented ingress feature, follow the commands below. No Google credentials or
Pub/Sub emulator are required for this checkpoint.

## Auger: running the ingress checkpoint

Use Python 3.12. From this worktree, install Flask and start the local server
(the token below is for the local demo):

```sh
.venv/bin/python -m pip install -r requirements.txt
export WEBHOOK_INGRESS_TOKEN=local-interview-token
.venv/bin/flask --app app run --port 8080
```

The server listens on `127.0.0.1:8080` and stores data in `var/webhooks.db`.
Override the port with `--port` and the database with `WEBHOOK_DB_PATH`.
The token authorizes only C1 by default; `WEBHOOK_CUSTOMER_ID` changes both that
binding and the seeded policy customer.
This is local demo authentication; production producer identity and TLS are deferred.

In another terminal, send the supplied event:

```sh
curl -i http://127.0.0.1:8080/events \
  -H 'Authorization: Bearer local-interview-token' \
  -H 'Content-Type: application/json' \
  --data-binary @examples/event.json
```

Expect `202` and two delivery IDs. Sending the identical event again returns the
same IDs. Changing its contents while retaining its customer/event ID returns
`409`. Input is restricted to the documented fields and a 256 KiB request limit.

Inspect the three tables:

```sh
sqlite3 -header -column var/webhooks.db '
  SELECT event_id, customer_id, routing_status FROM events;
  SELECT delivery_id, endpoint_id, status, attempt_count FROM deliveries;
  SELECT delivery_id, next_publish_at, published_at FROM outbox;
'
```

The first request atomically creates one event, two `pending` deliveries, and two
outbox rows with `next_publish_at` equal to acceptance time and `published_at` null.
Database timestamps are UTC Unix milliseconds. The seeded routing for
`C1 + billing.invoice_paid` selects A and B. Other event types have a valid empty
routing result and are accepted as `no_targets`. Destinations are example HTTPS
URLs, and queued messages contain secret references, never signing keys.

Run the ingress and Flask API tests:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

This checkpoint ends at durable ingress acceptance. The Pub/Sub publisher,
delivery worker, attempt-history table, and DLQ handler come in later checkpoints.
The full design also describes delivery state and lease fields that will be added
with the worker; the current executable schema is in
`webhook_service/adapters/schema.sql`.

## Code layout

- `app.py`: Flask application factory, event route, and JSON error responses.
- `webhook_service/ingress.py`: validation, destination resolution, and acceptance.
- `webhook_service/models.py`: event and delivery contracts.
- `webhook_service/ports.py`: repository and resolver interfaces.
- `webhook_service/adapters/`: SQLite persistence, SQL schema, and seeded routing.
- `tests/`: acceptance, failure, concurrency, and Flask API tests.

VS Code provides **Webhook: Run Flask ingress**, **Webhook: Debug Flask ingress**,
and **Interview: Tests**. The run and debug entries set the local demo token.
The application runs without the AI Team Harness or agent instruction files.
The original prompt is in `PROBLEM.md`; agreed behavior is in `design/`.
