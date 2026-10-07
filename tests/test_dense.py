import datetime as dt
import math

import psycopg

from lex.domain import Citation
from lex.retrieval.dense import Dense, embed_missing
from lex.store import db
from lex.store.models import ArticleVersion

TODAY = dt.date(2026, 9, 29)
WORDS = ("férias", "falta", "salário")


class Toy:
    """Counts three words, normalised: enough to test storage, dates and ranking without a
    real model."""

    name = "toy@1"
    query_format = "{}"
    document_format = "{heading}\n{text}"

    def __init__(self) -> None:
        self.calls = 0

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.calls += len(texts)
        vectors = []
        for text in texts:
            counts = [text.lower().count(w) + 0.01 for w in WORDS]
            norm = math.sqrt(sum(c * c for c in counts))
            vectors.append([c / norm for c in counts])
        return vectors


def version(article: str, text: str, start: dt.date, end: dt.date | None) -> ArticleVersion:
    return ArticleVersion(
        diploma="lei-7-2009",
        article=article,
        heading="Epígrafe",
        path=[],
        text=text,
        valid_from=start,
        valid_to=end,
        introduced_by="lei-7-2009",
        source_url="https://example.org",
        fetched=TODAY,
    )


START = dt.date(2009, 2, 17)
LAW = [
    version("238", "férias férias férias", START, None),
    version("251", "falta por falecimento, falta justificada", START, None),
    version("258", "salário", START, dt.date(2012, 8, 1)),
]


def test_embeddings_are_computed_once_and_redone_when_a_text_changes(
    conn: psycopg.Connection,
) -> None:
    toy = Toy()
    db.load(conn, LAW)
    assert embed_missing(conn, toy) == 3
    assert embed_missing(conn, toy) == 0  # nothing changed

    db.load(conn, [*LAW[:2], version("258", "salário e férias", START, dt.date(2012, 8, 1))])
    assert embed_missing(conn, toy) == 1
    assert toy.calls == 4


def test_embeddings_are_kept_on_a_connection_that_does_not_autocommit(
    conn: psycopg.Connection,
) -> None:
    db.load(conn, LAW)
    conn.autocommit = False  # as the eval's and the API's connections are
    assert embed_missing(conn, Toy()) == 3
    conn.rollback()  # what closing the connection without a commit does
    assert embed_missing(conn, Toy()) == 0


def test_dense_ranks_by_similarity_among_the_law_in_force(conn: psycopg.Connection) -> None:
    toy = Toy()
    db.load(conn, LAW)
    embed_missing(conn, toy)
    dense = Dense(conn, toy)

    def cite(article: str) -> Citation:
        return Citation(diploma="lei-7-2009", article=article)

    assert dense.search("quantos dias de férias?", TODAY, 1) == [cite("238")]
    assert dense.search("uma falta", TODAY, 1) == [cite("251")]
    assert cite("258") in dense.search("salário", dt.date(2011, 1, 1), 3)
    assert cite("258") not in dense.search("salário", TODAY, 3)  # no longer in force
