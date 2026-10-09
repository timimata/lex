"""Which split an item belongs to, and the checks that keep the splits honest.

The split is a hash of the item's group, so nobody chooses it. The group was the item's main
article, its first `must_cite` (ADR 0009); since 2026-10-08 it also takes in every item linked to
it: one whose main article the other must cite, or one drawn from the same ACT FAQ entry. A group
is in dev if any of its items' main articles hashes to dev, and in test otherwise, so a group that
spanned both splits goes to dev and never the reverse: dev is public, and a dev item can never
become a test item (ADR 0009, amended). Items are written to incoming.jsonl without a split;
`assign` moves each to the split of the group it joins.

Nothing here prints item content. Problems are reported by file, line, id and field, so running
the checks over test.jsonl never shows what is in it.
"""

import datetime as dt
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
    """The split of the item's main article alone: its split unless a link puts it in a group
    with others (`placement`)."""
    return "test" if hashlib.sha256(group_of(item).encode()).digest()[0] % 2 else "dev"


def _keys(item: Item) -> tuple[set[str], set[str]]:
    """What an item offers to links (its main article, its FAQ entry) and what it reaches with
    (every article it must cite, its FAQ entry). Two items are linked when one reaches what the
    other offers."""
    entry = {f"entry {item.source.url}"} if "/items(" in str(item.source.url) else set()
    offers = {f"article {group_of(item)}"} if item.must_cite else set()
    reaches = {f"article {c.diploma}/{c.article}" for c in item.must_cite}
    return offers | entry, reaches | entry


