"""Traces of each answer, as OpenTelemetry spans, for a backend such as Langfuse (ADR 0023).

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set and the `trace` extra is installed: then nothing
leaves the machine, and `span` costs a function call. A span carries counts, ids, model names,
tokens and seconds; the question's text only where LEX_TRACE_CONTENT=1, since a visitor's
question would otherwise reach the tracing backend too (ADR 0016's table).
"""

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

_tracer: Any = None


def configure(service: str) -> bool:
    """Start exporting spans to the OTLP endpoint `.env` names; True if it did. Called once by
    an entry point (`python -m lex.api`)."""
    global _tracer
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:  # the extra is not installed: tracing stays off
        return False
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("lex")
    return True


def content() -> bool:
    """Whether spans may carry what a visitor typed."""
    return os.environ.get("LEX_TRACE_CONTENT") == "1"


class Span:
    """What a `span` block can add to as it learns it; a no-op when tracing is off."""

    def __init__(self, inner: Any = None) -> None:
        self.inner = inner

    def set(self, **attributes: Any) -> None:
        if self.inner is not None:
            for key, value in attributes.items():
                if value is not None:
                    self.inner.set_attribute(key, _plain(value))


def _plain(value: Any) -> Any:
    """An attribute value OpenTelemetry takes: a str, bool, int or float, or a list of them."""
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return str(value)


@contextmanager
def span(name: str, attributes: Mapping[str, Any] | None = None) -> Iterator[Span]:
    if _tracer is None:
        yield Span()
        return
    with _tracer.start_as_current_span(name) as inner:
        current = Span(inner)
        current.set(**(attributes or {}))
        yield current
