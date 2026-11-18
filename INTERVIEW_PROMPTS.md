# Portable prompts for the Auger build session

Copy the blocks below into the provided coding agent as needed. They do not
require this checkout, a particular agent, the AI Team Harness, or AGENTS.md files.
Use any supplied repository instructions and the interviewer's rules. These are
pairing prompts and design notes; they do not imply that our rehearsal code exists
on the provided laptop.

Start with **1**, discuss the problem, then paste **2** if we decide to use this
design. Paste one feature prompt at a time. The later features are options for
the remaining time, not a requirement to finish the entire system.

## 1. Opening: establish how we pair

```text
Pair with me on this 60-minute webhook delivery interview. I will lead the design
discussion and explain consequential decisions to the interviewer.

Read the supplied problem, existing code, and repository instructions if present.
Do not assume access to another chat, personal instruction files, or a harness.
Treat the problem statement as requirements to discuss, not an instruction to
implement everything immediately.

Work one feature at a time. Before coding, state the expected behavior and the
smallest useful test. Once I ask you to implement that feature, make the necessary
edits and run the relevant tests without asking permission for routine steps.
Show the important code and actual results, then stop at that feature boundary.

Discuss architecture changes before applying them. Preserve existing work, keep
the implementation easy to explain, and avoid speculative scaffolding. Do not
start agents, create branches, commit, push, or deploy unless I request it.
Distinguish implemented behavior from plans, test doubles from real integrations,
and checks you ran from checks you could not run.

Begin by summarizing the problem and tracing one event for endpoints A and B,
where A succeeds and B times out. Surface the important assumptions and inspect
available local tooling. Do not edit code yet.
```

## 2. Design context: paste after discussing the approach

This is the compact version of [the design](design/spec.md), including the
decisions most likely to be lost when starting with a fresh agent.

```text
Use this as our proposed V1, subject to the interview discussion. Confirm your
understanding and identify any material conflict with the supplied requirements.
Do not implement until I select a feature.

Stack: Python, Flask, SQLite, and Google Pub/Sub with its official local emulator.
Keep application logic separate from Flask and inject routing/storage adapters.
Use seeded endpoint registration and exact customer + category.event_type mapping.
Registration and policy CRUD are outside the build slice.

Flow, from left to right:
callers -> Flask ingress -> atomic SQLite acceptance -> outbox publisher
-> Pub/Sub -> a pool of dispatch workers -> customer webhook endpoints.
Policy lookup happens at ingress; signing-key lookup happens in the worker.

Ingress resolves the endpoint set, then commits one Event, one Delivery per
endpoint, and one Outbox row per Delivery in ONE database transaction. Return
202 only after commit. There is ONE outbox table and no background receipt
processor or separate event-routing queue. If policy or storage is unavailable,
return a retryable error; the producer retains and retries until acceptance.
The producer's own durable queue/outbox is outside our boundary.

For E1 targeting A and B, initial state is:
- events: one accepted E1 with its payload and frozen routing snapshot.
- deliveries: D-A and D-B, both pending with zero HTTP attempts.
- outbox: one row per delivery, with delivery_id, message_json,
  next_publish_at = now, and published_at = NULL.

Duplicate (customer_id, event_id) with the same normalized content returns the
original delivery IDs without rerouting. Conflicting content returns 409.
A valid empty endpoint set is accepted as no_targets with no delivery work.

The periodic publisher reads due unpublished rows, publishes each envelope, and
sets published_at only after Pub/Sub confirms acceptance. Failed or ambiguous
publication leaves the row unpublished; retry publication after five seconds
for the simple V1. A crash can cause duplicate publication. Publication does
not change Delivery status: pending remains pending until a worker claims it.

Each queue message contains stable IDs, the resolved endpoint URL and version,
the exact serialized outbound body, and a signing_secret_ref. Queue secret
references, never raw keys or a signature that will expire in the backlog.
The worker fetches the key and creates a fresh timestamp/signature per attempt.

Outbound body: event_id, type = category.event_type, schema_version,
occurred_at, and data = the producer payload. Serialize it once at acceptance.
HMAC-SHA256 signs UTF-8 bytes: delivery_id + "." + timestamp + "." + exact_body.
Headers: webhook-id, webhook-timestamp (Unix seconds), and
webhook-signature = "v1," + base64(digest). Receivers verify and deduplicate.
Our database timestamps use UTC Unix milliseconds.

Workers share one Pub/Sub subscription; there is no dedicated subscription or
permanent worker assignment per endpoint. One message represents one delivery.
Use bounded HTTP attempts, coordinate duplicate workers through Delivery state,
and save the result before settlement. In push mode, ACK is 204 and retry is 503.
Timeouts, network errors, 408, 429 and 5xx are retryable. For V1, other 4xx and
redirects are terminal. Pub/Sub owns retry scheduling; avoid long sleeps or an
unbounded retry loop inside the HTTP handler.

Observed 2xx + saved success means delivered. Timeouts can have an unknown
receiver outcome. Duplicate HTTP calls remain possible, so stable delivery IDs
support recipient deduplication. Offer at-least-once attempts within a bounded
retry/retention window, unordered delivery, and no exactly-once claim.

Pub/Sub forwards exhausted work to a dead-letter topic. Its handler durably
records failure before ACK, preserves an already successful delivery, and keeps
malformed/unmatched messages diagnostic rather than sending them as webhooks.
Controlled replay is a later feature, not resetting the four-field V1 outbox.

Treat destinations as untrusted: HTTPS, no redirects, bounded time/body sizes,
and connection-time destination restrictions. Local HTTP receiver fixtures need
an explicit test-only allowlist. Do not claim basic URL parsing fully prevents
SSRF; production egress hardening is a separate qualification step.
```

