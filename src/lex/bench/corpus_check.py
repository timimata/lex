"""Checks that need the corpus: every cited article of a diploma the corpus holds exists, and
every `must_cite` article has a version in force on the item's `as_of`.

The corpus is read from the ingestion output (data/processed/<code>/versions.jsonl) as plain
JSON, so the benchmark still depends only on lex.domain. Like the other checks, problems name the
file, id and field, never the article, so running this over test shows nothing of its content.
"""

import json
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from lex.bench.schema import Item

Periods = dict[tuple[str, str], list[tuple[str, str | None]]]

# What a question about tenancy, which the corpus holds since ADR 0017, is likely to say.
TENANCY = re.compile(
    r"\barrend|\bsenhori|\binquilin|\blocaç|\bdespejo|\brendas?\b|\bNRAU\b|6/2006|Código Civil",
    re.IGNORECASE,
)


def load_periods(versions_paths: Iterable[Path]) -> Periods:
    """(diploma, article) -> (valid_from, valid_to) of each stored version, as ISO dates."""
    periods: Periods = defaultdict(list)
    for path in versions_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            v = json.loads(line)
            periods[(v["diploma"], v["article"])].append((v["valid_from"], v["valid_to"]))
    return periods


def check_citations(items: dict[str, list[Item]], periods: Periods) -> list[str]:
    """Problems with the cited articles of the given items, keyed by split or file name."""
    held = {diploma for diploma, _ in periods}
    problems = []
    for name, rows in items.items():
        for item in rows:
            day = item.as_of.isoformat()
            for field in ("must_cite", "may_cite"):
                for n, cite in enumerate(getattr(item, field)):
                    if cite.diploma not in held:
                        continue  # other diplomas are outside the corpus by design
                    spans = periods.get((cite.diploma, cite.article))
                    if spans is None:
                        problems.append(f"{name} {item.id}: {field}[{n}] is not in the corpus")
                    elif field == "must_cite" and not any(
                        start <= day and (end is None or day < end) for start, end in spans
                    ):
                        problems.append(
                            f"{name} {item.id}: {field}[{n}] has no version in force on as_of"
                        )
    return problems


def refusals_to_review(items: dict[str, list[Item]]) -> list[str]:
    """`unanswerable` items written for the Código do Trabalho alone (ids ct-*), before the
    corpus held tenancy, that speak of it: their right answer may no longer be a refusal. Ids
    only, for a person to review."""
    return [
        f"{name} {item.id}"
        for name, rows in items.items()
        for item in rows
        if item.id.startswith("ct-")
        and item.type == "unanswerable"
        and TENANCY.search(" ".join([item.question, item.answer, item.notes or ""]))
    ]
