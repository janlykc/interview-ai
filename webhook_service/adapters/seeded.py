from ..models import Endpoint, RoutingSnapshot


class SeededEndpointResolver:
    """Read-only routing fixture. An absent mapping is a valid empty result."""

    def __init__(self, policies):
        self.policies = dict(policies)

    def resolve(self, customer_id, category, event_type):
        return self.policies.get((customer_id, category, event_type), RoutingSnapshot("seed-v1", ()))


def example_resolver(customer_id="C1"):
    return SeededEndpointResolver({
        (customer_id, "billing", "invoice_paid"): RoutingSnapshot("seed-v1", (
            Endpoint("A", customer_id, "1", "https://a.example/webhooks", "secrets/A"),
            Endpoint("B", customer_id, "1", "https://b.example/webhooks", "secrets/B"),
        )),
    })
