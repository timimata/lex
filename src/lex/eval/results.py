"""Where every reported number comes from (CLAUDE.md: a number not in results/ is not reported).

A dev run overwrites results/dev/<system>.json, and git keeps its history. A test run writes a
new, dated file that keeps each item's scores by id and nothing an item says or cites
(TEST_FIELDS), and it refuses to run from a working tree with uncommitted changes, because its
number would not be reproducible from a commit. Every run
records which version of its split it ran on, so numbers on different questions are never
compared.
"""

import datetime as dt
import hashlib
import json
import platform
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


# What a test run keeps of each item: its scores by id. Never a text, a citation or the judge's
# reason, which may quote the reference answer.
TEST_FIELDS = (
    "id",
    "type",
    "refused",
    "precision",
    "recall",
    "given_recall",
    "version_right",
    "verdict",
    "verdicts",
)

# What a run reads of an item. A legal reviewer's sign-off (status, validated_by) or a note does
# not change what is scored; a corrected answer or citation does.
SCORED = ("id", "question", "as_of", "type", "must_cite", "may_cite", "answer")


def bench_version(split: str, data_dir: Path = BENCH) -> dict[str, Any]:
    """The split's items, counted and fingerprinted, never shown: `sha` hashes the file,
    `scored` only what a run reads of each item (SCORED), the version runs are compared by."""
    data = (data_dir / f"{split}.jsonl").read_bytes()
    lines = [line for line in data.splitlines() if line.strip()]
    rows = []
    for line in lines:
        item = json.loads(line)
        scored = {key: item.get(key, [] if key.endswith("_cite") else None) for key in SCORED}
        rows.append(json.dumps(scored, sort_keys=True, ensure_ascii=False))
    return {
        "items": len(lines),
        "sha": hashlib.sha256(data).hexdigest()[:12],
        "scored": hashlib.sha256("\n".join(sorted(rows)).encode()).hexdigest()[:12],
    }


def git_state() -> tuple[str, bool]:
    """The current commit, and whether the working tree has uncommitted changes outside
    results/ (a result written by one run must not block the next)."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    changes = git("status", "--porcelain", "--", ".", ":(exclude)results")
    return git("rev-parse", "HEAD"), bool(changes)


def source(root: Path = ROOT) -> dict[str, bytes]:
    """The code that can change a number, as it stands in the working tree: the package and
    pyproject.toml, by path (line endings as git stores them)."""
    files = [*sorted((root / "src" / "lex").rglob("*.py")), root / "pyproject.toml"]
    return {
        f.relative_to(root).as_posix(): f.read_bytes().replace(b"\r\n", b"\n")
        for f in files
        if f.exists() and "__pycache__" not in f.parts
    }


def environment(root: Path = ROOT) -> dict[str, str | None]:
    """The Python a run ran on and the locked dependencies (uv.lock, ADR 0019), by hash."""
    lock = root / "uv.lock"
    locked = hashlib.sha256(lock.read_bytes()).hexdigest()[:16] if lock.exists() else None
    return {"python": platform.python_version(), "lock": locked}


def source_sha(files: dict[str, bytes]) -> str:
    """One hash of some code, by path and content (ROADMAP, Phase 10)."""
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.encode() + b"\0" + files[path] + b"\0")
    return digest.hexdigest()[:16]


def ensure_reproducible(split: str) -> None:
    """Refuse a test run from a working tree with uncommitted changes, before it starts."""
    if split == "test" and git_state()[1]:
        raise RuntimeError("test runs need a clean working tree: commit first")


# Tiago, 2026-10-09: test items may reach a model on a free tier, whose provider may train
# on them; each run records every endpoint's tier, and the dataset card says what was sent
# (ADR 0016, amended 2026-10-09). False restores the rule of 2026-10-08: a paid key, an operator
# who agreed, or this machine.
FREE_TIER_ON_TEST = True


def ensure_private(
    split: str,
    endpoints: dict[str, dict[str, str]],
    free_tier_on_test: bool = FREE_TIER_ON_TEST,
) -> None:
    """Refuse, before it starts, a test run that would send test items to a model on a free
    tier, unless that is accepted (`FREE_TIER_ON_TEST`). `endpoints` is what
    lex.generation.llm.endpoint says of each model the run calls."""
    if split != "test":
        return
    # "agreed": an outside system's operator agreed not to keep the questions (ADR 0016); an
    # operator who did not ("unagreed") never receives them, whatever the free tier's standing.
    allowed = ("local", "paid", "agreed", *(("free",) if free_tier_on_test else ()))
    refused = sorted(role for role, e in endpoints.items() if e["tier"] not in allowed)
    if refused:
        raise SystemExit(
            f"test runs would send test items to {', '.join(refused)} on terms ADR 0016 does not "
            "allow: an outside system needs its operator's agreement (--operator-agrees), a free "
            "tier needs FREE_TIER_ON_TEST"
        )


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
        # The code that made the run, so check-results can hold it to the commit that adds it.
        "source": source_sha(source()),
        "environment": environment(),
        "run_at": now.isoformat(timespec="seconds"),
        "summary": summary,
    }
    if split == "dev":
        record["items"] = [asdict(r) for r in items]
        path = results_dir / "dev" / f"{system}.json"
    else:
        # Scores by id and nothing an item says or cites, so the summary can be recomputed
        # without a copy of a test item outside test.jsonl (ADR 0016, amended 2026-10-08).
        record["items"] = [{k: v for k, v in asdict(r).items() if k in TEST_FIELDS} for r in items]
        path = results_dir / "test" / f"{now:%Y-%m-%dT%H%M}-{system}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return path
