"""Two runs compared item by item (ROADMAP, Phase 10): `python -m lex.eval compare A B`.

Totals hide which questions changed: 50 correct before and 50 after can be ten gained and ten
lost. Pairing the two runs by item, only the items on which they disagree say anything, and an
exact sign test on them says how often a difference that large would come from noise alone, as
two runs of the same system differ (ADR 0018). Ids only: a test run's items are scores by id.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import comb
from typing import Any

ALPHA = 0.05  # a regression is a loss a fair coin would give less often than this


@dataclass(frozen=True)
class Paired:
    measure: str  # "correct" or "refused" (an answerable question wrongly refused)
    items: int  # answerable items in both runs, with the measure in each
    only_a: list[str]  # ids where the first run has it and the second not
    only_b: list[str]

    def p_value(self) -> float:
        """Two-sided exact sign test on the items the runs disagree on."""
        return sign_test(len(self.only_a), len(self.only_b))


def sign_test(a: int, b: int) -> float:
    """The chance, if each disagreement went either way with even odds, of a split at least as
    uneven as a against b."""
    n = a + b
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(min(a, b) + 1)) / (1 << n)
    return min(1.0, 2 * tail)


def one_sided(worse: int, better: int) -> float:
    """The chance, with even odds, of at least `worse` of the disagreements going against."""
    n = worse + better
    if n == 0:
        return 1.0
    return sum(comb(n, i) for i in range(worse, n + 1)) / (1 << n)


def _has(item: Mapping[str, Any], measure: str) -> bool | None:
    if item.get("type") == "unanswerable":
        return None
    if measure == "correct":
        verdict = item.get("verdict")
        return None if verdict is None else verdict == "correta"
    return bool(item.get("refused"))


def paired(a: Sequence[Mapping[str, Any]], b: Sequence[Mapping[str, Any]], measure: str) -> Paired:
    """The answerable items both runs scored for `measure`, and those only one of them has."""
    first = {i["id"]: _has(i, measure) for i in a}
    second = {i["id"]: _has(i, measure) for i in b}
    both = [i for i in first if i in second and first[i] is not None and second[i] is not None]
    return Paired(
        measure,
        len(both),
        [i for i in both if first[i] and not second[i]],
        [i for i in both if second[i] and not first[i]],
    )


def regressed(before: Sequence[Mapping[str, Any]], now: Sequence[Mapping[str, Any]]) -> list[str]:
    """Why `now` is worse than `before` beyond the noise, if it is: fewer answers judged correct,
    or more answerable questions refused, with a one-sided sign test under ALPHA."""
    found = []
    correct = paired(before, now, "correct")
    if one_sided(len(correct.only_a), len(correct.only_b)) < ALPHA:
        found.append(
            f"correct on {len(correct.only_a)} items it no longer gets right and gained "
            f"{len(correct.only_b)}: {', '.join(correct.only_a)}"
        )
    refused = paired(before, now, "refused")
    if one_sided(len(refused.only_b), len(refused.only_a)) < ALPHA:
        found.append(
            f"refuses {len(refused.only_b)} answerable items it answered and answers "
            f"{len(refused.only_a)} it refused: {', '.join(refused.only_b)}"
        )
    return found
