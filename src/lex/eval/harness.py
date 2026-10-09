"""Runs a Retriever or a System over benchmark items and scores it, as bench/README.md defines.

Retrieval is scored on answerable items only: an `unanswerable` item has no article to find, and
its refusal is scored when a System answers it. A refused answer counts as citing nothing: its
citations are not claims.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field

from lex.bench.schema import Item
from lex.domain import Answer, Citation, Retriever, System
from lex.eval.metrics import citation_precision, citation_recall, mean, recall_at_k

KS = (1, 3, 5, 10)


@dataclass(frozen=True)
class ItemResult:
    id: str
    type: str
    recall: dict[int, float]  # k -> recall@k
    retrieved: list[str] = field(default_factory=list)  # "diploma/article", best first
    expected: list[str] = field(default_factory=list)


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
    # Share of must_cite the model was given: recall's loss down to it is retrieval's, the rest
    # the answer's. None on unanswerable items and where the system does not say what it gave.
    given_recall: float | None = None
    # Share of the cited articles whose version the model read is the one in force on as_of, by
    # the corpus index: what answering for a date claims. None where no version is known.
    version_right: float | None = None
    # Test runs keep none of the fields below but the verdict (lex.eval.results.TEST_FIELDS).
    cited: list[str] = field(default_factory=list)  # "diploma/article", as the answer cites them
    expected: list[str] = field(default_factory=list)  # must_cite
    allowed: list[str] = field(default_factory=list)  # may_cite
    text: str = ""
    requests: list[str] = field(default_factory=list)  # what the system asked for first
    tokens: dict[str, int] = field(default_factory=dict)  # calls and tokens the answer took
    verdict: str | None = None  # the judge's, on an answerable item, when the run is judged
    reason: str | None = None  # the judge's sentence for it
    verdicts: list[str] = field(default_factory=list)  # each sample's, if more than one
    given: list[str] = field(default_factory=list)  # "diploma/article@valid_from", as read
    refusal_reason: str = ""  # the model's, on a refusal: read, never shown or scored


def _ids(citations: list[Citation]) -> list[str]:
    return [f"{c.diploma}/{c.article}" for c in citations]


def _version_right(
    item: Item, answer: Answer, periods: Mapping[tuple[str, str], list[tuple[str, str | None]]]
) -> float | None:
    day = item.as_of.isoformat()
    read = {
        (v.diploma, v.article): v.valid_from.isoformat()
        for v in [*answer.given, *answer.cited_versions]
    }
    checked = []
    for c in answer.citations:
        if (c.diploma, c.article) in read and (c.diploma, c.article) in periods:
            in_force = [
                s for s, e in periods[(c.diploma, c.article)] if s <= day and (e is None or day < e)
            ]
            checked.append(in_force == [read[(c.diploma, c.article)]])
    return sum(checked) / len(checked) if checked else None


def run_answers(
    items: list[Item],
    system: System,
    periods: Mapping[tuple[str, str], list[tuple[str, str | None]]] | None = None,
) -> list[AnswerResult]:
    """Each item answered and scored; with the corpus's periods (lex.bench.corpus_check), the
    versions cited are checked against the date too."""
    results = []
    for item in items:
        answer = system.answer(item.question, item.as_of)
        cited = [] if answer.refused else answer.citations
        answerable = item.type != "unanswerable"
        read = [Citation(diploma=v.diploma, article=v.article) for v in answer.given]
        results.append(
            AnswerResult(
                id=item.id,
                type=item.type,
                refused=answer.refused,
                precision=citation_precision(cited, item.must_cite, item.may_cite)
                if answerable
                else None,
                recall=citation_recall(cited, item.must_cite) if answerable else None,
                given_recall=citation_recall(read, item.must_cite)
                if answerable and answer.given
                else None,
                version_right=_version_right(item, answer, periods)
                if answerable and periods and not answer.refused
                else None,
                cited=_ids(answer.citations),
                expected=_ids(item.must_cite),
                allowed=_ids(item.may_cite),
                text=answer.text,
                requests=answer.requests,
                tokens=answer.tokens,
                given=[f"{v.diploma}/{v.article}@{v.valid_from}" for v in answer.given],
                refusal_reason=answer.reason,
            )
        )
    return results


def summarise_answers(results: list[AnswerResult]) -> dict[str, dict[str, float | int | None]]:
    """Per question type, and over all answerable items together: the share refused (right for
    `unanswerable`, wrong for the rest), citation precision over the answers that cite something
    (`cited`, how many) and citation recall over every answerable item. Where the system says
    what its model read: `given_recall`, the share of must_cite it was given, and `unsupported`,
    how many answers it made though given no must_cite article."""
    says = any(r.given_recall is not None for r in results)
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
        if says:
            given = [r.given_recall for r in rs if r.given_recall is not None]
            summary[name]["given_recall"] = mean(given)
            summary[name]["unsupported"] = sum(
                r.given_recall == 0 and not r.refused for r in rs if r.type != "unanswerable"
            )
        if any(r.version_right is not None for r in results):
            versions = [r.version_right for r in rs if r.version_right is not None]
            summary[name]["version_right"] = mean(versions)
    return summary
