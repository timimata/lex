"""Checks that need the corpus: every cited article of the Código do Trabalho exists, and every
`must_cite` article has a version in force on the item's `as_of`.

The corpus is read from the ingestion output (data/processed/ct/versions.jsonl) as plain JSON, so
the benchmark still depends only on lex.domain. Like the other checks, problems name the file,
id and field, never the article, so running this over test shows nothing of its content.
"""

import json
from collections import defaultdict
from pathlib import Path

from lex.bench.schema import Item

CT = "lei-7-2009"


def load_periods(versions_path: Path) -> dict[str, list[tuple[str, str | None]]]:
    """Article number -> (valid_from, valid_to) of each stored version, as ISO dates."""
    periods: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
    for line in versions_path.read_text(encoding="utf-8").splitlines():
        v = json.loads(line)
        periods[v["article"]].append((v["valid_from"], v["valid_to"]))
    return periods


def check_citations(
    items: dict[str, list[Item]], periods: dict[str, list[tuple[str, str | None]]]
) -> list[str]:
    """Problems with the cited articles of the given items, keyed by split or file name."""
    problems = []
    for name, rows in items.items():
        for item in rows:
            day = item.as_of.isoformat()
            for field in ("must_cite", "may_cite"):
                for n, cite in enumerate(getattr(item, field)):
                    if cite.diploma != CT:
                        continue  # other diplomas are outside the corpus by design
                    if cite.article not in periods:
                        problems.append(f"{name} {item.id}: {field}[{n}] is not in the corpus")
                    elif field == "must_cite" and not any(
                        start <= day and (end is None or day < end)
                        for start, end in periods[cite.article]
                    ):
                        problems.append(
                            f"{name} {item.id}: {field}[{n}] has no version in force on as_of"
                        )
    return problems
