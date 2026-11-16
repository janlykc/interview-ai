# Multi-tenant API rate limiter

This specification captures the design agreed in the interview discussion.
Current implementation uses in-memory policies and per-tenant bucket state.
Distributed storage and the HTTP transport adapter remain open.

## Agreed requirements

- Provide a traffic-handling service that calls a rate-limiting engine/library
  to decide whether a request is allowed.
- Support multiple tenants. The incoming request hostname is the tenant ID.
- Configure rate-limit policies per tenant; individual client identification and
  bucket scope remain open.
- Use token bucket as the initial algorithm, supporting bounded bursts and a
  sustained request rate. Additional algorithms are deferred.
- Provide a tenant policy registry mapping tenant hostnames to rate limits.
- Store each tenant policy as tenant_id (hostname), rate_limit (tokens/second),
  and burst_limit (extra token allowance above rate_limit). The traffic service retrieves this
  policy and supplies it to the rate limiter.
- Keep policy configuration separate from runtime bucket accounting.
- The gate returns success when allowed so the traffic service can forward the
  original request to the tenant resource. This is an internal success result,
  not an immediate HTTP 200 response to the caller.
- If tokens are insufficient, return a denial mapped to HTTP 429 Too Many
  Requests. Do not forward that request and do not queue it.

## Components and data

1. Traffic-handling service: receives traffic, resolves the applicable identity,
   and invokes the decision engine. Its relationship to the NLB is unresolved.
2. Tenant policy registry: associates a tenant hostname with its policy.
   Policy configuration includes bucket capacity (burst allowance) and token
   refill rate (sustained allowance).
3. Rate-limiting engine/library: evaluates token availability under that policy
   and returns an allow/deny decision.
4. Bucket state: records the current token balance and last refill timestamp
   for each independently limited source. Whether all requests to a tenant share
   one bucket or clients have separate buckets under the tenant policy is open.

## Token accounting

Bucket capacity and initial balance are rate_limit + burst_limit. Refill is
rate_limit tokens per second; each request costs one token. Zero extra burst
quota is allowed. The rate contribution to capacity is one second of allowance.

Use lazy refill on request arrival rather than periodic background filling:

```text
available = min(capacity, tokens + elapsed_time * refill_rate)
if available >= request_cost:
    allow and subtract request_cost
else:
    deny without subtracting request_cost
persist the resulting balance and accounting timestamp
```

Preserve partial refill credit. Each bucket evaluation uses constant-size state
and O(1) arithmetic. Concurrent decisions against the same bucket must not spend
the same tokens twice; the coordination mechanism remains open.

## Illustrative acceptance examples

These numbers illustrate behavior, not production limits. They assume an
initially full bucket and a request cost of one token; those defaults remain open.

| Scenario | Input or action | Expected result |
| --- | --- | --- |
| Burst | Rate 100/second + extra burst 100 = capacity 200; 200 requests at the same instant | All 200 allowed; balance becomes zero |
| Exhausted bucket | One more request at that instant | HTTP 429; no forwarding; balance remains zero |
| Successful gate | Sufficient tokens | Internal success; forward once to tenant resource and return its response |
| Lazy refill | Refill rate 100/second; wait 0.25 seconds after exhaustion | 25 tokens available before charging the next request |
| Capacity cap | Long idle interval | Available tokens do not exceed capacity |
| Tenant policy selection | Requests to tenant-a.example and tenant-b.example | Each resolves the policy registered for its hostname |

## Open decisions

- Meaning and trusted origin of source/client identity: credential, application,
  authenticated user, IP address, or another identifier.
- NLB placement, protocol, and where request-level identity is available.
- Whether limits apply per client only, or also to a shared tenant-wide bucket
  or endpoint scope.
- Unknown-tenant behavior: reject or apply a default policy.
- Hostname extraction and normalization, accepted hostnames, and trusted proxy
  handling. Hostname selects the tenant; it does not authenticate a caller.
- Additional policy validation requirements beyond positive finite rate and
  nonnegative finite burst quota.
- Denial response body and optional Retry-After header.
- Policy updates, disabled clients, and their effect on existing bucket state.
- Local versus distributed state, consistency guarantees, clock source, policy
  caching, state expiry, and failure behavior.
- Required traffic scale, latency target, deployment scope, and acceptable overshoot.

## Verification status

Implemented handler, in-memory registry and per-tenant token bucket. Tests cover
forwarding/429, registry loading, burst capacity, refill and tenant isolation.
