import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from lex.domain import Answer, Citation

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from lex.api.app import DISCLAIMER, LISBON, Limits, create_app, leaderboard, lisbon_today

TODAY = dt.date(2026, 9, 30)


class Echo:
    name = "echo"

    def __init__(self) -> None:
        self.asked: list[tuple[str, dt.date]] = []

    def answer(self, question: str, as_of: dt.date) -> Answer:
        self.asked.append((question, as_of))
        return Answer(text="Resposta.", citations=[Citation(diploma="lei-7-2009", article="238")])


@dataclass(frozen=True)
class Version:
    heading: str
    text: str
    valid_from: dt.date
    valid_to: dt.date | None
    introduced_by: str
    source_url: str


HISTORY = [
    Version(
        "Férias", "com majoração", dt.date(2009, 2, 17), dt.date(2012, 8, 1), "lei-7-2009", "u1"
    ),
    Version("Férias", "sem majoração", dt.date(2012, 8, 1), None, "lei-23-2012", "u2"),
]


def library(diploma: str, article: str) -> list[Version]:
    return HISTORY if (diploma, article) == ("lei-7-2009", "238") else []


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def client(system: Echo, limits: Limits | None = None, clock: Clock | None = None) -> TestClient:
    app = create_app(
        system,
        library=library,
        leaderboard=[{"system": "s", "task": "answers"}],
        limits=limits,
        today=lambda: TODAY,
        clock=clock or Clock(),
    )
    return TestClient(app)


def test_an_answer_comes_dated_cited_and_with_the_disclaimer() -> None:
    system = Echo()
    response = client(system).post("/api/answer", json={"question": "Quantos dias de férias?"})

    assert response.status_code == 200
    assert response.json() == {
        "question": "Quantos dias de férias?",
        "as_of": "2026-09-30",
        "system": "echo",
        "answer": {
            "text": "Resposta.",
            "citations": [{"diploma": "lei-7-2009", "article": "238"}],
            "refused": False,
            "timings": {},
            "requests": [],
            "tokens": {},
        },
        "seconds": response.json()["seconds"],
        "cached": False,
        "disclaimer": DISCLAIMER,
    }
    assert 0 <= response.json()["seconds"] < 5
    assert system.asked == [("Quantos dias de férias?", TODAY)]


def test_dates_outside_the_corpus_are_refused() -> None:
    system = Echo()
    api = client(system)
    past = api.post("/api/answer", json={"question": "Férias?", "as_of": "2011-06-01"})

    assert past.json()["as_of"] == "2011-06-01"
    assert (
        api.post("/api/answer", json={"question": "Férias?", "as_of": "2026-10-01"}).status_code
        == 422
    )
    # Tenancy's complete history starts on 2006-06-27, before the Código do Trabalho's.
    assert (
        api.post("/api/answer", json={"question": "Rendas?", "as_of": "2008-01-01"}).status_code
        == 200
    )
    refused = api.post("/api/answer", json={"question": "Rendas?", "as_of": "2006-06-26"})
    assert refused.status_code == 422 and "27/06/2006" in refused.json()["detail"]
    assert system.asked == [("Férias?", dt.date(2011, 6, 1)), ("Rendas?", dt.date(2008, 1, 1))]


def test_a_repeated_question_is_answered_once() -> None:
    system = Echo()
    api = client(system)
    api.post("/api/answer", json={"question": "Quantos  dias de férias?"})
    again = api.post("/api/answer", json={"question": "quantos dias de FÉRIAS?"})

    assert again.status_code == 200
    assert (again.json()["cached"], again.json()["seconds"]) == (True, 0)
    assert len(system.asked) == 1


def test_answers_are_limited_per_visitor_per_hour_and_in_total_per_day() -> None:
    clock = Clock()
    api = client(Echo(), Limits(per_visitor_per_hour=2, per_day=3), clock)

    def ask(n: int, who: str) -> int:
        headers = {"x-real-ip": who}
        return api.post(
            "/api/answer", json={"question": f"Pergunta {n}?"}, headers=headers
        ).status_code

    assert [ask(1, "a"), ask(2, "a"), ask(3, "a")] == [200, 200, 429]
    clock.now = 3600.0  # an hour later the visitor may ask again
    assert ask(4, "a") == 200
    assert ask(5, "b") == 429  # but the day's three answers are spent, for everyone


