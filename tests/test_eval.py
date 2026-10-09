import datetime as dt
import json
from pathlib import Path
from typing import Any

import psycopg
import pytest

from lex.bench.schema import Item
from lex.domain import Answer, Citation, Version
from lex.eval import results
from lex.eval.__main__ import cost
from lex.eval.harness import run_answers, run_retrieval, summarise, summarise_answers
from lex.eval.metrics import citation_precision, citation_recall, recall_at_k
from lex.generation import llm
from lex.retrieval.bm25 import Bm25
from lex.store import db
from lex.store.models import ArticleVersion

TODAY = dt.date(2026, 9, 29)


def cite(article: str) -> Citation:
    return Citation(diploma="lei-7-2009", article=article)


def item(item_id: str, type_: str, must: list[str], may: list[str] | None = None) -> Item:
    return Item.model_validate(
        {
            "id": item_id,
            "question": f"Pergunta de teste {item_id}",
            "as_of": TODAY.isoformat(),
            "type": type_,
            "must_cite": [cite(a).model_dump() for a in must],
            "may_cite": [cite(a).model_dump() for a in may or []],
            "answer": "Resposta.",
            "source": {"url": "https://example.org", "title": "Fonte", "retrieved": "2026-09-29"},
            "reviewed_by": "test",
        }
    )


def test_recall_counts_expected_articles_in_the_first_k() -> None:
    ranked = [cite("1"), cite("2"), cite("3")]
    assert recall_at_k([cite("2")], ranked, 1) == 0
    assert recall_at_k([cite("2")], ranked, 2) == 1
    assert recall_at_k([cite("2"), cite("9")], ranked, 3) == 0.5
    with pytest.raises(ValueError):
        recall_at_k([], ranked, 3)


class Fixed:
    """A retriever that returns the same ranking for every question."""

    name = "fixed"

    def __init__(self, ranking: list[str]) -> None:
        self.ranking = [cite(a) for a in ranking]

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        return self.ranking[:k]


def test_the_harness_scores_answerable_items_and_groups_by_type() -> None:
    items = [
        item("ct-0001", "simple", ["2"]),
        item("ct-0002", "composite", ["2", "9"]),
        item("ct-0003", "unanswerable", []),
    ]
    scored = run_retrieval(items, Fixed(["1", "2", "3"]), ks=(1, 3))

    assert [r.id for r in scored] == ["ct-0001", "ct-0002"]  # unanswerable is not retrieval
    summary = summarise(scored)
    assert list(summary) == ["all", "composite", "simple"]
    assert summary["all"] == {"items": 2, "recall@1": 0.0, "recall@3": 0.75}
    assert summary["composite"]["recall@3"] == 0.5


def test_citation_metrics_follow_the_bench_readme() -> None:
    must, may = [cite("2"), cite("9")], [cite("5")]
    assert citation_precision([cite("2"), cite("5"), cite("7")], must, may) == 2 / 3
    assert citation_precision([], must, may) is None
    assert citation_recall([cite("2"), cite("7")], must) == 0.5
    with pytest.raises(ValueError):
        citation_recall([cite("2")], [])


class Scripted:
    """A system that gives a set answer per question."""

    name = "scripted"

    def __init__(self, answers: dict[str, Answer]) -> None:
        self.answers = answers

    def answer(self, question: str, as_of: dt.date) -> Answer:
        return self.answers[question]


def test_answers_are_scored_on_citations_and_refusals_by_type() -> None:
    items = [
        item("ct-0001", "simple", ["2"]),
        item("ct-0002", "composite", ["2", "9"], may=["5"]),
        item("ct-0003", "simple", ["4"]),
        item("ct-0004", "unanswerable", []),
    ]
    q = {i.id: i.question for i in items}
    system = Scripted(
        {
            q["ct-0001"]: Answer(text="a", citations=[cite("2")]),
            q["ct-0002"]: Answer(text="b", citations=[cite("2"), cite("5"), cite("7")]),
            # A refusal's citations are not claims: it counts as citing nothing.
            q["ct-0003"]: Answer(text="c", citations=[cite("4")], refused=True),
            q["ct-0004"]: Answer(text="d", citations=[cite("1")], refused=True),
        }
    )

    scored = run_answers(items, system)

    assert [(r.precision, r.recall, r.refused) for r in scored] == [
        (1.0, 1.0, False),
        (2 / 3, 0.5, False),
        (None, 0.0, True),
        (None, None, True),
    ]
    assert scored[1].cited == ["lei-7-2009/2", "lei-7-2009/5", "lei-7-2009/7"]
    assert scored[1].allowed == ["lei-7-2009/5"]
    summary = summarise_answers(scored)
    assert list(summary) == ["answerable", "composite", "simple", "unanswerable"]
    assert summary["answerable"] == {
        "items": 3,
        "refused": 1 / 3,
        "cited": 2,
        "citation_precision": (1.0 + 2 / 3) / 2,
        "citation_recall": 0.5,
    }
    assert summary["unanswerable"] == {
        "items": 1,
        "refused": 1.0,
        "cited": 0,
        "citation_precision": None,
        "citation_recall": None,
    }


