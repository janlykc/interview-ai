"""Simulated traffic through the real handler; no HTTP, sleeps or benchmarking."""

import argparse
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.handler import InMemoryPolicyRegistry, RateLimitHandler
from src.limiter import RateLimitingComponent
from src.models import Request, Response, TenantPolicy


class SimulatedClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def run_scenarios(rate=10, burst=5, seconds=3):
    """Return {phase: (sent, allowed, rejected)} for fresh scenario buckets."""
    if any(type(value) is not int for value in (rate, burst, seconds)):
        raise ValueError("Rate, burst and seconds must be integers")
    if rate <= 0 or burst < 0 or seconds <= 0:
        raise ValueError("Rate and seconds must be positive; burst nonnegative")

    policy = TenantPolicy("traffic.example", rate, burst)
    request = Request(policy.tenant_id)

    def setup():
        clock = SimulatedClock()
        registry = InMemoryPolicyRegistry(lambda: {policy.tenant_id: policy})
        handler = RateLimitHandler(
            registry, RateLimitingComponent(clock), lambda _: Response(200)
        )
        return clock, handler

    def send(handler, count):
        statuses = [handler.handle(request).status_code for _ in range(count)]
        if any(status not in (200, 429) for status in statuses):
            raise RuntimeError("Unexpected response from traffic handler")
        return count, statuses.count(200), statuses.count(429)

    clock, handler = setup()
    allowed = rejected = 0
    # Compute absolute timestamps rather than accumulating floating point steps.
    for index in range(rate * seconds):
        clock.now = index / rate
        _, passed, denied = send(handler, 1)
        allowed += passed
        rejected += denied
    results = {"sustained": (rate * seconds, allowed, rejected)}

    clock, handler = setup()
    results["burst"] = send(handler, rate + burst + 1)
    clock.now = 1.0
    results["refill"] = send(handler, rate)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=("Simulated token-bucket traffic. Burst is EXTRA quota; "
                     "total capacity = rate + burst. No HTTP or real-time load.")
    )
    parser.add_argument("--rate", type=int, default=10, help="Tokens/second (positive)")
    parser.add_argument("--burst", type=int, default=5, help="Extra token quota (nonnegative)")
    parser.add_argument("--seconds", type=int, default=3, help="Simulated duration (positive)")
    args = parser.parse_args(argv)
    try:
        results = run_scenarios(args.rate, args.burst, args.seconds)
    except ValueError as error:
        parser.error(str(error))

    capacity = args.rate + args.burst
    expected = {
        "sustained": (args.rate * args.seconds, args.rate * args.seconds, 0),
        "burst": (capacity + 1, capacity, 1),
        "refill": (args.rate, args.rate, 0),
    }
    print(f"Simulated traffic: rate={args.rate}/s extra_burst={args.burst} capacity={capacity}")
    for phase, (sent, allowed, rejected) in results.items():
        verdict = "PASS" if results[phase] == expected[phase] else "FAIL"
        print(f"{phase}: sent={sent} allowed={allowed} rejected={rejected} "
              f"expected={expected[phase]} {verdict}")
    return 0 if results == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