def test_an_article_shows_the_version_in_force_and_its_timeline() -> None:
    api = client(Echo())
    view = api.get("/api/articles/lei-7-2009/238", params={"as_of": "2011-06-01"}).json()

    assert (view["heading"], view["text"], view["source_url"]) == ("Férias", "com majoração", "u1")
    assert [p["valid_from"] for p in view["versions"]] == ["2009-02-17", "2012-08-01"]
    assert view["disclaimer"] == DISCLAIMER
    assert api.get("/api/articles/lei-7-2009/238").json()["text"] == "sem majoração"
    assert api.get("/api/articles/lei-7-2009/238?as_of=2008-01-01").json()["text"] is None
    assert api.get("/api/articles/lei-7-2009/999").status_code == 404


def test_the_leaderboard_and_health_are_served() -> None:
    api = client(Echo())
    assert api.get("/api/leaderboard").json() == [{"system": "s", "task": "answers"}]
    assert api.get("/api/health").json() == {
        "status": "ok",
        "system": "echo",
        "today": "2026-09-30",
    }
    assert api.post("/api/answer", json={"question": ""}).status_code == 422


class Failing(Echo):
    def answer(self, question: str, as_of: dt.date) -> Answer:
        self.asked.append((question, as_of))
        raise RuntimeError("quota exceeded")


def test_a_failed_answer_is_a_503_and_is_tried_again_next_time() -> None:
    system = Failing()
    api = client(system)
    first = api.post("/api/answer", json={"question": "Férias?"})

    assert first.status_code == 503
    assert first.json()["detail"] == "O Lex não conseguiu responder agora. Tente mais tarde."
    api.post("/api/answer", json={"question": "Férias?"})
    assert len(system.asked) == 2