def test_a_test_run_refuses_uncommitted_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(results, "git_state", lambda: ("abc123", True))
    (tmp_path / "dev.jsonl").write_text('{"id": "ct-0001"}\n{"id": "ct-0002"}\n', encoding="utf-8")
    with pytest.raises(RuntimeError):
        results.write("test", "fixed", {}, {}, [], results_dir=tmp_path, data_dir=tmp_path)
    dev = results.write("dev", "fixed", {}, {}, [], results_dir=tmp_path, data_dir=tmp_path)
    assert dev == tmp_path / "dev" / "fixed.json"
    # The run says which questions it ran on: how many, and a hash of the file, not its content.
    bench = json.loads(dev.read_text(encoding="utf-8"))["bench"]
    assert bench["items"] == 2 and len(bench["sha"]) == 12


def test_a_test_run_reaches_a_free_tier_only_while_that_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    google = "https://generativelanguage.googleapis.com/v1beta/openai/"
    monkeypatch.delenv("LLM_KEY_TIER", raising=False)
    free, local = llm.endpoint(google), llm.endpoint("http://127.0.0.1:8080/v1")
    assert free == {"url": google, "tier": "free"} and local["tier"] == "local"
    results.ensure_private("test", {"answers": local, "judge": free})  # accepted since 10-09
    monkeypatch.setattr(results, "FREE_TIER_ON_TEST", False)
    with pytest.raises(SystemExit, match="judge"):
        results.ensure_private("test", {"answers": local, "judge": free}, False)
    results.ensure_private("dev", {"judge": free}, False)  # dev is public already
    monkeypatch.setenv("LLM_KEY_TIER", "paid")
    results.ensure_private("test", {"answers": local, "judge": llm.endpoint(google)}, False)
    # Gemma has no paid tier on Google's API: a paid key leaves its requests on unpaid terms.
    gemma = llm.endpoint(google, "gemma-4-26b-a4b-it")
    assert (
        gemma["tier"] == "free" and llm.endpoint(google, "gemini-3.1-flash-lite")["tier"] == "paid"
    )
    with pytest.raises(SystemExit, match="judge"):
        results.ensure_private("test", {"answers": llm.endpoint(google), "judge": gemma}, False)


def version(article: str, text: str, start: dt.date, end: dt.date | None) -> ArticleVersion:
    fields: dict[str, Any] = {
        "diploma": "lei-7-2009",
        "article": article,
        "heading": "Epígrafe",
        "path": [],
        "text": text,
        "valid_from": start,
        "valid_to": end,
        "introduced_by": "lei-7-2009",
        "source_url": "https://example.org",
        "fetched": TODAY,
    }
    return ArticleVersion(**fields)


def test_bm25_stems_portuguese_and_searches_only_the_law_in_force(
    conn: psycopg.Connection,
) -> None:
    db.load(
        conn,
        [
            version(
                "367",
                "Noção de despedimento por extinção de posto de trabalho.",
                dt.date(2009, 2, 17),
                None,
            ),
            version(
                "238",
                "O período anual de férias tem 22 dias úteis, com majoração.",
                dt.date(2009, 2, 17),
                dt.date(2012, 8, 1),
            ),
            version(
                "238",
                "O período anual de férias tem a duração mínima de 22 dias úteis.",
                dt.date(2012, 8, 1),
                None,
            ),
            version("252-B", "Falta por endometriose.", dt.date(2025, 4, 26), None),
        ],
    )
    bm25 = Bm25(conn)

    assert bm25.search("Quais são os despedimentos?", TODAY, 5) == [cite("367")]
    assert bm25.search("majoração das férias", dt.date(2011, 1, 1), 5) == [cite("238")]
    assert bm25.search("endometriose", dt.date(2024, 1, 1), 5) == []  # not yet in the code


def test_percentiles_are_nearest_rank() -> None:
    from lex.eval.__main__ import percentile

    values = [float(v) for v in range(1, 11)]
    assert (percentile(values, 0.5), percentile(values, 0.95)) == (5.0, 10.0)
    assert percentile([3.0], 0.95) == 3.0


def test_cost_is_at_the_paid_prices_with_thinking_as_output() -> None:
    usage = {
        "prompt_tokens": 2_000_000,
        "completion_tokens": 100_000,
        "thinking_tokens": 300_000,
        "thinking_unrecorded": 0,
    }
    found = cost(usage, "gemini-3.1-flash-lite", 4)
    assert found is not None
    assert found["usd"] == 2 * 0.25 + 0.4 * 1.50  # 1.1
    assert found["usd_per_question"] == 0.275 and not found["lower_bound"]
    partial = cost({**usage, "thinking_unrecorded": 1}, "gemini-3.1-flash-lite", 4)
    assert partial is not None and partial["lower_bound"]
    assert cost(usage, "a-local-model", 4) is None