def groups(items: list[Item]) -> list[list[Item]]:
    """The items joined into groups by their links, each group in the order its items come."""
    parent = list(range(len(items)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    offered: dict[str, list[int]] = {}
    for i, item in enumerate(items):
        for key in _keys(item)[0]:
            offered.setdefault(key, []).append(i)
    for i, item in enumerate(items):
        for key in _keys(item)[1]:
            for j in offered.get(key, []):
                parent[root(i)] = root(j)
    joined: dict[int, list[Item]] = {}
    for i, item in enumerate(items):
        joined.setdefault(root(i), []).append(item)
    return list(joined.values())


def group_split(group: list[Item]) -> str:
    """Dev if any of the group's main articles hashes to dev, else test: no dev item may ever
    move to test."""
    return "dev" if any(split_for(item) == "dev" for item in group) else "test"


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
            question = _normalise(item.question)
            if question in id_of_question:
                problems.append(f"{item.id} repeats the question of {id_of_question[question]}")
            id_of_question.setdefault(question, item.id)
            if "/items(" in str(item.source.url) and item.source.modified is None:
                problems.append(
                    f"{item.id} comes from an ACT FAQ entry but records no source.modified "
                    "(ADR 0008): python -m lex.bench stamp"
                )
            if "/items(" in str(item.source.url):
                when = item.as_of.isoformat() if item.type == "temporal" else "present"
                entry = (str(item.source.url), when)
                if entry in id_of_entry:
                    problems.append(
                        f"{item.id} comes from the same FAQ entry, about the same date, as "
                        f"{id_of_entry[entry]}"
                    )
                id_of_entry.setdefault(entry, item.id)
    placed, refused = placement(data_dir)
    problems += refused
    # Since benchmark v4 (ADR 0009, amended), a test item in a group with dev items is a fault.
    for split, ids in placed.items():
        for item_id in ids:
            where = file_of.get(item_id)
            if where in SPLITS and where != split:
                problems.append(f"{item_id} is in {where}, but its group puts it in {split}")
    return problems


def placement(data_dir: Path = DATA_DIR) -> tuple[dict[str, list[str]], list[str]]:
    """Where each item's group puts it, as ids by split; and the incoming items `assign` must
    refuse, which link groups already in both splits. An incoming item joins the split its
    group's other items are in; a group of new items alone goes where `group_split` says."""
    files = items_by_file(data_dir)
    where = {i.id: name for name in (*SPLITS, INCOMING) for i in files[name]}
    placed: dict[str, list[str]] = {"dev": [], "test": []}
    refused = []
    for group in groups([i for name in (*SPLITS, INCOMING) for i in files[name]]):
        settled = {where[i.id] for i in group} - {INCOMING}
        new = [i for i in group if where[i.id] == INCOMING]
        if new and len(settled) > 1:
            refused += [f"{i.id} (incoming) links items in dev and in test" for i in new]
            continue
        split = settled.pop() if new and settled else group_split(group)
        placed[split] += [i.id for i in group]
    return placed, refused


def assign(data_dir: Path = DATA_DIR) -> Counter[str]:
    """Move every incoming item to its group's split. Call only when `check` finds no
    problems."""
    incoming = data_dir / f"{INCOMING}.jsonl"
    items, _ = _parse(incoming)
    split_of = {i: split for split, ids in placement(data_dir)[0].items() for i in ids}
    moved: Counter[str] = Counter()
    for item in items:
        split = split_of[item.id]
        with (data_dir / f"{split}.jsonl").open("a", encoding="utf-8", newline="\n") as f:
            f.write(item.model_dump_json() + "\n")
        moved[split] += 1
    incoming.write_text("", encoding="utf-8")
    return moved


def stamp(modified: dict[str, dt.date], data_dir: Path = DATA_DIR) -> int:
    """Write each ACT FAQ entry's last-modified date (`modified`: entry URL -> date, from
    data/processed/act_faq.jsonl) into the items drawn from it that lack one. Only those lines
    change, and nothing a run reads. Returns how many were stamped."""
    stamped = 0
    for name in (*SPLITS, INCOMING):
        path = data_dir / f"{name}.jsonl"
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines):
            if not line.strip():
                continue
            item = Item.model_validate_json(line)
            day = modified.get(str(item.source.url))
            if day is not None and item.source.modified is None:
                source = item.source.model_copy(update={"modified": day})
                lines[n] = item.model_copy(update={"source": source}).model_dump_json()
                stamped += 1
        path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8", newline="\n")
    return stamped


def find(item_id: str, data_dir: Path = DATA_DIR) -> tuple[str, Item] | None:
    """The file an item is in (dev, test or incoming), and the item."""
    for name, items in items_by_file(data_dir).items():
        for item in items:
            if item.id == item_id:
                return name, item
    return None


def mark_validated(item_id: str, by: str, on: dt.date, data_dir: Path = DATA_DIR) -> str:
    """Record that a legal reviewer signed the item off: `status` validated, `validated_by`,
    `validated_on`. Only its line changes, and nothing a run reads (`lex.eval.results.SCORED`),
    so no run goes stale. Returns the file it is in."""
    found = find(item_id, data_dir)
    if found is None:
        raise LookupError(f"no item {item_id}")
    if not by.strip():
        raise ValueError("a validation names the person who made it")
    name, _ = found
    path = data_dir / f"{name}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    for n, line in enumerate(lines):
        if line.strip() and Item.model_validate_json(line).id == item_id:
            update = {"status": "validated", "validated_by": by.strip(), "validated_on": on}
            signed = Item.model_validate_json(line).model_copy(update=update)
            lines[n] = Item.model_validate(signed.model_dump()).model_dump_json()
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8", newline="\n")
    return name


def _shared(item: Item) -> set[str]:
    """What an item shares with another, for `cross_split_pairs`: its FAQ entry or other source
    page, and each article it must cite. A page other than a FAQ entry (a guide, a procedure's
    page) holds many questions, so sharing one is listed but links no group."""
    url = str(item.source.url)
    kind = "entry" if "/items(" in url else "page"
    return {f"{kind} {url}"} | {f"article {c.diploma}/{c.article}" for c in item.must_cite}


KINDS = {"entry": "the same FAQ entry", "article": "a must_cite article", "page": "the same page"}


def _kind(keys: set[str]) -> str:
    return " and ".join(KINDS[k] for k in sorted({key.split(" ", 1)[0] for key in keys}))


def cross_split_pairs(data_dir: Path = DATA_DIR) -> list[str]:
    """Every dev item and test item that share a source page or a must_cite article, by id and
    kind of link only, so the list never shows what a test item says or cites. A main article or
    a FAQ entry puts both in one group, so `check` refuses those pairs; the rest (a secondary
    article, a page of many questions) are listed for a person to read on the dev side."""
    dev, test = (_parse(data_dir / f"{name}.jsonl")[0] for name in SPLITS)
    keys = {i.id: _shared(i) for i in dev}
    pairs = []
    for t in test:
        mine = _shared(t)
        for d in dev:
            if common := keys[d.id] & mine:
                pairs.append(f"{d.id} (dev) ~ {t.id} (test): {_kind(common)}")
    return pairs


def summary(data_dir: Path = DATA_DIR) -> str:
    """Item counts per file and type, and how many a legal reviewer has validated."""
    types: tuple[str, ...] = get_args(QuestionType)
    rows = [("", *types, "total", "validated")]
    for name in (*SPLITS, INCOMING):
        items, _ = _parse(data_dir / f"{name}.jsonl")
        counts: Counter[str] = Counter(item.type for item in items)
        validated = sum(item.status == "validated" for item in items)
        rows.append((name, *(str(counts[t]) for t in types), str(len(items)), str(validated)))
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return "\n".join(
        "  ".join(cell.rjust(w) for cell, w in zip(row, widths, strict=True)) for row in rows
    )