class Status(Exception):
    """An error from the model's client, which carries the reply's HTTP status."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class APITimeoutError(Exception):
    """Named as the client names a request that took too long."""


class Raising(Echo):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def answer(self, question: str, as_of: dt.date) -> Answer:
        raise self.error


@pytest.mark.parametrize(
    ("error", "told"),
    [
        (
            Status(429, "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"),
            "limite diário",
        ),
        (Status(429, "quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier"), "minuto"),
        (Status(503, "This model is currently experiencing high demand."), "sobrecarregado"),
        (APITimeoutError("Request timed out."), "demorou demasiado"),
    ],
)
def test_the_visitor_is_told_what_stopped_the_answer(error: Exception, told: str) -> None:
    reply = client(Raising(error)).post("/api/answer", json={"question": "Férias?"})

    assert reply.status_code == 503
    assert told in reply.json()["detail"]


def test_a_client_cannot_pick_its_own_address_to_dodge_the_limit() -> None:
    api = client(Echo(), Limits(per_visitor_per_hour=1, per_day=10))

    def ask(n: int, spoofed: str) -> int:
        # The proxy appends the real address last; whatever comes first, the client wrote.
        headers = {"x-forwarded-for": f"{spoofed}, 203.0.113.7"}
        return api.post("/api/answer", json={"question": f"P{n}?"}, headers=headers).status_code

    assert [ask(1, "1.1.1.1"), ask(2, "2.2.2.2")] == [200, 429]


def test_a_failed_answer_costs_the_visitor_nothing() -> None:
    system = Failing()
    api = client(system, Limits(per_visitor_per_hour=1, per_day=1))
    assert api.post("/api/answer", json={"question": "Férias?"}).status_code == 503
    assert api.post("/api/answer", json={"question": "Férias?"}).status_code == 503  # not 429
    assert len(system.asked) == 2


def test_today_is_lisbons_date_even_on_a_utc_server() -> None:
    late = dt.datetime(2026, 9, 30, 23, 30, tzinfo=dt.UTC)  # 00:30 on 1 October in Lisbon
    assert lisbon_today(late) == dt.date(2026, 10, 1)
    winter = dt.datetime(2026, 12, 31, 23, 30, tzinfo=dt.UTC)  # Lisbon is on UTC in winter
    assert lisbon_today(winter) == dt.date(2026, 12, 31)
    assert LISBON.key == "Europe/Lisbon"


@dataclass(frozen=True)
class Found:
    diploma: str
    article: str
    heading: str
    text: str = ""
    introduced_by: str = "lei-7-2009"
    valid_from: dt.date = dt.date(2009, 2, 17)


def test_articles_can_be_searched_by_word_without_a_model() -> None:
    asked: list[tuple[str, dt.date, int]] = []

    def find(q: str, day: dt.date, k: int) -> list[Found]:
        asked.append((q, day, k))
        return [
            Found("lei-7-2009", "238", "Férias", "1 - O período anual de férias tem 22 dias."),
            Found("dl-47344-1966", "1076", "Antecipação de rendas", "Não fala disso."),
        ]

    api = TestClient(create_app(Echo(), find=find, today=lambda: TODAY))
    hits = api.get("/api/search", params={"q": "férias", "k": 999}).json()

    assert hits[0] == {
        "diploma": "lei-7-2009",
        "article": "238",
        "heading": "Férias",
        "excerpt": "1 - O período anual de férias tem 22 dias.",
        "marks": [[23, 29]],  # "férias", for the page to mark
    }
    assert asked == [("férias", TODAY, 200)]  # filtered and cut to k after
    only = api.get("/api/search", params={"q": "férias", "diploma": "dl-47344-1966"}).json()
    assert [h["article"] for h in only] == ["1076"]
    assert TestClient(create_app(Echo())).get("/api/search", params={"q": "x"}).status_code == 404


def test_answers_made_at_deploy_are_served_without_asking_the_system(tmp_path: Path) -> None:
    from lex.api.__main__ import load_answers

    path = tmp_path / "answers.json"
    made = Answer(
        text="Feita no deploy.", citations=[Citation(diploma="lei-7-2009", article="238")]
    )
    rows = [
        {"question": "Quantos dias de férias?", "as_of": "2011-06-01", "answer": made.model_dump()}
    ]
    path.write_text(json.dumps(rows), encoding="utf-8")
    system = Echo()
    api = TestClient(create_app(system, preload=load_answers(path), today=lambda: TODAY))

    reply = api.post(
        "/api/answer", json={"question": "quantos  dias de FÉRIAS?", "as_of": "2011-06-01"}
    )
    assert (reply.json()["answer"]["text"], reply.json()["cached"]) == ("Feita no deploy.", True)
    assert system.asked == []
    assert load_answers(tmp_path / "missing.json") == {}


def test_the_leaderboard_keeps_each_systems_newest_run_and_how_it_was_judged(
    tmp_path: Path,
) -> None:
    def run(name: str, system: str, at: str, summary: dict[str, object], **config: object) -> None:
        record = {"system": system, "run_at": at, "commit": "abcdef123", "summary": summary}
        record["config"] = config
        (tmp_path / f"{name}.json").write_text(json.dumps(record), encoding="utf-8")

    measured = {"known_answer_checks": {"reference": {"as_expected": 40, "cases": 40}}}
    run("a", "demo", "2026-10-01T12:43:00+01:00", {"answerable": {"items": 50}}, task="answers")
    run(
        "b",
        "demo",
        "2026-10-01T15:00:00+01:00",
        {"answerable": {"items": 50}, "correctness": {"answerable": {"correta": 0.8}}},
        task="answers",
        judge={"model": "gemma", "prompt": "p", "measured_on_dev": measured, "unparsed": 0},
    )
    run("c", "demo", "2026-10-01T12:44:00+01:00", {"all": {"items": 50}})  # retrieval
    (tmp_path / "superseded").mkdir()

    board = leaderboard(tmp_path)

    assert [(e["system"], e["task"], e["run_at"][11:16]) for e in board] == [
        ("demo", "answers", "15:00"),
        ("demo", "retrieval", "12:44"),
    ]
    assert board[0]["summary"] == {"answerable": {"items": 50}}
    assert board[0]["correctness"] == {"answerable": {"correta": 0.8}}
    assert board[0]["judge"] == {"model": "gemma", "measured_on_dev": measured}
    assert board[1]["correctness"] is None and board[1]["judge"] is None


def test_the_pages_own_paths_are_served_the_page(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<!doctype html><title>Lex</title>", encoding="utf-8")
    (tmp_path / "app.js").write_text("// built", encoding="utf-8")
    app = create_app(Echo(), static=tmp_path)
    with TestClient(app) as c:
        for path in ("/", "/artigos", "/resultados", "/sobre"):
            response = c.get(path)
            assert response.status_code == 200 and "<title>Lex</title>" in response.text, path
        assert c.get("/app.js").text == "// built"
        missing = c.get("/nada")  # the page, which says it is not found, with a 404
        assert missing.status_code == 404 and "<title>Lex</title>" in missing.text
        assert c.get("/api/health").json()["status"] == "ok"
        api_missing = c.get("/api/articles/lei-7-2009/999999")  # the API's errors stay JSON
        assert api_missing.status_code == 404 and "detail" in api_missing.json()


class Priced(Echo):
    """Answers as the demo's model would, its calls and tokens reported; fails on "falha"."""

    name = "dense+gemini-3.1-flash-lite+agent"

    def answer(self, question: str, as_of: dt.date) -> Answer:
        if "falha" in question:
            raise Status(429, "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        tokens = {
            "calls": 1,
            "prompt_tokens": 2000,
            "completion_tokens": 200,
            "thinking_tokens": 100,
        }
        return super().answer(question, as_of).model_copy(update={"tokens": tokens})


