"""Checks the committed results against themselves and the benchmark, with no model and no
corpus, so CI can run it (`python -m lex.eval check-results`):

- a dev run's summary is what its own items add up to, so no number was edited by hand or left
  behind by a change to the harness;
- the test runs the leaderboard reads (results/test/*.json) are all on one version of the test
  split, and, where test.jsonl is present, on its current version, so the leaderboard never
  mixes numbers on different questions;
- every run says which version of its split it ran on, dev runs ran on today's dev, and a run
  made from 2026-10-08 on was made by the code of the commit that added it (ROADMAP, Phase 10).
  A dev run comes before the commit that reports it, so uncommitted changes when it ran are
  normal; what must hold is that the run is committed with the code that made it.
"""

import json
import subprocess
from dataclasses import fields
from pathlib import Path
from typing import Any

from lex.bench.corpus_check import INDEX, index_fingerprint
from lex.eval import judge
from lex.eval.harness import AnswerResult, ItemResult, summarise, summarise_answers
from lex.eval.results import ROOT, bench_version, source, source_sha

TOLERANCE = 1e-9


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(a - b) <= TOLERANCE
    return bool(a == b)


# Runs from this day on keep each item's verdict, so their correctness is recomputed too.
VERDICTS_KEPT_SINCE = "2026-10-08"


def _recomputed(run: dict[str, Any]) -> dict[str, Any] | None:
    """The run's summary from its items, or None if it is not a retrieval or answers run."""
    items = run.get("items")
    if not items or not isinstance(items[0], dict) or "recall" not in items[0]:
        return None
    if run["config"].get("task") == "answers":
        known = {f.name for f in fields(AnswerResult)}
        answers = [AnswerResult(**{k: v for k, v in i.items() if k in known}) for i in items]
        summary: dict[str, Any] = dict(summarise_answers(answers))
        verdicts = {a.id: a.verdict for a in answers if a.verdict is not None}
        if verdicts:
            summary["correctness"] = judge.correctness(verdicts, {a.id: a.type for a in answers})
        return summary
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


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)


def _committed_source(root: Path, commit: str) -> dict[str, bytes]:
    """The code as the commit holds it, as `results.source` reads the working tree."""
    listed = _git(root, "ls-tree", "-r", "--name-only", commit, "--", "src/lex", "pyproject.toml")
    paths = [
        p
        for p in listed.stdout.decode().splitlines()
        if p == "pyproject.toml" or (p.endswith(".py") and "__pycache__" not in p)
    ]
    return {p: _git(root, "show", f"{commit}:{p}").stdout for p in paths}


def _provenance(path: Path, run: dict[str, Any], root: Path, dev: str | None) -> list[str]:
    """What is wrong with where a run comes from: no version of its split, an earlier dev, or
    code other than the commit's that added it."""
    name = path.name
    if "bench" not in run:
        return [f"{name}: it records no version of its split: run it again, or archive it"]
    if run["split"] == "dev" and dev is not None and run["bench"].get("scored") != dev:
        return [f"{name}: it ran on another version of dev: run it again, or archive it"]
    if "source" not in run:
        new = run.get("run_at", "") >= VERDICTS_KEPT_SINCE
        return [f"{name}: it records no source"] if new else []
    if _git(root, "cat-file", "-e", f"{run['commit']}^{{commit}}").returncode != 0:
        return []  # a history without the run's commit (the public mirror, a shallow clone)
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    if _git(root, "status", "--porcelain", "--", relative).stdout.strip():
        code = source(root)  # not committed yet: held to the working tree
    else:
        added = _git(root, "log", "-1", "--format=%H", "--", relative).stdout.decode().strip()
        code = _committed_source(root, added)
    if source_sha(code) != run["source"]:
        return [f"{name}: it was made by code other than the commit's that adds it: run it again"]
    return []


def check_results(
    results_dir: Path, data_dir: Path, index: Path = INDEX, root: Path = ROOT
) -> list[str]:
    problems = []
    runs = [
        *sorted((results_dir / "dev").glob("*.json")),
        *sorted((results_dir / "test").glob("*.json")),
    ]
    dev = bench_version("dev", data_dir)["scored"] if (data_dir / "dev.jsonl").exists() else None
    for path in runs:
        run = json.loads(path.read_text(encoding="utf-8"))
        if "items" in run:  # a retrieval, answers or judge run, not a latency record
            problems += _provenance(path, run, root, dev)
        recomputed = _recomputed(run)
        if recomputed is None:
            continue
        stored = dict(run["summary"])
        if "correctness" in stored and "correctness" not in recomputed:
            if run.get("run_at", "") >= VERDICTS_KEPT_SINCE:
                problems.append(f"{path.name}: it reports correctness but keeps no verdicts")
            del stored["correctness"]  # older runs: the shares alone were kept
        if not _same(stored, recomputed):
            problems.append(f"{path.name}: its summary is not what its items add up to")
        medians = [
            i["verdict"] == judge.median(i["verdicts"]) for i in run["items"] if i.get("verdicts")
        ]
        if not all(medians):
            problems.append(f"{path.name}: a verdict is not the median of its samples")

    # Runs are compared by what they read of the items (`scored`), so a reviewer's sign-off on
    # an item leaves them current; runs from before 2026-10-08 have only the file's hash.
    versions: dict[str, list[str]] = {}
    corpora: dict[str, list[str]] = {}  # runs from 2026-10-08 on record theirs
    for path in sorted((results_dir / "test").glob("*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        bench = run["bench"]
        versions.setdefault(bench.get("scored") or bench["sha"], []).append(path.name)
        if corpus := run.get("config", {}).get("corpus"):
            corpora.setdefault(corpus["fingerprint"], []).append(path.name)
    if len(corpora) > 1:
        problems.append(
            "results/test/ mixes corpora: " + "; ".join(map(", ".join, corpora.values()))
        )
    if corpora and index.exists():
        stale_corpus = [
            n for f, names in corpora.items() if f != index_fingerprint(index) for n in names
        ]
        if stale_corpus:
            problems.append(
                f"test runs on a corpus other than {index.name}'s: {', '.join(stale_corpus)}"
            )
    if len(versions) > 1:
        problems.append(f"results/test/ mixes test split versions: {sorted(versions)}")
    if versions and (data_dir / "test.jsonl").exists():
        now = bench_version("test", data_dir)
        current = {now["scored"], now["sha"]}
        stale = [name for v, names in versions.items() if v not in current for name in names]
        if stale:
            problems.append(f"test runs on an earlier test split: {', '.join(stale)}")
    return problems
