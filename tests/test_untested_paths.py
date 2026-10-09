"""Paths no test exercised until 2026-10-08 (ROADMAP, Phase 11): the polite fetcher, the
embedder's wait on a rate limit, the gate's change of day, and the eval's gates that stop a run."""

import datetime as dt
import io
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from lex.ingest import fetch
from lex.ingest.fetch import Fetcher


class Clock:
    """A monotonic clock and sleep that only move when told, recording every pause."""

    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(round(seconds, 3))
        self.now += seconds


class Response(io.BytesIO):
    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def test_the_fetcher_waits_between_requests_backs_off_and_never_fetches_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock()
    monkeypatch.setattr("lex.ingest.fetch.time.monotonic", clock.monotonic)
    monkeypatch.setattr("lex.ingest.fetch.time.sleep", clock.sleep)
    replies: list[Any] = [
        urllib.error.HTTPError("https://example.org/a", 503, "busy", {}, None),  # type: ignore[arg-type]
        b"artigo",
        b"outro",
    ]
    asked: list[str] = []

    def urlopen(request: Any, timeout: float) -> Response:
        asked.append(request.get_header("User-agent"))
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return Response(reply)

    monkeypatch.setattr("lex.ingest.fetch.urllib.request.urlopen", urlopen)
    fetcher = Fetcher(tmp_path, min_interval=2.0)

    first = fetcher.get("https://example.org/a")
    assert first.body == b"artigo" and fetcher.requests == 2
    assert clock.slept[0] == fetch.BACKOFF_S[0]  # a 503 is waited out, then asked again
    assert all(agent == fetch.USER_AGENT for agent in asked)
    fetcher.get("https://example.org/b")
    assert clock.slept[-1] == 2.0  # one request at a time, 2 s apart
    # Cached: neither asked again, nor reachable offline if it never was.
    assert Fetcher(tmp_path, offline=True).get("https://example.org/a").body == b"artigo"
    with pytest.raises(LookupError):
        Fetcher(tmp_path, offline=True).get("https://example.org/c")
    assert replies == []


def test_the_fetcher_gives_up_on_a_client_error_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def urlopen(request: Any, timeout: float) -> Response:
        calls.append(1)
        raise urllib.error.HTTPError("https://example.org/x", 404, "gone", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr("lex.ingest.fetch.urllib.request.urlopen", urlopen)
    monkeypatch.setattr("lex.ingest.fetch.time.sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        Fetcher(tmp_path, min_interval=0).get("https://example.org/x")
    assert len(calls) == 1 and not list(tmp_path.glob("*.json"))  # nothing cached


def test_the_embedder_waits_out_a_rate_limit_and_raises_past_its_waits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import openai

    import lex.retrieval.dense as dense

    class Limited(openai.RateLimitError):
        def __init__(self) -> None:  # the client's 429, without a response to build it from
            Exception.__init__(self, "slow down")

    limited = Limited()
    slept: list[float] = []
    monkeypatch.setattr("lex.retrieval.dense.time.sleep", slept.append)

    class Embeddings:
        def __init__(self, failures: int) -> None:
            self.failures = failures

        def create(self, model: str, input: list[str], dimensions: int) -> Any:
            if self.failures:
                self.failures -= 1
                raise limited
            data = [type("D", (), {"embedding": [3.0, 4.0]})() for _ in input]
            return type("R", (), {"data": data})()

    embedder = dense.ApiEmbedder(api_key="k", waits=(30, 60))
    embedder.client = type("C", (), {"embeddings": Embeddings(2)})()
    assert embedder.encode(["a"]) == [[0.6, 0.8]]  # normalised, after two waits
    assert slept == [30, 60]
    embedder.client = type("C", (), {"embeddings": Embeddings(3)})()
    with pytest.raises(openai.RateLimitError):
        embedder.encode(["a"])


def test_the_gate_starts_a_new_day_with_the_quota() -> None:
    from lex.api.app import Gate, Limits

    day = [dt.date(2026, 10, 8)]
    gate = Gate(Limits(per_visitor_per_hour=10, per_day=1), lambda: 0.0, lambda: day[0])
    assert gate.admit("a") is None
    assert gate.admit("b") == "day_cap"
    day[0] = dt.date(2026, 10, 9)  # the quota's day turns: the cap starts again
    assert gate.admit("b") is None


def test_the_eval_refuses_what_it_cannot_stand_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import lex.eval.__main__ as cli
    from lex.eval import gates, judge, results

    monkeypatch.setattr(results, "RESULTS", tmp_path)
    (tmp_path / "dev").mkdir()
    with pytest.raises(SystemExit, match="no dev answers"):
        gates.dev_run("sys")
    (tmp_path / "dev" / "sys.json").write_text(json.dumps({"config": {}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="not an answers run"):
        gates.dev_run("sys")

    # measured_judge: nothing measured; measured with another model; a failed check.
    monkeypatch.setattr(results, "bench_version", lambda split: {"scored": "dev"})
    with pytest.raises(SystemExit, match="the judge is not measured"):
        gates.measured_judge("sys")
    check: dict[str, Any] = {
        "bench": {"scored": "dev"},
        "config": {
            "judge": "another-model",
            "judge_prompt": gates.prompt_version(),
            "judge_params": gates.JUDGE_PARAMS,
        },
        "summary": {"passed": False},
    }
    path = tmp_path / "dev" / "judge-check.json"
    path.write_text(json.dumps(check), encoding="utf-8")
    with pytest.raises(SystemExit, match="changed since its check"):
        gates.measured_judge("sys")
    check["config"]["judge"] = judge.JUDGE_MODEL
    path.write_text(json.dumps(check), encoding="utf-8")
    with pytest.raises(SystemExit, match="failed its known-answer checks"):
        gates.measured_judge("sys")
    # Other parameters are another judge, checked under a name of its own.
    assert gates.checked_as(gates.judge_params()) == "judge-check"
    monkeypatch.setenv("JUDGE_PARAMS", "{}")
    assert gates.checked_as(gates.judge_params()) == "judge-check-provider"
    monkeypatch.setenv("JUDGE_PARAMS", '{"temperature": 1}')
    assert gates.checked_as(gates.judge_params()) == "judge-check-temperature1"
    with pytest.raises(SystemExit, match="the judge is not measured"):
        gates.measured_judge("sys")
    (tmp_path / "dev" / "judge-check-temperature1.json").write_text(
        json.dumps(check), encoding="utf-8"
    )
    with pytest.raises(SystemExit, match="parameters changed since its check"):
        gates.measured_judge("sys")
    monkeypatch.delenv("JUDGE_PARAMS")
    labelled = {
        "bench": {"scored": "dev"},
        "config": {"judge": "another-model", "judge_prompt": gates.prompt_version()},
        "summary": {"agreement": {}},
    }
    (tmp_path / "dev" / "judge-sys.json").write_text(json.dumps(labelled), encoding="utf-8")
    with pytest.raises(SystemExit, match="changed since it was measured"):
        gates.measured_judge("sys")

    # regress: nothing committed to compare with.
    monkeypatch.setattr(cli, "demo_dev_run", lambda: None)
    with pytest.raises(SystemExit, match="no committed dev run"):
        cli.regress(cli.Stores(), [])
