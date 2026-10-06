"""Types shared by the benchmark, the eval harness and every system under test.

Anything that answers questions is a `System`: the full reference system, or an external tool
whose answers were typed in by hand. Anything that ranks articles for a question is a
`Retriever`: a BM25 baseline, a dense one, the hybrid. The eval harness sees nothing else.
"""

import datetime as dt
from typing import NamedTuple, Protocol

from pydantic import BaseModel, Field

# Type, number (with its letter, if any) and year, lowercase: lei-7-2009, dl-321-b-1990.
DIPLOMA_PATTERN = r"^[a-z]+(-[a-z]+)*-\d+(-[a-z]{1,2})?-\d{4}$"
# The article number as the DR prints it, without ".º": 238, 238-A.
ARTICLE_PATTERN = r"^\d+(-[A-Z]+)?$"


class Diploma(NamedTuple):
    short: str  # how a citation names it: "CT 238"
    name: str  # how a sentence names it: "Código do Trabalho, art. 238.º"


# The diplomas the corpus holds (ADRs 0003 and 0017). The Código Civil only in part: its
# articles 1022.º to 1113.º, on leases.
CT = "lei-7-2009"
CC = "dl-47344-1966"
NRAU = "lei-6-2006"
DIPLOMAS = {
    CT: Diploma("CT", "Código do Trabalho"),
    CC: Diploma("CC", "Código Civil"),
    NRAU: Diploma("NRAU", "NRAU"),
}


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
    # What the system asked for before answering, in order, with what each request added: the
    # agent's searches and reads (Phase 7). Empty for a system that does not ask.
    requests: list[str] = Field(default_factory=list)


class System(Protocol):
    name: str

    def answer(self, question: str, as_of: dt.date) -> Answer: ...


class Retriever(Protocol):
    name: str

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        """The k articles most relevant to the question, best first, among those in force on
        `as_of`."""
        ...
