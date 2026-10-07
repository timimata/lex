"""Checks the committed results against themselves and the benchmark, with no model and no
corpus, so CI can run it (`python -m lex.eval check-results`):

- a dev run's summary is what its own items add up to, so no number was edited by hand or left
  behind by a change to the harness;
- the test runs the leaderboard reads (results/test/*.json) are all on one version of the test
  split, and, where test.jsonl is present, on its current version, so the leaderboard never
  mixes numbers on different questions.
"""

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from lex.eval.harness import AnswerResult, ItemResult, summarise, summarise_answers
from lex.eval.results import bench_version

TOLERANCE = 1e-9


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(a - b) <= TOLERANCE
    return bool(a == b)


def _recomputed(run: dict[str, Any]) -> dict[str, Any] | None:
    """The run's summary from its items, or None if it is not a retrieval or answers run."""
    items = run.get("items")
    if not items or not isinstance(items[0], dict) or "recall" not in items[0]:
        return None
    if run["config"].get("task") == "answers":
        known = {f.name for f in fields(AnswerResult)}
        answers = [AnswerResult(**{k: v for k, v in i.items() if k in known}) for i in items]
        return dict(summarise_answers(answers))
    retrieval = [
        ItemResult(
            id=i["id"],
            type=i["type"],
            recall={int(k): v for k, v in i["recall"].items()},
            retrieved=i.get("retrieved", []),
            expected=i.get("expected", []),
        )
        for i in items
    ]
    return dict(summarise(retrieval))


def check_results(results_dir: Path, data_dir: Path) -> list[str]:
    problems = []
    for path in sorted((results_dir / "dev").glob("*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        recomputed = _recomputed(run)
        if recomputed is None:
            continue
        stored = {k: v for k, v in run["summary"].items() if k != "correctness"}
        if not _same(stored, recomputed):
            problems.append(f"{path.name}: its summary is not what its items add up to")

    versions: dict[str, list[str]] = {}
    for path in sorted((results_dir / "test").glob("*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        versions.setdefault(run["bench"]["sha"], []).append(path.name)
    if len(versions) > 1:
        problems.append(f"results/test/ mixes test split versions: {sorted(versions)}")
    if versions and (data_dir / "test.jsonl").exists():
        current = bench_version("test", data_dir)["sha"]
        stale = [name for sha, names in versions.items() if sha != current for name in names]
        if stale:
            problems.append(f"test runs on an earlier test split: {', '.join(stale)}")
    return problems