def test_a_changed_prompt_is_caught_until_dev_is_run_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from lex.eval import __main__ as cli
    from lex.generation.agent import AGENT_SYSTEM
    from lex.retrieval.dense import GEMINI_QUERY

    monkeypatch.setattr(results, "RESULTS", tmp_path)
    run = tmp_path / "dev" / "dense-gemini-embedding-2+refs+gemini-3.1-flash-lite+agent.json"
    run.parent.mkdir()
    config = {"prompts": cli.fingerprint("agent"), "query": GEMINI_QUERY}
    run.write_text(json.dumps({"config": config}), encoding="utf-8")
    assert cli.prompt_guard() == []

    monkeypatch.setattr(cli, "AGENT_SYSTEM", AGENT_SYSTEM + " Sê breve.")
    assert "prompts changed" in cli.prompt_guard()[0]
    assert cli.fingerprint("claims") != cli.fingerprint("agent")


def test_recall_lost_is_split_between_retrieval_and_the_answer() -> None:
    def read(*articles: str) -> list[Version]:
        return [Version(diploma="lei-7-2009", article=a, valid_from=TODAY) for a in articles]

    items = [
        item("ct-0001", "composite", ["2", "9"]),  # 9 never reached the model
        item("ct-0002", "composite", ["2", "9"]),  # both given, the answer left 9 out
        item("ct-0003", "simple", ["4"]),  # answered with nothing it needed: unsupported
        item("ct-0004", "simple", ["4"]),  # a system that does not say what it read
    ]
    q = {i.id: i.question for i in items}
    system = Scripted(
        {
            q["ct-0001"]: Answer(text="a", citations=[cite("2")], given=read("2", "5")),
            q["ct-0002"]: Answer(text="b", citations=[cite("2")], given=read("2", "9")),
            q["ct-0003"]: Answer(text="c", citations=[cite("5")], given=read("5")),
            q["ct-0004"]: Answer(text="d", citations=[cite("4")]),
        }
    )

    scored = run_answers(items, system)

    assert [(r.recall, r.given_recall) for r in scored] == [
        (0.5, 0.5),
        (0.5, 1.0),
        (0.0, 0.0),
        (1.0, None),
    ]
    assert scored[1].given == ["lei-7-2009/2@2026-09-29", "lei-7-2009/9@2026-09-29"]
    summary = summarise_answers(scored)
    assert summary["answerable"]["given_recall"] == 0.5
    assert summary["answerable"]["unsupported"] == 1
    assert summary["composite"]["unsupported"] == 0


def test_a_cited_version_must_be_the_one_in_force_on_the_date() -> None:
    temporal = Item.model_validate(
        item("ct-0001", "simple", ["2"]).model_dump(mode="json")
        | {"type": "temporal", "as_of": "2011-06-01"}
    )
    periods: dict[tuple[str, str], list[tuple[str, str | None]]] = {
        ("lei-7-2009", "2"): [("2009-02-17", "2012-08-01"), ("2012-08-01", None)]
    }

    def answering(valid_from: str) -> Scripted:
        given = [Version(diploma="lei-7-2009", article="2", valid_from=valid_from)]
        return Scripted({temporal.question: Answer(text="a", citations=[cite("2")], given=given)})

    [then] = run_answers([temporal], answering("2009-02-17"), periods)
    [today] = run_answers([temporal], answering("2012-08-01"), periods)  # today's text
    [unchecked] = run_answers([temporal], answering("2012-08-01"))

    assert (then.version_right, today.version_right, unchecked.version_right) == (1.0, 0.0, None)
    assert summarise_answers([today])["temporal"]["version_right"] == 0.0


def test_a_test_run_is_refused_without_a_dev_run_of_the_same_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lex.eval import gates

    monkeypatch.setattr(results, "RESULTS", tmp_path)
    monkeypatch.setattr(results, "bench_version", lambda split: {"scored": "dev-today"})
    expected = {"model": "m", "prompts": "p1"}
    with pytest.raises(SystemExit, match="no dev run of sys"):
        gates.justifying_dev_run("sys", expected)

    (tmp_path / "dev").mkdir()
    run: dict[str, Any] = {
        "bench": {"scored": "dev-today"},
        "config": {"model": "m", "prompts": "p0"},  # its prompts were another's
        "commit": "abc",
        "run_at": "2026-10-08T10:00:00+01:00",
    }
    (tmp_path / "dev" / "sys.json").write_text(json.dumps(run), encoding="utf-8")
    with pytest.raises(SystemExit, match="another prompts"):
        gates.justifying_dev_run("sys", expected)

    run["config"]["prompts"] = "p1"
    run["bench"]["scored"] = "dev-v2"
    (tmp_path / "dev" / "sys.json").write_text(json.dumps(run), encoding="utf-8")
    with pytest.raises(SystemExit, match="another version of dev"):
        gates.justifying_dev_run("sys", expected)

    run["bench"]["scored"] = "dev-today"
    (tmp_path / "dev" / "sys.json").write_text(json.dumps(run), encoding="utf-8")
    assert gates.justifying_dev_run("sys", expected) == {
        "file": "sys.json",
        "commit": "abc",
        "run_at": "2026-10-08T10:00:00+01:00",
        "prompts": "p1",
    }
