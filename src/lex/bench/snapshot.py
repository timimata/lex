"""The public mirror (ADR 0016): every tracked file but the test split, refused if any file still
holds a test item's question or answer, verbatim or in part, a test item's id beside an article
it must cite, or a string shaped like an API key.

Problems name the file only, never what was found, so running this never shows a test item.
"""

import json
import re
import shutil
import subprocess
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path

from lex.bench.schema import Item
from lex.bench.splits import DATA_DIR, _normalise, _parse
from lex.domain import DIPLOMAS

TEST = "bench/data/test.jsonl"
# Google (AIza..., AQ....), Hugging Face, OpenAI-style and GitHub tokens.
KEY = re.compile(
    r"AIza[0-9A-Za-z_-]{30,}|AQ\.[0-9A-Za-z_-]{20,}|hf_[0-9A-Za-z]{20,}|sk-[0-9A-Za-z]{20,}"
    r"|ghp_[0-9A-Za-z]{20,}"
)
BINARY = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".npz", ".woff", ".woff2", ".pdf")


SHINGLE = 6  # words in a row: a reworded sentence keeps runs this long of its source
# The runs of a test question or answer that nothing public holds (the law, dev) tell it apart:
# a file holding at least this share of them, and two at least, holds part of it. Reworded
# copies built in tests/ hold all of theirs; on 2026-10-08 the tracked files that share runs
# with a test item by chance (model answers to dev questions, a dev item's source quoted in a
# review sheet: legal phrasing) held a third of one item's runs at most.
TELLING_SHARE = 0.5
TELLING_MIN = 2
NEAR = 200  # characters between a test id and one of its articles, read as one note


def _words(text: str) -> list[str]:
    plain = unicodedata.normalize("NFD", text.casefold())
    return re.findall(r"\w+", "".join(c for c in plain if not unicodedata.combining(c)))


def _shingles(text: str) -> set[int]:
    """Every run of SHINGLE words, hashed: the law's runs number in the hundreds of thousands."""
    words = _words(text)
    return {hash(tuple(words[i : i + SHINGLE])) for i in range(len(words) - SHINGLE + 1)}


def _article_pattern(item: Item) -> re.Pattern[str] | None:
    """The ways a note names one of the item's must_cite articles: "art. 238.º", "artigo 238",
    "238.º-A", "CT 238", "lei-7-2009/238"."""
    forms = []
    for c in item.must_cite:
        number, _, suffix = c.article.partition("-")
        # After the number: "-A" for 238-A, written "238.º-A" or "238-A"; for 238, neither more
        # digits nor a letter after it, so "2380" and "238.º-A" are other articles.
        lettered = rf"(?:\.?º)?\s*-\s*{suffix}\b"
        tail = lettered if suffix else r"(?!\d)(?!(?:\.?º)?\s*-\s*[A-Z]\b)"
        short = DIPLOMAS[c.diploma].short if c.diploma in DIPLOMAS else None
        forms.append(rf"\bart(?:igo|\.)?\s*{number}{tail}")
        forms.append(rf"\b{number}\.º{tail}" if not suffix else rf"\b{number}{tail}")
        forms.append(rf"{re.escape(c.diploma)}/{re.escape(c.article)}\b")
        if short:
            forms.append(rf"\b{short}\s+{number}{tail}")
    return re.compile("|".join(forms), re.IGNORECASE) if forms else None


def find_leaks(
    texts: Mapping[str, str], items: Sequence[Item], public: Sequence[str] = ()
) -> list[str]:
    """The files, among `texts` (path -> content), that hold a test item's question or answer,
    whole or in part (runs of words found in none of the `public` texts: the law, the dev
    split), a test item's id within a few lines of an article it must cite, or something
    shaped like a key."""
    needles = [_normalise(i.question) for i in items]
    needles += [_normalise(i.answer)[:120] for i in items]
    known: set[int] = set().union(*(_shingles(text) for text in public))
    telling = [_shingles(text) - known for i in items for text in (i.question, i.answer)]
    ids = [(i.id, _article_pattern(i)) for i in items]
    problems = []
    for path, text in texts.items():
        if KEY.search(text):
            problems.append(f"{path} holds a string shaped like an API key")
        normal = _normalise(text)
        runs = _shingles(text)
        if any(n and n in normal for n in needles) or any(
            len(t & runs) >= max(min(TELLING_MIN, len(t)), TELLING_SHARE * len(t))
            for t in telling
            if t
        ):
            problems.append(f"{path} holds test content")
        elif any(
            article is not None
            and any(
                article.search(text, max(0, m.start() - NEAR), m.end() + NEAR)
                for m in re.finditer(rf"\b{re.escape(item_id)}\b", text)
            )
            for item_id, article in ids
        ):
            problems.append(f"{path} holds a test id beside an article it must cite")
    return problems


def public_texts(data_dir: Path, corpus: Path) -> list[str]:
    """What is public already, so a test item sharing it gives nothing away: every dev item's
    text, and every article version of the corpus where it has been ingested (the law a
    reference answer quotes). Without the corpus, quoted law counts as test content: the scan
    errs on refusing."""
    texts = [
        "\n".join([i.question, i.answer, i.notes, i.source.title])
        for i in _parse(data_dir / "dev.jsonl")[0]
    ]
    for path in sorted(corpus.glob("*/versions.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                version = json.loads(line)
                texts.append(f"{version['heading']}\n{version['text']}")
    return texts


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
    problems = find_leaks(texts, items, public_texts(data_dir, root / "data" / "processed"))
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
