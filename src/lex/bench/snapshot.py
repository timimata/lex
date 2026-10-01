"""The public mirror (ADR 0016): every tracked file but the test split, refused if any file still
holds a test item's question or answer, or a string shaped like an API key.

Problems name the file only, never what was found, so running this never shows a test item.
"""

import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from lex.bench.schema import Item
from lex.bench.splits import DATA_DIR, _normalise, _parse

TEST = "bench/data/test.jsonl"
# Google (AIza..., AQ....), Hugging Face, OpenAI-style and GitHub tokens.
KEY = re.compile(
    r"AIza[0-9A-Za-z_-]{30,}|AQ\.[0-9A-Za-z_-]{20,}|hf_[0-9A-Za-z]{20,}|sk-[0-9A-Za-z]{20,}"
    r"|ghp_[0-9A-Za-z]{20,}"
)
BINARY = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".npz", ".woff", ".woff2", ".pdf")


def find_leaks(texts: Mapping[str, str], items: Sequence[Item]) -> list[str]:
    """The files, among `texts` (path -> content), that hold a test item's question or the start of
    its answer, or something shaped like a key."""
    needles = [_normalise(i.question) for i in items]
    needles += [_normalise(i.answer)[:120] for i in items]
    problems = []
    for path, text in texts.items():
        if KEY.search(text):
            problems.append(f"{path} holds a string shaped like an API key")
        normal = _normalise(text)
        if any(n and n in normal for n in needles):
            problems.append(f"{path} holds test content")
    return problems


def tracked(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line and line != TEST]


def snapshot(root: Path, out: Path, data_dir: Path = DATA_DIR) -> list[str]:
    """Copy every tracked file but the test split into `out` (its .git, if any, is kept, so it can
    be the public repository's clone). Nothing is written if a file leaks."""
    files = tracked(root)
    texts = {}
    for path in files:
        if not path.lower().endswith(BINARY):
            texts[path] = (root / path).read_bytes().decode("utf-8", errors="replace")
    items, _ = _parse(data_dir / "test.jsonl")
    problems = find_leaks(texts, items)
    if problems:
        return problems
    out.mkdir(parents=True, exist_ok=True)
    for old in out.iterdir():
        if old.name != ".git":
            shutil.rmtree(old) if old.is_dir() else old.unlink()
    for path in files:
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / path, target)
    return []


ADR = "../docs/decisions/0016-licences-and-hidden-test.md"
ADR_ONLINE = (
    "https://github.com/timimata/lex/blob/main/docs/decisions/0016-licences-and-hidden-test.md"
)


def dataset(public: Path, out: Path) -> None:
    """The Hugging Face dataset's folder, from a snapshot: the card as README.md, the dev split
    and the licence, whose link to ADR 0016 points at the public repository."""
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)
    shutil.copy2(public / "bench" / "DATASET_CARD.md", out / "README.md")
    shutil.copy2(public / "bench" / "data" / "dev.jsonl", out / "data" / "dev.jsonl")
    licence = (public / "bench" / "LICENSE.md").read_text(encoding="utf-8")
    (out / "LICENSE.md").write_text(licence.replace(ADR, ADR_ONLINE), encoding="utf-8")