def test_usage_counts_each_outcome_with_latency_tokens_and_cost(
    capsys: pytest.CaptureFixture[str],
) -> None:
    api = client(Priced(), limits=Limits(per_visitor_per_hour=2))  # a failure is refunded
    api.post("/api/answer", json={"question": "Quantos dias de férias?"})
    api.post("/api/answer", json={"question": "Quantos dias de férias?"})  # from the cache
    api.post("/api/answer", json={"question": "Isto falha?"})
    api.post("/api/answer", json={"question": "Outra pergunta?"})
    assert api.post("/api/answer", json={"question": "Mais uma?"}).status_code == 429

    usage = api.get("/api/usage").json()

    assert usage["counts"] == {"answered": 2, "cached": 1, "failed_quota_day": 1, "limited": 1}
    assert usage["latency_seconds"]["answers"] == 2 and usage["latency_seconds"]["p95"] >= 0
    assert usage["tokens"] == {
        "calls": 2,
        "prompt_tokens": 4000,
        "completion_tokens": 400,
        "thinking_tokens": 200,
    }
    assert usage["usd_at_paid_prices"] == round((4000 * 0.25 + 600 * 1.50) / 1e6, 6)
    assert usage["scope"].startswith("this instance")
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if "event" in line]
    assert [line["outcome"] for line in lines][:2] == ["answered", "cached"]
    assert lines[0]["usd"] == round((2000 * 0.25 + 300 * 1.50) / 1e6, 6)


def test_changes_are_grouped_by_the_law_and_day_that_made_them() -> None:
    asked: list[tuple[str, dt.date, dt.date]] = []

    def changes(diploma: str, since: dt.date, until: dt.date) -> list[tuple[Found, str]]:
        asked.append((diploma, since, until))
        law = "lei-13-2019"
        day = dt.date(2019, 2, 13)
        return [
            (Found("dl-47344-1966", "1041", "Mora do locatário", "", law, day), "changed"),
            (Found("dl-47344-1966", "1067-A", "Igualdade", "", law, day), "added"),
        ]

    api = TestClient(create_app(Echo(), changes=changes, today=lambda: TODAY))
    view = api.get(
        "/api/changes", params={"diploma": "dl-47344-1966", "since": "2019-01-01"}
    ).json()

    assert asked == [("dl-47344-1966", dt.date(2019, 1, 1), TODAY)]  # until today by default
    assert view["groups"] == [
        {
            "introduced_by": "lei-13-2019",
            "valid_from": "2019-02-13",
            "articles": [
                {"article": "1041", "heading": "Mora do locatário", "kind": "changed"},
                {"article": "1067-A", "heading": "Igualdade", "kind": "added"},
            ],
        }
    ]
    bad = api.get(
        "/api/changes", params={"diploma": "x", "since": "2020-01-01", "until": "2019-01-01"}
    )
    assert bad.status_code == 422
