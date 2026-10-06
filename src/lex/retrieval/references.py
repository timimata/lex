"""Explicit article references in a question, resolved before any search (ADR 0004).

"artigo 199.º-A", "art. 238.º CT", "o n.º 2 do artigo 1084.º do Código Civil", "artigos 344.º e
345.º": a question that names its article has one right target, and neither BM25 nor dense search
can find it, because article numbers are not in the article text. Each reference is read in the
diploma named right after it, if the corpus holds that one (ADR 0017); one that names another
diploma ("artigo 108.º da Lei n.º 102/2009") is left alone. A bare number belongs to no diploma
yet: whoever reads it decides, the retriever by the question's words, an answer by the articles
it was given.
"""

import datetime as dt
import re
from typing import NamedTuple

from lex.domain import CC, CT, NRAU, Citation, Retriever
from lex.store.models import ArticleAt

# "artigo", "artigos", "art.", "arts.", "art.º", then one or more numbers joined by "," "e" "a".
_NUMBER = r"\d+(?:\.º|º)?(?:\s*-\s*[A-Z]{1,2}\b)?"
_REFERENCE = re.compile(
    rf"\b(?:artigos?|arts?\.(?:º)?|art\.º)\s+(?P<numbers>{_NUMBER}(?:\s*(?:,|e|a)\s*{_NUMBER})*)",
    re.IGNORECASE,
)
# What may come between a reference and the diploma it names: "/2" or ", n.º 2," (a
# paragraph), "do", "da".
_BETWEEN = r"^(?:/\d+)?\s*(?:,\s*)?(?:n\.?º\s*\d+\s*,?\s*)?(?:d[oa]s?\s+)?"
_IN_CORPUS = (
    (CT, re.compile(rf"{_BETWEEN}(?:Código\s+do\s+Trabalho|CT)\b", re.IGNORECASE)),
    (CC, re.compile(rf"{_BETWEEN}(?:Código\s+Civil|CC)\b", re.IGNORECASE)),
    (
        NRAU,
        re.compile(
            rf"{_BETWEEN}(?:NRAU|Novo\s+Regime\s+do\s+Arrendamento\s+Urbano|Lei\s+n\.?º\s*6/2006)",
            re.IGNORECASE,
        ),
    ),
)
_ELSEWHERE = re.compile(
    rf"{_BETWEEN}(?:Lei\b|Decreto|DL\b|Portaria|Código\s|Constituição|CRP\b|CPT\b|"
    r"Regulamento|Diretiva|Directiva)",
    re.IGNORECASE,
)
# Words that put a question in tenancy, for a bare number more than one diploma holds.
_TENANCY = re.compile(
    r"\barrend|\bsenhori|\binquilin|\blocad|\blocaç|\bdespejo|\brendas?\b", re.IGNORECASE
)


class Reference(NamedTuple):
    article: str  # '199-A'
    diploma: str | None  # None when the text names none


def normalise_article(number: str) -> str:
    """'199.º-A' -> '199-A', '238.º' -> '238'."""
    match = re.match(r"(\d+)(?:\.º|º)?(?:\s*-\s*([A-Z]{1,2}))?", number.strip(), re.IGNORECASE)
    if match is None:
        raise ValueError(f"not an article number: {number!r}")
    suffix = (match.group(2) or "").upper()
    return f"{int(match.group(1))}-{suffix}" if suffix else str(int(match.group(1)))


MAX_RANGE = 20  # "artigos 344.º a 346.º" names 345.º too; a longer span is kept as its two ends
_TOKEN = re.compile(rf"(?P<number>{_NUMBER})|(?P<joiner>,|\be\b|\ba\b)", re.IGNORECASE)


def _diploma_after(rest: str) -> tuple[bool, str | None]:
    """Whether the reference stays in the corpus, and the diploma it names, if one."""
    for diploma, named in _IN_CORPUS:
        if named.match(rest):
            return True, diploma
    return not _ELSEWHERE.match(rest), None


def find_references(text: str) -> list[Reference]:
    """Articles the text names, in order, once each, with the diploma named after them. A range
    ("344.º a 346.º") names every article in it."""
    found: list[Reference] = []

    def add(reference: Reference) -> None:
        if reference not in found:
            found.append(reference)

    for match in _REFERENCE.finditer(text):
        kept, diploma = _diploma_after(text[match.end() :])
        if not kept:
            continue
        previous, joiner = None, None
        for token in _TOKEN.finditer(match.group("numbers")):
            if token.group("joiner"):
                joiner = token.group("joiner").lower()
                continue
            article = normalise_article(token.group("number"))
            if joiner == "a" and previous and previous.isdigit() and article.isdigit():
                start, end = int(previous), int(article)
                if 0 < end - start <= MAX_RANGE:
                    for number in range(start + 1, end):
                        add(Reference(str(number), diploma))
            add(Reference(article, diploma))
            previous, joiner = article, None
    return found


def diplomas_for(question: str) -> tuple[str, ...]:
    """Where a bare article number is looked for, in order: tenancy first if the question speaks
    of it, the Código do Trabalho first otherwise."""
    return (NRAU, CC, CT) if _TENANCY.search(question) else (CT, NRAU, CC)


class WithReferences:
    """Puts the articles a question names first, if in force on the date asked about, then the
    base retriever's ranking. A bare number is the first diploma's, in diplomas_for's order,
    that has the article that day."""

    def __init__(self, base: Retriever, article_at: ArticleAt) -> None:
        self.base = base
        self.article_at = article_at  # from either store
        self.name = f"{base.name}+refs"

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        named: list[Citation] = []
        for reference in find_references(question):
            candidates = [reference.diploma] if reference.diploma else diplomas_for(question)
            for diploma in candidates:
                if self.article_at(diploma, reference.article, as_of) is not None:
                    named.append(Citation(diploma=diploma, article=reference.article))
                    break
        named = list(dict.fromkeys(named))
        ranked = named + [c for c in self.base.search(question, as_of, k) if c not in named]
        return ranked[:k]