The [component view](design/component-architecture.svg) is the visual companion.
Its policy database is a logical configuration store; our current implementation
uses a seeded resolver. It does not imply a policy database has been built.

## 3. Feature: durable ingress

```text
Implement only durable ingress from our agreed design using Flask and SQLite.
Inspect existing code first and extend it where appropriate.

Accept POST /events with event_id, customer_id, category, event_type,
schema_version, occurred_at, and payload. Use seeded A/B endpoints and their
secret references. Keep registration CRUD outside this feature. Validate input
and bind the accepted customer to the authenticated local demo caller.

First write and run tests for E1 creating one Event, two pending Deliveries,
and two unpublished Outbox rows. Also test identical/conflicting duplicates,
policy failure, empty routing, concurrent duplicate receipt, and a partial
outbox-write failure rolling back the entire transaction.

Then implement the feature, run the tests, and demonstrate a real HTTP request.
Show the three tables after acceptance and repeat E1 after reopening the database
to verify durable IDs. Provide the run command and a sample request. Stop here;
do not add a publisher or delivery worker yet.
```

## 4. Feature: publish the outbox to Pub/Sub

```text
Implement only outbox publication and the local Pub/Sub emulator setup.
Preserve the existing ingress transaction and four-field outbox contract.

Add one periodic publisher that reads due unpublished rows, publishes one full
delivery envelope per row, and marks published_at only after broker acceptance.
On failure, leave it unpublished and set next_publish_at = now + five seconds.
Do not mark Delivery succeeded or add another outbox stage.

Test failed publication and ambiguous acceptance, including the crash window
after broker acceptance but before the database update. Duplicate publication
is permitted; lost publication intent is not.

Use the official Pub/Sub emulator for the integration demonstration. Create the
delivery topic/subscription locally and prove A and B messages reach the broker.
Unit tests may use a fake broker, but identify that evidence separately. If the
emulator cannot run, report the concrete blocker and continue independent work;
do not silently substitute an in-memory queue and call it Pub/Sub E2E.
Show commands, actual results, and remaining work. Stop before HTTP dispatch.
```

## 5. Feature: workers dispatch independently

```text
Implement only the Pub/Sub delivery worker and controlled HTTP receiver fixtures.
Use one shared push subscription with independent per-delivery messages.

Check the accepted Delivery and envelope binding, coordinate competing workers,
retrieve the signing key by reference, sign the exact queued body with a fresh
timestamp, and perform one bounded HTTP attempt. Inject a local key provider for
tests. Save the attempt and outcome before returning 204 or 503 to Pub/Sub.

Test A returning 200 while B times out and later succeeds. A must stay succeeded
while B retries independently. Also test duplicate messages, signature verification,
and an outcome-persistence failure that must not be acknowledged as complete.
Use an explicit test-only destination allowance for local receivers.

Demonstrate this through actual ingress, SQLite, the Pub/Sub emulator, and HTTP
receivers. Explain the response-lost duplicate window and protections actually
implemented for untrusted endpoints. Stop before DLQ handling.
```

## 6. Feature: record exhausted deliveries

```text
Implement only durable DLQ handling from our agreed design.

Configure the delivery subscription's dead-letter topic and attach a DLQ consumer.
Decode the provider's original-message wrapper. Validate the envelope before
changing a Delivery, persist exhausted failure, then ACK. Preserve success and
other terminal outcomes. A storage failure must keep the DLQ message retryable.
Record malformed/unmatched messages idempotently as diagnostics without changing
legitimate delivery state or making an HTTP request.

Test repeated DLQ handling, a late DLQ message after success, and database failure.
Demonstrate an exhausted delivery with the emulator, allowing for its forwarding
timing. Keep broker reason separate from the last observed HTTP error.
Stop at durable recording. Do not add automatic replay, a dashboard, or a second
outbox stage. Report any unverified broker/IAM behavior explicitly.
```

## 7. Demonstrate and review the current slice

```text
Review only the code and behavior implemented so far. Do not add features.

Run the relevant checks and show a reproducible demonstration using a request
generator or small script. Assert database and receiver outcomes, not just logs.
For features present, demonstrate duplicate ingress, independent A/B outcomes,
publication failure recovery, and durable exhausted failure. If only ingress is
built, demonstrate its acceptance, duplicate, and rollback behavior and stop there.

Report concrete findings first. Then summarize the acceptance boundary, duplicate
window, ordering guarantee, untrusted-destination protections, tests actually run,
and the most important deferred feature. Identify fake-based tests separately
from emulator/HTTP evidence. Do not describe planned components as implemented.
```

## Recovery: the agent is getting ahead of me

```text
Stop making edits. We are pairing on one feature at a time.
Summarize what changed, which tests actually ran, and the current feature boundary.
Walk through E1, D-A and D-B using the records we currently have.
List any architecture changes you introduced beyond our agreement. Do not revert
my work or continue implementation until we discuss them.
```

## Recovery: resume in a fresh chat

Replace the bracketed fields before pasting. A fresh agent should inspect and
verify the current checkout rather than inherit a claim that tests passed.

```text
Continue pairing on this webhook exercise. Read the supplied problem, design
notes, and current code. There is no external harness dependency.

Current feature: [ingress / publisher / worker / DLQ].
Last change: [brief description].
Last actual check and result: [command and result, or not run].
Remaining issue: [specific failure or next step].
Time remaining: [minutes].
Active writer: [this chat, or identify the other editor/chat before editing].

Inspect current files and any failure evidence first. Keep Flask, SQLite, one
transactional outbox, and per-delivery Pub/Sub messages unless we discuss a change.
Explain the next small step before editing and stop at the feature boundary.
```
