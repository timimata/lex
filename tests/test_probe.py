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
    checks, usage, _ = probe.probe("https://demo/")
    # Health, article, search, each of the page's examples, the unknown path, usage.
    assert [c.problem for c in checks] == [""] * (5 + len(probe.examples()))
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
    lost = "the example was not served from the cache: it spent the quota"
    assert problems == {
        "article": "6.5 s, over the 5 s bar",
        "search": "status 503, expected 200",
        **{f"example {n}": lost for n in range(1, len(probe.examples()) + 1)},
    }
    assert probe.main(["https://demo"]) == 1


def test_every_example_has_its_date_so_it_stays_in_the_cache() -> None:
    assert all(e["as_of"] for e in probe.examples())


def test_the_live_check_spends_one_answer_and_fails_on_a_dead_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve({**HEALTHY, "/api/answer": (200, {"cached": False}, 2.0)}, monkeypatch)
    checks, _, _ = probe.probe("https://demo", live=True, asked=[])
    assert [c.name for c in checks if not c.problem][-1] == "live answer"
    # A revoked key: the demo cannot answer, and says so with a 503.
    serve({**HEALTHY, "/api/answer": (503, {"detail": "x"}, 0.3)}, monkeypatch)
    checks, _, _ = probe.probe("https://demo", live=True, asked=[])
    assert checks[-1].name == "live answer" and checks[-1].problem == "status 503, expected 200"


def test_a_recorded_probe_says_whether_it_met_a_cold_start(tmp_path: Any) -> None:
    import datetime as dt
    import json

    now = dt.datetime.now(dt.UTC)
    checks = [probe.Check("health", 200, 4.0), probe.Check("article", 200, 0.2)]
    path = tmp_path / "probe.jsonl"
    young = {"started_at": (now - dt.timedelta(seconds=3)).isoformat(), "build": {"commit": "c"}}
    probe.record(path, "https://demo", checks, young)
    probe.record(path, "https://demo", checks, {"started_at": "2026-10-01T00:00:00+00:00"})
    first, second = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    assert first["cold"] is True and first["build"] == {"commit": "c"}
    assert second["cold"] is False and second["checks"][0]["name"] == "health"
