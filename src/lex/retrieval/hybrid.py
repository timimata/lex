"""Reciprocal rank fusion of several retrievers' rankings (Cormack et al., 2009).

Each retriever returns its top `depth` articles; an article scores the sum of 1 / (k + rank) over
the rankings it appears in. k = 60 and depth = 50 are the usual defaults, used as they are: with
40 answerable dev items, tuning them would fit the dev set rather than the task.
"""

import datetime as dt
from collections import defaultdict

from lex.domain import Citation, Retriever

K = 60
DEPTH = 50


class Hybrid:
    def __init__(self, retrievers: list[Retriever], k: int = K, depth: int = DEPTH) -> None:
        self.retrievers = retrievers
        self.k = k
        self.depth = depth
        self.name = "-".join(["hybrid", *(r.name for r in retrievers)])

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        scores: dict[Citation, float] = defaultdict(float)
        first_seen: dict[Citation, int] = {}
        for retriever in self.retrievers:
            for rank, citation in enumerate(retriever.search(question, as_of, self.depth), start=1):
                scores[citation] += 1 / (self.k + rank)
                first_seen.setdefault(citation, len(first_seen))
        ranked = sorted(scores, key=lambda c: (-scores[c], first_seen[c]))
        return ranked[:k]
