import datetime as dt
import json
from pathlib import Path
from typing import Any

import psycopg
import pytest

from lex.bench.schema import Item
from lex.domain import Answer, Citation
from lex.eval import results
from lex.eval.harness import run_answers, run_retrieval, summarise, summarise_answers
from lex.eval.metrics import citation_precision, citation_recall, recall_at_k
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
