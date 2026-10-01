"""The Postgres store (ADR 0006): schema, loading, and reading an article as of a date."""

import datetime as dt
import os
from collections.abc import Iterable

import psycopg

from lex.store.models import ArticleVersion

# 127.0.0.1, not localhost: on Windows, localhost tries IPv6 first, and a connection to Docker's
# port that way took 130 s to fall back, against 0.24 s on 127.0.0.1.
DEFAULT_URL = "postgresql://lex:lex@127.0.0.1:5432/lex"

# Database-wide, so created before any schema-specific table (tests use throwaway schemas).
# vector before pg_search, which requires it: the ParadeDB image's bootstrap hid this, a fresh
# Postgres (the demo's, ADR 0013) does not.
EXTENSIONS = """
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS article_versions (
    id            bigserial PRIMARY KEY,
    diploma       text   NOT NULL,
    article       text   NOT NULL,
    heading       text   NOT NULL,
    path          text[] NOT NULL,
    text          text   NOT NULL,
    valid_from    date   NOT NULL,
    valid_to      date,
    introduced_by text   NOT NULL,
    source_url    text   NOT NULL,
    fetched       date   NOT NULL,
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    -- ADR 0002: at most one version of an article is in force on any day.
    EXCLUDE USING gist (
        diploma WITH =, article WITH =, daterange(valid_from, valid_to) WITH &&
    )
);
-- BM25 over heading and text with the Portuguese stemmer (ADR 0006). Maintained on insert.
CREATE INDEX IF NOT EXISTS article_versions_bm25 ON article_versions USING bm25 (
    id,
    (heading::pdb.simple('stemmer=portuguese')),
    (text::pdb.simple('stemmer=portuguese'))
) WITH (key_field = 'id');
-- Dense embeddings per article version and model (ADR 0007). Not cleared by load(): a row is
-- recomputed only when the hash of the text it embedded changes.
CREATE TABLE IF NOT EXISTS article_embeddings (
    diploma     text   NOT NULL,
    article     text   NOT NULL,
    valid_from  date   NOT NULL,
    model       text   NOT NULL,
    text_sha256 text   NOT NULL,
    embedding   vector NOT NULL,
    PRIMARY KEY (diploma, article, valid_from, model)
);
"""

_COLUMNS = (
    "diploma, article, heading, path, text, valid_from, valid_to, introduced_by, source_url, "
    "fetched"
)


def connect(url: str | None = None, timeout: int = 10) -> psycopg.Connection:
    # With Docker stopped on Windows, a connection to the port hangs instead of being refused.
    url = url or os.environ.get("DATABASE_URL", DEFAULT_URL)
    return psycopg.connect(url, connect_timeout=timeout)


def create_extensions(conn: psycopg.Connection) -> None:
    conn.execute(EXTENSIONS)


def create_schema(conn: psycopg.Connection) -> None:
    create_extensions(conn)
    conn.execute(SCHEMA)


def load(conn: psycopg.Connection, versions: Iterable[ArticleVersion]) -> int:
    """Replace every stored version with `versions`, in one transaction. Returns the count."""
    rows = [
        (
            v.diploma,
            v.article,
            v.heading,
            v.path,
            v.text,
            v.valid_from,
            v.valid_to,
            v.introduced_by,
            v.source_url,
            v.fetched,
        )
        for v in versions
    ]
    with conn.transaction():
        conn.execute("TRUNCATE article_versions RESTART IDENTITY")
        with conn.cursor() as cur:
            cur.executemany(
                f"INSERT INTO article_versions ({_COLUMNS}) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )
    return len(rows)


def article_at(
    conn: psycopg.Connection, diploma: str, article: str, as_of: dt.date
) -> ArticleVersion | None:
    """The version of an article in force on `as_of`, or None if there was none that day."""
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM article_versions "
        "WHERE diploma = %s AND article = %s AND daterange(valid_from, valid_to) @> %s::date",
        (diploma, article, as_of),
    ).fetchone()
    if row is None:
        return None
    fields = [name.strip() for name in _COLUMNS.split(",")]
    return ArticleVersion(**dict(zip(fields, row, strict=True)))


def versions_of(conn: psycopg.Connection, diploma: str, article: str) -> list[ArticleVersion]:
    """Every version of an article, oldest first."""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM article_versions WHERE diploma = %s AND article = %s "
        "ORDER BY valid_from",
        (diploma, article),
    ).fetchall()
    fields = [name.strip() for name in _COLUMNS.split(",")]
    return [ArticleVersion(**dict(zip(fields, row, strict=True))) for row in rows]


def export_embeddings(conn: psycopg.Connection) -> list[dict[str, str]]:
    """Every stored embedding, the vector in pgvector's own text form, so an import restores it
    exactly."""
    rows = conn.execute(
        "SELECT diploma, article, valid_from::text, model, text_sha256, embedding::text "
        "FROM article_embeddings ORDER BY diploma, article, valid_from, model"
    ).fetchall()
    keys = ["diploma", "article", "valid_from", "model", "text_sha256", "embedding"]
    return [dict(zip(keys, row, strict=True)) for row in rows]


def import_embeddings(conn: psycopg.Connection, rows: Iterable[dict[str, str]]) -> int:
    """Insert or replace embeddings exported by export_embeddings. Returns the count."""
    values = [
        (r["diploma"], r["article"], r["valid_from"], r["model"], r["text_sha256"], r["embedding"])
        for r in rows
    ]
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO article_embeddings
                (diploma, article, valid_from, model, text_sha256, embedding)
            VALUES (%s, %s, %s::date, %s, %s, %s::vector)
            ON CONFLICT (diploma, article, valid_from, model)
            DO UPDATE SET text_sha256 = EXCLUDED.text_sha256, embedding = EXCLUDED.embedding
            """,
            values,
        )
    return len(values)


def fingerprint(conn: psycopg.Connection) -> str:
    """A hash of every article version's identity, dates and text: it changes whenever the
    store's contents do."""
    row = conn.execute(
        "SELECT md5(coalesce(string_agg(concat_ws('|', diploma, article, valid_from, valid_to, "
        "md5(heading || text)), ',' ORDER BY diploma, article, valid_from), '')) "
        "FROM article_versions"
    ).fetchone()
    assert row is not None
    return str(row[0])
