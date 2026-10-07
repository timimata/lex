from typing import Any

import pytest

from lex import probe

HEALTHY: dict[str, tuple[int, Any, float]] = {
    "/api/health": (200, {"status": "ok", "system": "s"}, 3.0),  # a cold start, under its bar
    "/api/articles/lei-7-2009/238?as_of=2011-06-01": (200, {"text": "Férias."}, 0.2),
    "/api/search?q=f%C3%A9rias&k=3": (200, [{"article": "238"}], 0.3),
    "/api/answer": (200, {"cached": True}, 0.4),
    "/nada-que-exista": (404, None, 0.2),
    "/api/usage": (200, {"counts": {"cached": 1}}, 0.2),
}


def serve(replies: dict[str, tuple[int, Any, float]], monkeypatch: pytest.MonkeyPatch) -> None:
    def fetch(url: str, body: Any = None) -> tuple[int, Any, float]:
        return replies[url.removeprefix("https://demo")]

    monkeypatch.setattr(probe, "fetch", fetch)


def test_a_healthy_demo_passes_every_check(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(HEALTHY, monkeypatch)
    checks, usage = probe.probe("https://demo/")
    assert [c.problem for c in checks] == [""] * 6
    assert usage == {"counts": {"cached": 1}}
    assert probe.main(["https://demo"]) == 0


def test_slowness_an_error_or_a_paid_answer_fails_the_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(
        {
            **HEALTHY,
            "/api/articles/lei-7-2009/238?as_of=2011-06-01": (200, {"text": "Férias."}, 6.5),
            "/api/search?q=f%C3%A9rias&k=3": (503, None, 0.3),
            "/api/answer": (200, {"cached": False}, 0.4),  # the cache lost the example
        },
        monkeypatch,
    )
    problems = {c.name: c.problem for c in probe.probe("https://demo")[0] if c.problem}
    assert problems == {
        "article": "6.5 s, over the 5 s bar",
        "search": "status 503, expected 200",
        "example answer": "the example was not served from the cache: it spent the quota",
    }
    assert probe.main(["https://demo"]) == 1
