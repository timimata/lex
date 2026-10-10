"""The dataset card's counts, written from the benchmark files so none is typed by hand.

`python -m lex.bench card` rewrites the block between the markers in bench/DATASET_CARD.md;
`validate` fails when the block is not what the files give. Counts only: nothing here reads or
shows what an item says.
"""

import json
from collections import Counter
from pathlib import Path
from typing import get_args

from lex.bench.schema import Item, QuestionType
from lex.bench.splits import DATA_DIR, items_by_file

CARD = Path(__file__).resolve().parents[3] / "bench" / "DATASET_CARD.md"
START = "<!-- counts: written by python -m lex.bench card; edit the code, not this block -->"
END = "<!-- /counts -->"
WHAT = {
    "simple": "One fact, one or two articles",
    "composite": "Several articles combined",
    "temporal": "`as_of` in the past; the answer depends on the law in force that day",
    "explicit_reference": "The question names its article",
    "unanswerable": "Outside the corpus; the right response is to say so",
}


FAQ = Path(__file__).resolve().parents[3] / "data" / "processed" / "act_faq.jsonl"
# The one line that needs the ACT's FAQ itself, which CI does not have: it is left out of the
# comparison there (`is_current`).
VERBATIM = "Of the dev items drawn from the ACT's FAQ"


def _verbatim(dev: list[Item], faq: Path) -> tuple[int, int] | None:
    """How many dev items come from the FAQ, and how many keep its question word for word."""
    if not faq.exists():
        return None
    entries = [json.loads(line) for line in faq.read_text(encoding="utf-8").splitlines() if line]
    asked = {e["url"]: " ".join(e["question"].casefold().split()) for e in entries}
    drawn = [i for i in dev if str(i.source.url) in asked]
    same = sum(" ".join(i.question.casefold().split()) == asked[str(i.source.url)] for i in drawn)
    return len(drawn), same


def block(data_dir: Path = DATA_DIR, faq: Path = FAQ) -> str:
    files = items_by_file(data_dir)
    dev, test = files["dev"], files["test"]
    act = sum("act.gov.pt" in str(i.source.url) for i in dev)
    verbatim = _verbatim(dev, faq)
    types: Counter[str] = Counter(i.type for i in dev)
    tenancy = sum(i.id.startswith("ar-") for i in dev)
    rows = [f"| `{t}` | {WHAT[t]} | {types[t]} |" for t in get_args(QuestionType)]
    validated = {
        name: sum(i.status == "validated" for i in files[name]) for name in ("dev", "test")
    }
    return "\n".join(
        [
            START,
            f"Dev has {len(dev)} items, {tenancy} of them on tenancy; test has {len(test)}.",
            "",
            "| Type | What it tests | Dev items |",
            "|---|---|---|",
            *rows,
            "",
            f"Validated by a legal reviewer (`status`, `validated_by`): {validated['dev']} of the "
            f"{len(dev)} dev items and {validated['test']} of the {len(test)} test items.",
            "",
            f"From the ACT's portal: {act} of the {len(dev)} dev items.",
            *(
                [
                    f"{VERBATIM}, {verbatim[0]}, {verbatim[1]} keep its question word for word "
                    "(see Contamination)."
                ]
                if verbatim
                else []
            ),
            END,
        ]
    )


def _split(text: str) -> tuple[str, str, str] | None:
    start, end = text.find(START), text.find(END)
    if start < 0 or end < start:
        return None
    return text[:start], text[start : end + len(END)], text[end + len(END) :]


# The lines that count test items, which the public mirror cannot recount: it has no test
# split (ADR 0016), so there they are left out of the comparison, as `VERBATIM` is without the
# FAQ. The private repository's CI, which has both, checks every line.
TEST_LINES = ("Dev has ", "Validated by a legal reviewer")


def is_current(path: Path = CARD, data_dir: Path = DATA_DIR, faq: Path = FAQ) -> bool:
    """Whether the card's block is what the files give, leaving out the lines that need a file
    this checkout lacks: the FAQ (CI) or the test split (the public mirror)."""
    parts = _split(path.read_text(encoding="utf-8"))
    if parts is None:
        return False
    unknown = (() if faq.exists() else (VERBATIM,)) + (
        () if (data_dir / "test.jsonl").exists() else TEST_LINES
    )

    def without(text: str) -> list[str]:
        return [line for line in text.splitlines() if not line.startswith(unknown)]

    return without(parts[1]) == without(block(data_dir, faq))


def refresh(path: Path = CARD, data_dir: Path = DATA_DIR, faq: Path = FAQ) -> None:
    parts = _split(path.read_text(encoding="utf-8"))
    if parts is None:
        raise ValueError(f"{path.name} has no counts block ({START})")
    before, _, after = parts
    path.write_text(before + block(data_dir, faq) + after, encoding="utf-8", newline="\n")
