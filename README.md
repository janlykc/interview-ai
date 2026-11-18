# Auger webhook delivery

For the provided interview environment, [INTERVIEW_PROMPTS.md](INTERVIEW_PROMPTS.md)
contains copy/paste pairing prompts, the compact design, and one prompt per feature.
The full [design](design/spec.md) and [component view](design/component-architecture.svg)
are its companions. The prompt guide works without the local agent harness.

Current checkpoint: Flask ingress, atomic SQLite acceptance, and the outbox
publisher connected to the Pub/Sub emulator are implemented. HTTP dispatch and
DLQ handling remain planned. The original
interview handout is kept locally and excluded from this public repository.

## Retrieve this checkpoint

```sh
git clone --branch question/auger-webhook-delivery --single-branch https://github.com/janlykc/interview-ai.git auger-webhooks
cd auger-webhooks
python3 -m venv .venv
```

For preparation notes, open `INTERVIEW_PROMPTS.md` and `design/spec.md`. To run the
implemented ingress feature, follow the commands below. Ingress works without
Google credentials or an emulator. The publication demo additionally needs the
official local Pub/Sub emulator; it does not use a real Google Cloud project.

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

The delivery worker, attempt-history table, and DLQ handler come in later checkpoints.
The full design also describes delivery state and lease fields that will be added
with the worker; the current executable schema is in
`webhook_service/adapters/schema.sql`.

## Publish A and B to the Pub/Sub emulator

Install a Java 21 runtime and Google Cloud CLI, then install the emulator:

```sh
gcloud components install pubsub-emulator
```

Start it in a terminal and leave it running. `JAVA_HOME` must point to the Java
runtime if Java is not already on the system path.

```sh
mkdir -p var/pubsub-emulator
gcloud beta emulators pubsub start --host-port=127.0.0.1:8085 --project=auger-webhooks-local --data-dir=var/pubsub-emulator
```

In another terminal, create the topic and **inspection** pull subscription before
publishing. All commands here require `PUBSUB_EMULATOR_HOST`; the application
entrypoints refuse to silently fall back to a cloud endpoint.

```sh
export PUBSUB_EMULATOR_HOST=127.0.0.1:8085
.venv/bin/python pubsub_emulator.py setup
```

Start Flask and submit `examples/event.json` using the ingress commands above.
Then publish one due batch and inspect the two real broker messages:

```sh
.venv/bin/python publisher.py --once
.venv/bin/python pubsub_emulator.py pull --count 2
```

The output includes separate envelopes for A and B: delivery ID, URL, exact body,
and signing-secret reference. The inspector acknowledges messages on its own
subscription after reading them. It does not POST to customer URLs or mark a
delivery successful. The future worker will use a separate push subscription;
this diagnostic pull subscriber does not change the dispatch design.

For continuous publication, run the separate process:

```sh
.venv/bin/python publisher.py
```

It polls every second, publishes at most 100 due rows per batch, and schedules
publication failures five seconds later. Each publish is one synchronous Google
client RPC with a five-second deadline and SDK retries disabled. Publication
changes only the outbox's `published_at`; deliveries remain `pending` with zero
HTTP attempts. A crash after broker acceptance can cause duplicate publication.

Ingress and publisher must use the same database. Set `WEBHOOK_DB_PATH` for both,
or pass `--db` to the publisher. For example, use `var/pubsub-demo.db` for an isolated
rehearsal. Repeating E1 reuses existing work; change its `event_id` to E2 when you
want two new messages. Resources are emulator-session data: restart the emulator,
rerun setup, and use a fresh event for a new demo. Published outbox rows are not
automatically reset when the disposable emulator loses its messages.

Run the real emulator integration tests:

```sh
PUBSUB_EMULATOR_HOST=127.0.0.1:8085 .venv/bin/python -m unittest discover -s tests -v
```

There are 25 unit/API tests and two emulator integration tests. The integration
tests use isolated topics/subscriptions, cover real HTTP ingress through broker
receipt and recovery from a missing topic, and remove only their own resources.
Without `PUBSUB_EMULATOR_HOST`, those two tests are explicitly skipped.

The host emulator was verified on the prep Mac. The Docker route encountered a
local Docker storage I/O failure and was not used for this result. Local Java
downloads and emulator data live under ignored `var/` and are not shipped in Git.
See [Google's emulator setup](https://docs.cloud.google.com/pubsub/docs/emulator)
for platform prerequisites and emulator limitations, including absent IAM checks.

## Code layout

- `app.py`: Flask application factory, event route, and JSON error responses.
- `webhook_service/ingress.py`: validation, destination resolution, and acceptance.
- `publisher.py`: periodic publisher process, or a single `--once` batch.
- `pubsub_emulator.py`: local resource setup and message inspection.
- `webhook_service/outbox.py`: publication, acceptance recording, and retry timing.
- `webhook_service/models.py`: event and delivery contracts.
- `webhook_service/ports.py`: repository and resolver interfaces.
- `webhook_service/adapters/`: SQLite persistence, SQL schema, Pub/Sub client, and seeded routing.
- `tests/`: acceptance, failure, concurrency, and Flask API tests.

VS Code provides **Webhook: Run Flask ingress**, **Webhook: Debug Flask ingress**,
and **Interview: Tests**. The run and debug entries set the local demo token.
The application runs without the AI Team Harness or agent instruction files.
The public practice summary is in `PROBLEM.md`; agreed behavior is in `design/`.
