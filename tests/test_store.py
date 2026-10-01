import datetime as dt

import psycopg
import pytest

from lex.store import db
from lex.store.models import ArticleVersion


def version(start: dt.date, end: dt.date | None, text: str, by: str) -> ArticleVersion:
    return ArticleVersion(
        diploma="lei-7-2009",
        article="238",
        heading="Duração do período de férias",
        path=["Livro I - Parte geral"],
        text=text,
        valid_from=start,
        valid_to=end,
        introduced_by=by,
        source_url="https://example.org",
        fetched=dt.date(2026, 9, 29),
    )


HISTORY = [
    version(dt.date(2009, 2, 17), dt.date(2012, 8, 1), "com majoração", "lei-7-2009"),
    version(dt.date(2012, 8, 1), None, "sem majoração", "lei-23-2012"),
]


def test_an_article_reads_as_it_was_on_the_day_asked(conn: psycopg.Connection) -> None:
    assert db.load(conn, HISTORY) == 2

    def text_on(day: dt.date) -> str | None:
        found = db.article_at(conn, "lei-7-2009", "238", day)
        return found.text if found else None

    assert text_on(dt.date(2009, 2, 16)) is None  # before the code
    assert text_on(dt.date(2011, 6, 1)) == "com majoração"
    assert text_on(dt.date(2012, 7, 31)) == "com majoração"
    assert text_on(dt.date(2012, 8, 1)) == "sem majoração"  # valid_to is exclusive
    assert text_on(dt.date(2026, 9, 29)) == "sem majoração"
    assert db.article_at(conn, "lei-7-2009", "238", dt.date(2011, 6, 1)) == HISTORY[0]


def test_overlapping_versions_are_refused_and_nothing_is_half_loaded(
    conn: psycopg.Connection,
) -> None:
    db.load(conn, HISTORY)
    overlapping = [*HISTORY, version(dt.date(2020, 1, 1), None, "outra", "lei-93-2019")]

    with pytest.raises(psycopg.errors.ExclusionViolation):
        db.load(conn, overlapping)

    count = conn.execute("SELECT count(*) FROM article_versions").fetchone()
    assert count == (2,)


def test_an_articles_versions_come_oldest_first(conn: psycopg.Connection) -> None:
    db.load(conn, list(reversed(HISTORY)))
    assert db.versions_of(conn, "lei-7-2009", "238") == HISTORY
    assert db.versions_of(conn, "lei-7-2009", "999") == []


def test_embeddings_survive_an_export_and_import_exactly(conn: psycopg.Connection) -> None:
    db.load(conn, HISTORY)
    conn.execute(
        "INSERT INTO article_embeddings VALUES "
        "('lei-7-2009', '238', '2009-02-17', 'm@1', 'abc', '[0.12345679,-1e-07,0.5]')"
    )
    exported = db.export_embeddings(conn)
    conn.execute("DELETE FROM article_embeddings")

    assert db.import_embeddings(conn, exported) == 1
    assert db.export_embeddings(conn) == exported
    assert exported[0]["valid_from"] == "2009-02-17"
