"""A benchmark item: a question, the date it is asked about, and what a correct answer cites.

Field meanings and writing rules are in bench/README.md.
"""

import datetime as dt
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from lex.domain import Citation

QuestionType = Literal["simple", "composite", "temporal", "explicit_reference", "unanswerable"]


class Source(BaseModel):
    """The public page an item was taken from."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    title: str = Field(min_length=1)
    retrieved: dt.date


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z]+-\d{4}$")
    question: str = Field(min_length=10)
    as_of: dt.date
    type: QuestionType
    must_cite: list[Citation] = []
    may_cite: list[Citation] = []
    answer: str = Field(min_length=1)
    source: Source
    # Who checked the item against its source and the law in force on as_of before it entered
    # the benchmark: a person's name, or the model that did it (e.g. "claude-opus-5.5").
    reviewed_by: str = Field(min_length=1)
    status: Literal["draft", "validated"] = "draft"
    validated_by: str | None = None
    notes: str = ""

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.type == "unanswerable":
            if self.must_cite or self.may_cite:
                raise ValueError("an unanswerable item cites nothing")
        elif not self.must_cite:
            raise ValueError("an answerable item needs at least one must_cite")
        if set(self.must_cite) & set(self.may_cite):
            raise ValueError("a citation is must_cite or may_cite, not both")
        if self.status == "validated" and not self.validated_by:
            raise ValueError("a validated item names who validated it")
        # bench/README.md: a temporal item asks about an earlier date; any other is about the
        # day it was written, which is the day its source was read.
        if self.type == "temporal" and not self.as_of < self.source.retrieved:
            raise ValueError("a temporal item's as_of must be before its source was read")
        if self.type != "temporal" and self.as_of != self.source.retrieved:
            raise ValueError("a non-temporal item's as_of is the day its source was read")
        return self
