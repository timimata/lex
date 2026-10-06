"""Runs a Retriever or a System over benchmark items and scores it, as bench/README.md defines.

Retrieval is scored on answerable items only: an `unanswerable` item has no article to find, and
its refusal is scored when a System answers it. A refused answer counts as citing nothing: its
citations are not claims.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from lex.bench.schema import Item
from lex.domain import Citation, Retriever, System
from lex.eval.metrics import citation_precision, citation_recall, mean, recall_at_k

KS = (1, 3, 5, 10)


@dataclass(frozen=True)
class ItemResult:
    id: str
    type: str
    recall: dict[int, float]  # k -> recall@k
    retrieved: list[str]  # "diploma/article", best first
    expected: list[str]


def run_retrieval(
    items: list[Item], retriever: Retriever, ks: tuple[int, ...] = KS
) -> list[ItemResult]:
    results = []
    for item in items:
        if item.type == "unanswerable":
            continue
        ranked = retriever.search(item.question, item.as_of, max(ks))
        results.append(
            ItemResult(
                id=item.id,
                type=item.type,
                recall={k: recall_at_k(item.must_cite, ranked, k) for k in ks},
                retrieved=_ids(ranked),
                expected=_ids(item.must_cite),
            )
        )
    return results


def summarise(results: list[ItemResult]) -> dict[str, dict[str, float | int | None]]:
    """Mean recall@k overall and per question type, with the number of items behind each."""
    groups: dict[str, list[ItemResult]] = defaultdict(list)
    for r in results:
        groups["all"].append(r)
        groups[r.type].append(r)
    ks = sorted({k for r in results for k in r.recall})
    return {
        name: {"items": len(rs), **{f"recall@{k}": mean([r.recall[k] for r in rs]) for k in ks}}
        for name, rs in sorted(groups.items(), key=lambda g: (g[0] != "all", g[0]))
    }


@dataclass(frozen=True)
class AnswerResult:
    id: str
    type: str
    refused: bool
    precision: float | None  # None when nothing is cited, and on unanswerable items
    recall: float | None  # None on unanswerable items
    cited: list[str]  # "diploma/article", as the answer cites them
    expected: list[str]  # must_cite
    allowed: list[str]  # may_cite
    text: str
    requests: list[str] = field(default_factory=list)  # what the system asked for first


def _ids(citations: list[Citation]) -> list[str]:
    return [f"{c.diploma}/{c.article}" for c in citations]


def run_answers(items: list[Item], system: System) -> list[AnswerResult]:
    results = []
    for item in items:
        answer = system.answer(item.question, item.as_of)
        cited = [] if answer.refused else answer.citations
        answerable = item.type != "unanswerable"
        results.append(
            AnswerResult(
                id=item.id,
                type=item.type,
                refused=answer.refused,
                precision=citation_precision(cited, item.must_cite, item.may_cite)
                if answerable
                else None,
                recall=citation_recall(cited, item.must_cite) if answerable else None,
                cited=_ids(answer.citations),
                expected=_ids(item.must_cite),
                allowed=_ids(item.may_cite),
                text=answer.text,
                requests=answer.requests,
            )
        )
    return results


def summarise_answers(results: list[AnswerResult]) -> dict[str, dict[str, float | int | None]]:
    """Per question type, and over all answerable items together: the share refused (right for
    `unanswerable`, wrong for the rest), citation precision over the answers that cite something
    (`cited`, how many) and citation recall over every answerable item."""
    groups: dict[str, list[AnswerResult]] = defaultdict(list)
    for r in results:
        if r.type != "unanswerable":
            groups["answerable"].append(r)
        groups[r.type].append(r)
    summary: dict[str, dict[str, float | int | None]] = {}
    for name, rs in sorted(groups.items(), key=lambda g: (g[0] != "answerable", g[0])):
        precisions = [r.precision for r in rs if r.precision is not None]
        recalls = [r.recall for r in rs if r.recall is not None]
        summary[name] = {
            "items": len(rs),
            "refused": mean([float(r.refused) for r in rs]),
            "cited": len(precisions),
            "citation_precision": mean(precisions),
            "citation_recall": mean(recalls),
        }
    return summary
