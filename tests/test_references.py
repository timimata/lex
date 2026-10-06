import csv
import datetime as dt
from pathlib import Path

import pytest

from lex.domain import DIPLOMAS, Citation
from lex.retrieval.references import Reference, WithReferences, find_references
from lex.store.memory import Corpus
from lex.store.models import ArticleVersion

PHRASINGS = list(
    csv.DictReader(
        (Path(__file__).parent / "fixtures" / "references.tsv").open(encoding="utf-8"),
        delimiter="\t",
    )
)


SHORT = {d.short: diploma for diploma, d in DIPLOMAS.items()}


def reference(token: str) -> Reference:
    """'CT:244' is article 244.º of the Código do Trabalho; '244', a bare number."""
    short, _, article = token.rpartition(":")
    return Reference(article, SHORT[short] if short else None)


@pytest.mark.parametrize("row", PHRASINGS, ids=[r["question"][:40] for r in PHRASINGS])
def test_article_references_are_found_in_real_phrasings(row: dict[str, str]) -> None:
    # An empty cell: no references.
    expected = [reference(t) for t in (row["expected"] or "").split(",") if t]
    assert find_references(row["question"]) == expected


def cite(article: str) -> Citation:
    return Citation(diploma="lei-7-2009", article=article)


class Fixed:
    name = "fixed"

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        return [cite("237"), cite("238"), cite("239")][:k]


def version(article: str, start: dt.date, diploma: str = "lei-7-2009") -> ArticleVersion:
    return ArticleVersion(
        diploma=diploma,
        article=article,
        heading="Epígrafe",
        path=[],
        text="Texto.",
        valid_from=start,
        valid_to=None,
        introduced_by=diploma,
        source_url="https://example.org",
        fetched=dt.date(2026, 9, 30),
    )


def test_named_articles_come_first_only_if_in_force() -> None:
    corpus = Corpus([version("238", dt.date(2009, 2, 17)), version("252-B", dt.date(2025, 4, 26))])
    retriever = WithReferences(Fixed(), corpus.article_at)
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


def test_a_bare_number_goes_to_the_diploma_the_question_speaks_of() -> None:
    nrau, cc = "lei-6-2006", "dl-47344-1966"
    corpus = Corpus(
        [
            version("9", dt.date(2009, 2, 17)),
            version("9", dt.date(2006, 6, 27), nrau),
            version("1083", dt.date(2006, 6, 27), cc),
        ]
    )
    retriever = WithReferences(Fixed(), corpus.article_at)
    today = dt.date(2026, 9, 30)

    assert retriever.search("O que diz o artigo 9.º?", today, 1) == [cite("9")]
    assert retriever.search("O artigo 9.º aplica-se às cartas ao senhorio?", today, 1) == [
        Citation(diploma=nrau, article="9")
    ]
    assert retriever.search("E o artigo 9.º do NRAU?", today, 1) == [
        Citation(diploma=nrau, article="9")
    ]
    # Only the Código Civil holds 1083.º, whatever the question speaks of.
    assert retriever.search("O que diz o artigo 1083.º?", today, 1) == [
        Citation(diploma=cc, article="1083")
    ]
