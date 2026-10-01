"""Which split an item belongs to, and the checks that keep the splits honest.

The split is a hash of the item's group, so nobody chooses it and it never changes. The group is
the item's main article, its first `must_cite`; an item that cites nothing is its own group.
Items about the same article therefore always share a split, so a dev item never gives away a
test item's answer (ADR 0009). Items are written to incoming.jsonl without a split; `assign`
moves each to the file its group dictates.

Nothing here prints item content. Problems are reported by file, line, id and field, so running
the checks over test.jsonl never shows what is in it.
"""

import hashlib
from collections import Counter
from pathlib import Path
from typing import get_args

from pydantic import ValidationError

from lex.bench.schema import Item, QuestionType

DATA_DIR = Path(__file__).resolve().parents[3] / "bench" / "data"
SPLITS = ("dev", "test")
INCOMING = "incoming"


def group_of(item: Item) -> str:
    """'lei-7-2009/131' for an item whose main article is article 131.º; the id if it cites
    nothing."""
    if item.must_cite:
        main = item.must_cite[0]
        return f"{main.diploma}/{main.article}"
    return item.id


def split_for(item: Item) -> str:
    return "test" if hashlib.sha256(group_of(item).encode()).digest()[0] % 2 else "dev"


def _parse(path: Path) -> tuple[list[Item], list[str]]:
    items: list[Item] = []
    problems: list[str] = []
    if not path.exists():
        return items, problems
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            items.append(Item.model_validate_json(line))
        except ValidationError as e:
            fields = "; ".join(
                f"{'.'.join(map(str, err['loc'])) or 'item'}: {err['msg']}" for err in e.errors()
            )
            problems.append(f"{path.name}:{number}: {fields}")
    return items, problems


def load(split: str, data_dir: Path = DATA_DIR) -> list[Item]:
    """The items of one split. Only the eval harness calls this for test (CLAUDE.md)."""
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    items, problems = _parse(data_dir / f"{split}.jsonl")
    if problems:
        raise ValueError(f"{split} does not validate; run python -m lex.bench validate")
    return items


def items_by_file(data_dir: Path = DATA_DIR) -> dict[str, list[Item]]:
    """The valid items of dev, test and incoming, by file name. Invalid lines are left to
    `check` to report."""
    return {name: _parse(data_dir / f"{name}.jsonl")[0] for name in (*SPLITS, INCOMING)}


def _normalise(question: str) -> str:
    return " ".join(question.casefold().split())


def check(data_dir: Path = DATA_DIR) -> list[str]:
    """Every problem in the benchmark files. An empty list means they are consistent."""
    problems: list[str] = []
    file_of: dict[str, str] = {}
    id_of_question: dict[str, str] = {}
    # An ACT FAQ entry is one question: one item about the present at most; it may also be asked
    # about an earlier date, as a temporal item (one per date).
    id_of_entry: dict[tuple[str, str], str] = {}
    for name in (*SPLITS, INCOMING):
        items, parse_problems = _parse(data_dir / f"{name}.jsonl")
        problems += parse_problems
        for item in items:
            if item.id in file_of:
                problems.append(f"{item.id} is in both {file_of[item.id]} and {name}")
            file_of[item.id] = name
            if name in SPLITS and split_for(item) != name:
                problems.append(
                    f"{item.id} is in {name}, but its group puts it in {split_for(item)}"
                )
            question = _normalise(item.question)
            if question in id_of_question:
                problems.append(f"{item.id} repeats the question of {id_of_question[question]}")
            id_of_question.setdefault(question, item.id)
            if "/items(" in str(item.source.url):
                when = item.as_of.isoformat() if item.type == "temporal" else "present"
                entry = (str(item.source.url), when)
                if entry in id_of_entry:
                    problems.append(
                        f"{item.id} comes from the same FAQ entry, about the same date, as "
                        f"{id_of_entry[entry]}"
                    )
                id_of_entry.setdefault(entry, item.id)
    return problems


def assign(data_dir: Path = DATA_DIR) -> Counter[str]:
    """Move every incoming item to its split. Call only when `check` finds no problems."""
    incoming = data_dir / f"{INCOMING}.jsonl"
    items, _ = _parse(incoming)
    moved: Counter[str] = Counter()
    for item in items:
        split = split_for(item)
        with (data_dir / f"{split}.jsonl").open("a", encoding="utf-8", newline="\n") as f:
            f.write(item.model_dump_json() + "\n")
        moved[split] += 1
    incoming.write_text("", encoding="utf-8")
    return moved


def summary(data_dir: Path = DATA_DIR) -> str:
    """Item counts per file and type."""
    types: tuple[str, ...] = get_args(QuestionType)
    rows = [("", *types, "total")]
    for name in (*SPLITS, INCOMING):
        items, _ = _parse(data_dir / f"{name}.jsonl")
        counts: Counter[str] = Counter(item.type for item in items)
        rows.append((name, *(str(counts[t]) for t in types), str(len(items))))
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return "\n".join(
        "  ".join(cell.rjust(w) for cell, w in zip(row, widths, strict=True)) for row in rows
    )
