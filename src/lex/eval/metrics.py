"""Metrics, as bench/README.md defines them."""

from collections.abc import Sequence

from lex.domain import Citation


def recall_at_k(expected: Sequence[Citation], ranked: Sequence[Citation], k: int) -> float:
    """Share of the expected articles found among the first k retrieved."""
    if not expected:
        raise ValueError("recall is undefined for an item that expects no article")
    return len(set(expected) & set(ranked[:k])) / len(set(expected))


def citation_precision(
    cited: Sequence[Citation], must: Sequence[Citation], may: Sequence[Citation]
) -> float | None:
    """Share of the cited articles that are in must_cite or may_cite; None if nothing is cited."""
    if not cited:
        return None
    return len(set(cited) & (set(must) | set(may))) / len(set(cited))


def citation_recall(cited: Sequence[Citation], must: Sequence[Citation]) -> float:
    """Share of the must_cite articles that are cited."""
    if not must:
        raise ValueError("citation recall is undefined for an item that expects no article")
    return len(set(must) & set(cited)) / len(set(must))


def mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None
