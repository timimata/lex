"""Types shared by the benchmark, the eval harness and every system under test.

Anything that answers questions is a `System`: the full reference system, or an external tool
whose answers were typed in by hand. Anything that ranks articles for a question is a
`Retriever`: a BM25 baseline, a dense one, the hybrid. The eval harness sees nothing else.
"""

import datetime as dt
import hashlib
from collections.abc import Iterable
from typing import NamedTuple, Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

# On every surface that shows the law (CLAUDE.md): the API, the page, the MCP server.
DISCLAIMER = (
    "Os textos consolidados não têm valor legal: só faz fé a publicação no Diário da República. "
    "O Lex não é aconselhamento jurídico."
)
# "Today" is Lisbon's date: the law asked about is Portuguese, and a server's clock may be on UTC.
LISBON = ZoneInfo("Europe/Lisbon")


def lisbon_today(now: dt.datetime | None = None) -> dt.date:
    """The date in Lisbon at `now` (a timezone-aware instant, the current one by default)."""
    return (now or dt.datetime.now(dt.UTC)).astimezone(LISBON).date()


# Type, number (with its letter, if any) and year, lowercase: lei-7-2009, dl-321-b-1990.
DIPLOMA_PATTERN = r"^[a-z]+(-[a-z]+)*-\d+(-[a-z]{1,2})?-\d{4}$"
# The article number as the DR prints it, without ".º": 238, 238-A.
ARTICLE_PATTERN = r"^\d+(-[A-Z]+)?$"


def text_sha(heading: str, text: str, notes: Iterable[str] = ()) -> str:
    """The sha256 of an article version's heading, text and notes, as corpus/index.jsonl keeps
    it; a version with no notes hashes as before notes were kept."""
    noted = "".join(f"\n{note}" for note in notes)
    return hashlib.sha256(f"{heading}\n{text}{noted}".encode()).hexdigest()


def corpus_fingerprint(rows: Iterable[tuple[str, str, str, str | None, str]]) -> str:
    """One hash of a corpus, whichever holds it (Postgres, memory, the committed index): each
    version's diploma, article, dates and `text_sha`, in sorted order. A changed heading changes
    it, as it changes what an embedding reads."""
    lines = sorted("|".join([d, a, start, end or "", sha]) for d, a, start, end, sha in rows)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


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


class Version(Citation, frozen=True):
    """One version of an article: the article, and the day that version came into force."""

    valid_from: dt.date


class Answer(BaseModel):
    text: str
    citations: list[Citation] = []
    refused: bool = False
    # The article versions the system's model read before answering, its searches and reads
    # included: what tells an article retrieval missed from one the answer left out. Empty for
    # a system that does not say (one scored from outside).
    given: list[Version] = Field(default_factory=list)
    # The version of each cited article, where a system scored from outside says it (lex.eval.
    # outside); the reference systems' citations are among `given`, which says it already.
    cited_versions: list[Version] = Field(default_factory=list)
    # Why the model refused, in its words: no citation backs it, so it is never shown as part of
    # the answer, and the API drops it (lex.api.app); runs keep it for reading.
    reason: str = ""
    # Seconds spent per stage ("retrieval", "generation"), where a system measures them.
    timings: dict[str, float] = Field(default_factory=dict)
    # What the system asked for before answering, in order, with what each request added: the
    # agent's searches and reads (Phase 7). Empty for a system that does not ask.
    requests: list[str] = Field(default_factory=list)
    # What the answer cost the model in calls and tokens (lex.generation.llm.spent), where known.
    tokens: dict[str, int] = Field(default_factory=dict)


class System(Protocol):
    name: str

    def answer(self, question: str, as_of: dt.date) -> Answer: ...


class Retriever(Protocol):
    name: str

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        """The k articles most relevant to the question, best first, among those in force on
        `as_of`."""
        ...
