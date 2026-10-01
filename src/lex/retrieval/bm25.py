"""The lexical baseline: BM25 over article headings and texts, with the Portuguese stemmer, among
the versions in force on the date asked about (ADR 0006)."""

import datetime as dt

import psycopg

from lex.domain import Citation


class Bm25:
    name = "bm25"

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        # ||| tokenises the question with each field's tokenizer and matches any of its terms,
        # so punctuation and article numbers in the question need no escaping.
        rows = self.conn.execute(
            """
            SELECT diploma, article FROM article_versions
            WHERE (heading ||| %(q)s OR text ||| %(q)s)
              AND daterange(valid_from, valid_to) @> %(as_of)s::date
            ORDER BY pdb.score(id) DESC, article
            LIMIT %(k)s
            """,
            {"q": question, "as_of": as_of, "k": k},
        ).fetchall()
        return [Citation(diploma=diploma, article=article) for diploma, article in rows]
