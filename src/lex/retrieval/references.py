"""Explicit article references in a question, resolved before any search (ADR 0004).

"artigo 199.º-A", "art. 238.º CT", "o n.º 2 do artigo 131.º", "artigos 344.º e 345.º": a
question that names its article has one right target, and neither BM25 nor dense search can
find it, because article numbers are not in the article text. A reference that names another
diploma ("artigo 108.º da Lei n.º 102/2009", "do Código Civil") is left alone: the corpus holds
only the Código do Trabalho, so a bare number is read as one of its articles (ADR 0004).
"""

import datetime as dt
import re

from lex.domain import Citation, Retriever
from lex.store.models import ArticleAt

CT = "lei-7-2009"

# "artigo", "artigos", "art.", "arts.", "art.º", then one or more numbers joined by "," "e" "a".
_NUMBER = r"\d+(?:\.º|º)?(?:\s*-\s*[A-Z]{1,2}\b)?"
_REFERENCE = re.compile(
    rf"\b(?:artigos?|arts?\.(?:º)?|art\.º)\s+(?P<numbers>{_NUMBER}(?:\s*(?:,|e|a)\s*{_NUMBER})*)",
    re.IGNORECASE,
)
# What may follow a reference and still point outside the code.
_OTHER_DIPLOMA = re.compile(
    r"^\s*(?:,\s*)?(?:n\.º\s*\d+\s*,?\s*)?(?:d[oa]s?\s+)?"
    r"(?:Lei\b|Decreto|DL\b|Portaria|Código\s+(?!do\s+Trabalho)|Constituição|CRP\b|CC\b|CPT\b|"
    r"Regulamento|Diretiva|Directiva)",
    re.IGNORECASE,
)


def normalise_article(number: str) -> str:
    """'199.º-A' -> '199-A', '238.º' -> '238'."""
    match = re.match(r"(\d+)(?:\.º|º)?(?:\s*-\s*([A-Z]{1,2}))?", number.strip(), re.IGNORECASE)
    if match is None:
        raise ValueError(f"not an article number: {number!r}")
    suffix = (match.group(2) or "").upper()
    return f"{int(match.group(1))}-{suffix}" if suffix else str(int(match.group(1)))


MAX_RANGE = 20  # "artigos 344.º a 346.º" names 345.º too; a longer span is kept as its two ends
_TOKEN = re.compile(rf"(?P<number>{_NUMBER})|(?P<joiner>,|\be\b|\ba\b)", re.IGNORECASE)


def find_references(question: str) -> list[str]:
    """Article numbers of the Código do Trabalho that the question names, in order, once each.
    A range ("344.º a 346.º") names every article in it."""
    found: list[str] = []

    def add(article: str) -> None:
        if article not in found:
            found.append(article)

    for match in _REFERENCE.finditer(question):
        if _OTHER_DIPLOMA.match(question[match.end() :]):
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
                        add(str(number))
            add(article)
            previous, joiner = article, None
    return found


class WithReferences:
    """Puts the articles a question names first, if in force on the date asked about, then the
    base retriever's ranking."""

    def __init__(self, base: Retriever, article_at: ArticleAt) -> None:
        self.base = base
        self.article_at = article_at  # from either store
        self.name = f"{base.name}+refs"

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        named = [
            Citation(diploma=CT, article=article)
            for article in find_references(question)
            if self.article_at(CT, article, as_of) is not None
        ]
        ranked = named + [c for c in self.base.search(question, as_of, k) if c not in named]
        return ranked[:k]
