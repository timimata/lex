"""Where every reported number comes from (CLAUDE.md: a number not in results/ is not reported).

A dev run overwrites results/dev/<system>.json, and git keeps its history. A test run writes a
new, dated file and keeps no per-item detail, and it refuses to run from a working tree with
uncommitted changes, because its number would not be reproducible from a commit. Every run
records which version of its split it ran on, so numbers on different questions are never
compared.
"""

import datetime as dt
import hashlib
import json
import subprocess
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"
BENCH = ROOT / "bench" / "data"


def bench_version(split: str, data_dir: Path = BENCH) -> dict[str, Any]:
    """The split's items, counted and fingerprinted: a hash of the file, never its content."""
    data = (data_dir / f"{split}.jsonl").read_bytes()
    lines = [line for line in data.splitlines() if line.strip()]
    return {"items": len(lines), "sha": hashlib.sha256(data).hexdigest()[:12]}


def git_state() -> tuple[str, bool]:
    """The current commit, and whether the working tree has uncommitted changes outside
    results/ (a result written by one run must not block the next)."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    changes = git("status", "--porcelain", "--", ".", ":(exclude)results")
    return git("rev-parse", "HEAD"), bool(changes)


def ensure_reproducible(split: str) -> None:
    """Refuse a test run from a working tree with uncommitted changes, before it starts."""
    if split == "test" and git_state()[1]:
        raise RuntimeError("test runs need a clean working tree: commit first")


def write(
    split: str,
    system: str,
    config: dict[str, Any],
    summary: dict[str, Any],
    items: Sequence["DataclassInstance"],
    results_dir: Path = RESULTS,
    data_dir: Path = BENCH,
) -> Path:
    ensure_reproducible(split)
    commit, dirty = git_state()
    now = dt.datetime.now().astimezone()
    record: dict[str, Any] = {
        "split": split,
        "bench": bench_version(split, data_dir),
        "system": system,
        "config": config,
        "commit": commit,
        "uncommitted_changes": dirty,
        "run_at": now.isoformat(timespec="seconds"),
        "summary": summary,
    }
    if split == "dev":
        record["items"] = [asdict(r) for r in items]
        path = results_dir / "dev" / f"{system}.json"
    else:
        path = results_dir / "test" / f"{now:%Y-%m-%dT%H%M}-{system}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return path
