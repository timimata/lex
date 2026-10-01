"""Cross-references: the articles that the best-ranked articles point to, placed right after them.

A composite question often needs two articles where one names the other ("nos termos do artigo
238.º", "salvo no caso previsto no artigo seguinte"); retrieval tends to find the first and miss
the second. On dev, following such references would have recovered 2 of the 6 second articles
missed by the demo's retriever. How many articles to follow and how many references to take from
each are set here, not tuned on dev (9 composite items would only fit noise).
"""

import datetime as dt
import re

from lex.domain import Citation, Retriever
from lex.retrieval.references import find_references
from lex.store.models import ArticleAt

TOP = 3  # the articles whose references are followed
PER_ARTICLE = 2  # references taken from each, in the order the text gives them
_RELATIVE = re.compile(r"\bartigo\s+(anterior|seguinte)\b", re.IGNORECASE)


def cited_by(text: str, article: str) -> list[str]:
    """The code's articles an article's text refers to, in order, itself excluded: by number
    ("artigo 238.º", with the reference parser's rules for other diplomas) and by position
    ("o artigo anterior", "o artigo seguinte")."""
    refs = find_references(text)
    if article.isdigit():
        for match in _RELATIVE.finditer(text):
            step = 1 if match.group(1).lower() == "seguinte" else -1
            refs.append(str(int(article) + step))
    return [r for r in dict.fromkeys(refs) if r != article]


class WithCrossReferences:
    def __init__(
        self, base: Retriever, article_at: ArticleAt, top: int = TOP, per_article: int = PER_ARTICLE
    ) -> None:
        self.base = base
        self.article_at = article_at
        self.top = top
        self.per_article = per_article
        self.name = f"{base.name}+xrefs"

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        ranked = self.base.search(question, as_of, k)
        out: list[Citation] = []
        for rank, citation in enumerate(ranked):
            if citation not in out:
                out.append(citation)
            if rank >= self.top:
                continue
            version = self.article_at(citation.diploma, citation.article, as_of)
            if version is None:
                continue
            taken = 0
            for ref in cited_by(version.text, citation.article):
                if taken == self.per_article:
                    break
                target = Citation(diploma=citation.diploma, article=ref)
                if target in out or self.article_at(target.diploma, ref, as_of) is None:
                    continue
                out.append(target)  # moved up if the base ranked it lower: two signals agree
                taken += 1
        return out[:k]
