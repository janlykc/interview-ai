import json

from app import create_app
from test_ingress import IngressFixture, example_event
from webhook_service.models import RoutingUnavailable


class ApiTests(IngressFixture):
    def setUp(self):
        super().setUp()
        self.app = create_app({
            "TESTING": True, "INGRESS_TOKEN": "test-token", "CUSTOMER_ID": "C1",
            "MAX_CONTENT_LENGTH": 2048,
        }, service=self.service)
        self.client = self.app.test_client()

    def request(self, body, token="test-token", path="/events"):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        response = self.client.post(path, data=body, headers=headers)
        return response.status_code, response.get_json()

    def test_http_acceptance_and_repeat_return_same_ids(self):
        first = self.request(json.dumps(example_event()))
        self.assertEqual(first[0], 202)
        self.assertEqual(len(first[1]["delivery_ids"]), 2)
        self.assertEqual(self.request(json.dumps(example_event())), first)
        self.assertEqual(len(self.rows("outbox")), 2)

    def test_http_authentication_and_customer_binding(self):
        self.assertEqual(self.request(json.dumps(example_event()), token=None)[0], 401)
        self.assertEqual(self.request(json.dumps(example_event()), token="wrong")[0], 401)
        other = example_event()
        other["customer_id"] = "OTHER"
        self.assertEqual(self.request(json.dumps(other))[0], 403)
        self.assert_empty()

    def test_http_input_errors(self):
        for body, expected in (("{", 400), ("[]", 400), ('{"event_id":"E1","event_id":"E2"}', 400), ("x" * 2049, 413)):
            with self.subTest(expected=expected, body=body[:40]):
                self.assertEqual(self.request(body)[0], expected)
        self.assertEqual(self.request("{}", path="/unknown")[0], 404)
        self.assert_empty()

    def test_http_conflict(self):
        self.assertEqual(self.request(json.dumps(example_event()))[0], 202)
        changed = example_event()
        changed["payload"] = {"different": True}
        self.assertEqual(self.request(json.dumps(changed))[0], 409)
        self.assertEqual(len(self.rows("outbox")), 2)

    def test_http_policy_outage_returns_retryable_error_without_acceptance(self):
        def unavailable(*args):
            raise RoutingUnavailable("Unavailable")
        self.service.resolver.resolve = unavailable
        self.assertEqual(self.request(json.dumps(example_event()))[0], 503)
        self.assert_empty()
