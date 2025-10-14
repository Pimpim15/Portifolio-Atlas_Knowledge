"""Setup de OpenTelemetry."""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from ..config import get_settings

_tracer_configured = False


def setup_tracing() -> None:
    global _tracer_configured
    if _tracer_configured:
        return

    settings = get_settings()
    resource = Resource.create({"service.name": "atlas-api"})
    provider = TracerProvider(resource=resource)

    endpoint: str | None = (
        str(settings.opentelemetry_endpoint) if settings.opentelemetry_endpoint else None
    )
    if endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
    _tracer_configured = True
