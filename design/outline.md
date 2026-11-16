# Rate limiter component design

Derived from [spec.md](spec.md). Interfaces below are proposed contracts, not
implemented APIs. Open requirements in the spec remain open.

## Component boundaries

```text
Traffic -> TrafficHandler -> TenantPolicyRegistry.resolve(tenant_hostname)
               |
               +-> RateLimiter.check(identity, policy, cost)
               |             |
               |             +-> BucketStore.consume(key, policy, cost)
               |                           |
               |                           +-> TokenBucket.evaluate(...)
               |
               +-> Success: forward request to tenant resource
               +-> Rate limited: return HTTP 429, do not forward

Administration -> TenantPolicyRegistry (tenant registrations and policies)
```

The administration path changes configuration; the request path reads it. The
NLB's placement is intentionally omitted until the traffic protocol is clarified.

| Component | Responsibility | Does not own |
| --- | --- | --- |
| TrafficHandler | Extract and validate tenant hostname; obtain client identity if required, invoke limiter, translate result into transport behavior | Token arithmetic or policy storage |
| TenantPolicyRegistry | Map tenant hostnames to policy definitions; resolve a tenant policy | Mutable token balances |
| RateLimiter | Accept supplied tenant policy and coordinate atomic bucket consumption; expose a transport-independent decision API | Forwarding or queuing traffic |
| TokenBucket | Calculate refill, affordability, new balance and retry delay from explicit inputs | Network I/O, identity lookup or scheduling |
| BucketStore | Own bucket state and serialize consumption for the same key | Selecting a tenant's policy |
| Clock | Supply time to accounting, replaceable in tests | Timers to refill idle buckets |

These boundaries can be classes in one solution.py; they do not require separate
modules or deployed services. The registry and bucket store are logical storage
boundaries; their physical implementations remain undecided.

## Proposed data contracts

```text
RequestIdentity:
    tenant_id = incoming request hostname
    client_id (only if per-client buckets are selected)

TenantRegistration:
    tenant_id, policy_id

TenantPolicy:
    tenant_id, rate_limit (tokens/second), burst_limit (extra token allowance)
    policy_id/version (proposed metadata)

BucketKey (scope unresolved):
    tenant_id for a shared tenant bucket
    OR (tenant_id, client_id) for separate client buckets

BucketState:
    tokens, last_refill_time, applied_policy_version

GateResult:
    status = SUCCESS | RATE_LIMITED
    remaining_tokens
    retry_after (optional)
    policy_version (if versioning is adopted)

Transport mapping:
    SUCCESS -> forward to tenant resource and relay its response
    RATE_LIMITED -> HTTP 429 Too Many Requests; no forwarding or queuing

CheckResult:
    decision OR explicit configuration/dependency error
```

Policy lookup is always per tenant hostname. Bucket scope is a separate choice:
a shared tenant bucket bounds aggregate tenant traffic; per-client buckets apply
the tenant's policy independently to each client. Do not assume either scope yet.
Policy version supports detecting changes; it must not silently create a new
full bucket on each update.

Unknown tenants and unavailable dependencies are distinct from an exhausted
bucket. The traffic handler's response remains open. Hostname selection is not
caller authentication. Define hostname normalization and trusted forwarding
before implementing the transport adapter.

## Request flow and atomicity

1. TrafficHandler obtains the incoming request hostname as tenant_id using the
   agreed extraction/normalization rules. Caller authentication is separate.
2. TrafficHandler resolves a policy from TenantPolicyRegistry. An absent tenant or
   policy produces an explicit unresolved-configuration result for now.
3. TrafficHandler supplies identity, TenantPolicy and cost to RateLimiter.check.
   RateLimiter builds the BucketKey for the agreed scope and calls BucketStore.consume.
4. Within one atomic operation for that key, BucketStore reads or initializes
   state, obtains accounting time, invokes TokenBucket, and stores updated state.
   Initialization and policy-change rules must be agreed before implementation.
5. RateLimiter returns SUCCESS or RATE_LIMITED. On SUCCESS, TrafficHandler
   forwards the original request once to the tenant resource and relays the
   resource's response; gate success does not itself mean the resource returned
   HTTP 200. On RATE_LIMITED, return HTTP 429 without forwarding or queuing.

Do not expose a separate uncoordinated read/evaluate/write sequence to callers:
two requests could otherwise spend the same tokens. Different keys should not
require one global lock. A local store could use per-key synchronization; a
distributed implementation needs atomic execution at the state authority.
Reading time inside the serialized operation avoids stale request timestamps.

## Token bucket calculation

Map policy.rate_limit to refill_rate. Capacity and initial balance are
policy.rate_limit + policy.burst_limit; request cost is one token.

For positive request cost and refill rate:

```text
effective_now = max(now, state.last_refill_time)
elapsed = effective_now - state.last_refill_time
available = min(policy.capacity,
                state.tokens + elapsed * policy.refill_rate)

if cost <= available:
    next_tokens = available - cost
    allowed = true
    retry_after = absent
else:
    next_tokens = available
    allowed = false
    retry_after = (cost - available) / policy.refill_rate

next_timestamp = effective_now
```

Proposed safeguards: reject invalid capacity/rate/cost; treat cost above capacity
as permanently unaffordable rather than returning a misleading finite retry.
Final validation rules remain open. Retry delay is advisory: competing requests
can consume future tokens. Use fractional or fixed-point token accounting to
preserve refill credit. Clock ownership depends on storage deployment; use a
monotonic clock locally, and a consistent authority for shared state.

Example: with an empty bucket, capacity 200, rate 100/second, and elapsed time
0.25 seconds, available is 25. A one-token request is allowed and stores 24.
A request at the same instant sees 24, not the original 25.

## Implementation checkpoints — tests first

1. Agree on initial balance, valid policy/cost values, and decision shape. Add
   deterministic TokenBucket tests for burst exhaustion, partial refill, cap,
   denial without debit, and clock behavior; observe failure, then implement.
2. Agree on bucket scope. Add registry and limiter tests for hostname-based
   policy lookup and isolation under that scope. Implement the small in-memory integration if selected.
3. Add a synchronized concurrency test: with one token and simultaneous requests
   for one key, exactly one succeeds. Implement atomic consumption and validate
   the actual chosen store rather than claiming distributed safety from local tests.
4. Once agreed, test unknown-tenant handling, policy changes and dependency
   failures. Add the traffic adapter only after protocol and denial behavior
   are specified. Review the diff and run the relevant suite at each checkpoint.

Implementation and testing can be delegated in small checkpoints; the lead owns
the spec, one-writer handoffs, integration, review and reporting in the main chat.

## Verification status

Design only. Product code and tests remain unchanged. No behavior tests run.
Expected test command: `.venv/bin/python -m unittest discover -s tests -v`.
