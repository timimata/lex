import csv
import datetime as dt
from pathlib import Path

import psycopg
import pytest

from lex.domain import Citation
from lex.retrieval.references import WithReferences, find_references
from lex.store import db
from lex.store.models import ArticleVersion

PHRASINGS = list(
    csv.DictReader(
        (Path(__file__).parent / "fixtures" / "references.tsv").open(encoding="utf-8"),
        delimiter="\t",
    )
)


@pytest.mark.parametrize("row", PHRASINGS, ids=[r["question"][:40] for r in PHRASINGS])
def test_article_references_are_found_in_real_phrasings(row: dict[str, str]) -> None:
    expected = [a for a in (row["expected"] or "").split(",") if a]  # empty cell: no references
    assert find_references(row["question"]) == expected


def cite(article: str) -> Citation:
    return Citation(diploma="lei-7-2009", article=article)


class Fixed:
    name = "fixed"

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        return [cite("237"), cite("238"), cite("239")][:k]


def version(article: str, start: dt.date) -> ArticleVersion:
    return ArticleVersion(
        diploma="lei-7-2009",
        article=article,
        heading="Epígrafe",
        path=[],
        text="Texto.",
        valid_from=start,
        valid_to=None,
        introduced_by="lei-7-2009",
        source_url="https://example.org",
        fetched=dt.date(2026, 9, 30),
    )


def test_named_articles_come_first_only_if_in_force(conn: psycopg.Connection) -> None:
    db.load(conn, [version("238", dt.date(2009, 2, 17)), version("252-B", dt.date(2025, 4, 26))])
    retriever = WithReferences(Fixed(), lambda d, a, day: db.article_at(conn, d, a, day))
    today, before = dt.date(2026, 9, 30), dt.date(2024, 1, 1)

    assert retriever.name == "fixed+refs"
    assert retriever.search("O que diz o artigo 238.º?", today, 3) == [
        cite("238"),
        cite("237"),
        cite("239"),
    ]
    assert retriever.search("E o artigo 252.º-B?", today, 2) == [cite("252-B"), cite("237")]
    # 252.º-B did not exist yet, so the base ranking stands.
    assert retriever.search("E o artigo 252.º-B?", before, 2) == [cite("237"), cite("238")]
