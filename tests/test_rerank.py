import datetime as dt

import psycopg

from lex.domain import Citation
from lex.retrieval.rerank import Reranked
from lex.store import db
from lex.store.models import ArticleVersion

TODAY = dt.date(2026, 9, 30)


def cite(article: str) -> Citation:
    return Citation(diploma="lei-7-2009", article=article)


class Fixed:
    name = "fixed"

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        return [cite("237"), cite("238"), cite("251")][:k]


class Overlap:
    """Scores a document by how many of the question's words it contains."""

    name = "overlap"

    def __init__(self) -> None:
        self.seen: list[str] = []

    def score(self, question: str, documents: list[str]) -> list[float]:
        self.seen += documents
        words = set(question.lower().split())
        return [float(len(words & set(d.lower().split()))) for d in documents]


def version(article: str, heading: str, text: str) -> ArticleVersion:
    return ArticleVersion(
        diploma="lei-7-2009",
        article=article,
        heading=heading,
        path=[],
        text=text,
        valid_from=dt.date(2009, 2, 17),
        valid_to=None,
        introduced_by="lei-7-2009",
        source_url="https://example.org",
        fetched=TODAY,
    )


def test_candidates_are_reordered_by_the_scorer_reading_each_article(
    conn: psycopg.Connection,
) -> None:
    db.load(
        conn,
        [
            version("237", "Direito a férias", "O trabalhador tem direito a férias."),
            version("238", "Duração do período de férias", "Mínimo de 22 dias úteis."),
            version("251", "Faltas por falecimento", "Faltar por falecimento de filho."),
        ],
    )
    scorer = Overlap()
    reranked = Reranked(Fixed(), scorer, conn)

    assert reranked.name == "fixed+rerank"
    # 251 shares four words with the question, 238 shares "de", 237 shares none.
    assert reranked.search("faltar por falecimento de filho", TODAY, 2) == [
        cite("251"),
        cite("238"),
    ]
    assert "Faltas por falecimento\nFaltar por falecimento de filho." in scorer.seen
