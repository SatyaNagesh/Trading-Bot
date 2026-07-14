"""Monitoring — Prometheus metrics, health checks, and structured logging export."""

from datetime import datetime, timezone
from typing import Any

import prometheus_client
from prometheus_client import Counter, Histogram, Gauge

from packages.core.logging import get_logger

logger = get_logger("monitoring")

_request_count = Counter("quantlab_requests_total", "Total requests", ["service", "method"])
_request_duration = Histogram("quantlab_request_duration_seconds", "Request duration", ["service"])
_active_orders = Gauge("quantlab_active_orders", "Active orders")
_model_predictions = Counter("quantlab_model_predictions_total", "Model predictions", ["model"])
_errors_total = Counter("quantlab_errors_total", "Total errors", ["service", "error_type"])
_memory_entries = Gauge("quantlab_memory_entries", "Memory entries by tier", ["tier"])


def track_request(service: str, method: str):
    _request_count.labels(service=service, method=method).inc()


def track_duration(service: str):
    return _request_duration.labels(service=service).time()


def track_prediction(model: str):
    _model_predictions.labels(model=model).inc()


def track_error(service: str, error_type: str):
    _errors_total.labels(service=service, error_type=error_type).inc()


def set_active_orders(count: int):
    _active_orders.set(count)


def set_memory_entries(tier: str, count: int):
    _memory_entries.labels(tier=tier).set(count)


def metrics_app():
    from prometheus_client import make_asgi_app
    return make_asgi_app()


def health_check(services: dict[str, bool]) -> dict[str, Any]:
    all_healthy = all(services.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": services,
    }
