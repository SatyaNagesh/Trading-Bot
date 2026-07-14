"""OpenTelemetry tracing configuration for distributed tracing."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from fastapi import FastAPI

from packages.core.logging import get_logger

logger = get_logger("tracing")

_service_tracers: dict[str, trace.Tracer] = {}


def setup_tracing(service_name: str, otlp_endpoint: str = "http://localhost:4317") -> trace.Tracer:
    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(service_name)
    _service_tracers[service_name] = tracer
    logger.info("tracing_initialized", service=service_name)
    return tracer


def instrument_fastapi(app: FastAPI, service_name: str = "quantlab") -> None:
    FastAPIInstrumentor.instrument_app(app)
    logger.info("fastapi_instrumented", service=service_name)


def get_tracer(service_name: str) -> trace.Tracer:
    return _service_tracers.get(service_name, trace.get_tracer("default"))
