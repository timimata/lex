"""What the store holds. See docs/decisions/0002-article-versions.md."""

import datetime as dt
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from lex.domain import ARTICLE_PATTERN, DIPLOMA_PATTERN


class ArticleVersion(BaseModel):
    """One article's text over one stretch of time: [valid_from, valid_to)."""

    model_config = ConfigDict(extra="forbid")

    diploma: str = Field(pattern=DIPLOMA_PATTERN)
    article: str = Field(pattern=ARTICLE_PATTERN)
    heading: str
    path: list[str]  # place in the code, outermost first: "Livro I - Parte geral", ...
    text: str
    valid_from: dt.date
    valid_to: dt.date | None = None  # None while in force
    introduced_by: str = Field(pattern=DIPLOMA_PATTERN)
    source_url: str
    fetched: dt.date
    # What the DR notes on the version beside its text: another diploma deferring, suspending or
    # starting its effects, or a Constitutional Court ruling on it, verbatim (ROADMAP, Phase 11).
    notes: list[str] = []

    def in_force_on(self, day: dt.date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day < self.valid_to)


# The version of an article in force on a date, or None: what lex.store.db.article_at and
# lex.store.memory.Corpus.article_at both answer, for code that works with either store.
ArticleAt = Callable[[str, str, dt.date], ArticleVersion | None]
