"""Flask HTTP boundary for durable webhook event acceptance."""

import hmac
import os

from flask import Flask, abort, jsonify, request
from werkzeug.exceptions import HTTPException

from webhook_service.adapters.seeded import example_resolver
from webhook_service.adapters.sqlite import SQLiteRepository
from webhook_service.ingress import EventIngressService
from webhook_service.models import IngressError


def create_app(config=None, *, service=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("WEBHOOK_DB_PATH", "var/webhooks.db"),
        INGRESS_TOKEN=os.environ.get("WEBHOOK_INGRESS_TOKEN"),
        CUSTOMER_ID=os.environ.get("WEBHOOK_CUSTOMER_ID", "C1"),
        MAX_CONTENT_LENGTH=262144,
    )
    app.config.update(config or {})
    token = app.config["INGRESS_TOKEN"]
    customer_id = app.config["CUSTOMER_ID"]
    if not token or not customer_id:
        raise ValueError("Set WEBHOOK_INGRESS_TOKEN and a nonempty customer identity")
    if service is None:
        service = EventIngressService(
            SQLiteRepository(app.config["DATABASE"]), example_resolver(customer_id),
        )

    @app.post("/events")
    def accept_event():
        supplied = request.headers.get("Authorization", "").encode("utf-8")
        if not hmac.compare_digest(supplied, f"Bearer {token}".encode("utf-8")):
            abort(401)
        event = request.get_json()
        if isinstance(event, dict) and event.get("customer_id") is not None and event["customer_id"] != customer_id:
            abort(403)
        return jsonify(service.accept(event).as_dict()), 202

    @app.errorhandler(IngressError)
    def ingress_error(error):
        response = jsonify(error=error.code)
        response.status_code = error.status
        if error.status == 503:
            response.headers["Retry-After"] = "5"
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        codes = {
            400: "invalid_json_request", 401: "unauthorized", 403: "customer_not_authorized",
            404: "not_found", 405: "method_not_allowed", 413: "event_too_large",
            415: "content_type_must_be_json",
        }
        response = error.get_response()
        response.data = app.json.dumps({"error": codes.get(error.code, "http_error")})
        response.content_type = "application/json"
        return response

    @app.errorhandler(RecursionError)
    def nested_json_error(error):
        return jsonify(error="invalid_json_request"), 400

    return app
