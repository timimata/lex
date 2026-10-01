"""Types shared by the benchmark, the eval harness and every system under test.

Anything that answers questions is a `System`: the full reference system, or an external tool
whose answers were typed in by hand. Anything that ranks articles for a question is a
`Retriever`: a BM25 baseline, a dense one, the hybrid. The eval harness sees nothing else.
"""

import datetime as dt
from typing import Protocol

from pydantic import BaseModel, Field

# Type, number and year, lowercase: lei-7-2009, dl-157-2006, portaria-112-2024.
DIPLOMA_PATTERN = r"^[a-z]+(-[a-z]+)*-\d+-\d{4}$"
# The article number as the DR prints it, without ".º": 238, 238-A.
ARTICLE_PATTERN = r"^\d+(-[A-Z]+)?$"


class Citation(BaseModel, frozen=True):
    """One article of one diploma. Número and alínea are not scored."""

    diploma: str = Field(pattern=DIPLOMA_PATTERN)
    article: str = Field(pattern=ARTICLE_PATTERN)


class Answer(BaseModel):
    text: str
    citations: list[Citation] = []
    refused: bool = False
    # Seconds spent per stage ("retrieval", "generation"), where a system measures them.
    timings: dict[str, float] = Field(default_factory=dict)


class System(Protocol):
    name: str

    def answer(self, question: str, as_of: dt.date) -> Answer: ...


class Retriever(Protocol):
    name: str

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        """The k articles most relevant to the question, best first, among those in force on
        `as_of`."""
        ...
