import datetime as dt
from typing import Any

import pytest

from lex import tracing
from lex.domain import Answer, Citation


class Echo:
    name = "echo"

    def answer(self, question: str, as_of: dt.date) -> Answer:
        with tracing.span("retrieve", {"k": 5}) as span:
            span.set(given=["lei-7-2009:238"])
        return Answer(text="Resposta.", citations=[Citation(diploma="lei-7-2009", article="238")])


def test_a_span_is_a_no_op_while_tracing_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert tracing.configure("lex-test") is False  # nothing set: nothing leaves the machine
    with tracing.span("answer", {"k": 5}) as span:
        span.set(refused=False)  # accepted, and dropped


@pytest.fixture
def exporter(monkeypatch: pytest.MonkeyPatch) -> Any:
    pytest.importorskip("opentelemetry.sdk")  # the `trace` extra
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    monkeypatch.setattr(tracing, "_tracer", provider.get_tracer("test"))
    return memory


def test_an_answer_is_traced_without_the_question_unless_asked(
    exporter: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from lex.api.app import create_app

    monkeypatch.delenv("LEX_TRACE_CONTENT", raising=False)
    api = TestClient(create_app(Echo(), today=lambda: dt.date(2026, 10, 10)))
    api.post("/api/answer", json={"question": "Quantos dias de férias?"})
    monkeypatch.setenv("LEX_TRACE_CONTENT", "1")
    api.post("/api/answer", json={"question": "Outra pergunta?"})

    spans = exporter.get_finished_spans()
    answers = [s for s in spans if s.name == "answer"]
    retrieves = [s for s in spans if s.name == "retrieve"]
    assert len(answers) == 2 and len(retrieves) == 2
    pairs = zip(retrieves, answers, strict=True)
    assert all(r.parent.span_id == a.context.span_id for r, a in pairs)  # nested in the answer
    assert answers[0].attributes["question_chars"] == len("Quantos dias de férias?")
    assert "question" not in answers[0].attributes  # a visitor's words stay out by default
    assert answers[1].attributes["question"] == "Outra pergunta?"
    assert answers[0].attributes["cited"] == ("lei-7-2009:238",)
    assert retrieves[0].attributes["given"] == ("lei-7-2009:238",)
