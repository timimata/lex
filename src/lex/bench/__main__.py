"""python -m lex.bench validate | assign | index | card | stamp | snapshot [--out DIR]
python -m lex.bench review ID --by NAME   (a legal reviewer, never a model)
"""

import argparse
import datetime as dt
import gzip
import json
import sys
from pathlib import Path

from lex.bench import card
from lex.bench.corpus_check import (
    INDEX,
    TEXT,
    check_citations,
    index_lines,
    joined_text,
    load_periods,
    refusals_to_review,
)
from lex.bench.snapshot import dataset, snapshot
from lex.bench.splits import (
    DATA_DIR,
    assign,
    check,
    cross_split_pairs,
    find,
    items_by_file,
    mark_validated,
    stamp,
    summary,
)
from lex.domain import Citation

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "data" / "processed"  # one folder per diploma, each with its versions.jsonl


def _cites(citations: list[Citation]) -> str:
    return ", ".join(f"{c.diploma}/{c.article}" for c in citations) or "-"


def review(item_id: str, by: str, data_dir: Path, card_path: Path) -> int:
    """A legal reviewer's sign-off on one item, asked in the terminal: the item is shown here and
    nowhere else, so a test item's content leaves no copy. A person runs this, never a model
    (CLAUDE.md); a correction is an edit of its own, one commit per fix (bench/README.md)."""
    found = find(item_id, data_dir)
    if found is None:
        print(f"no item {item_id}", file=sys.stderr)
        return 1
    name, item = found
    print(f"{item.id} · {name} · {item.type} · lei em vigor a {item.as_of:%d/%m/%Y}")
    print(f"Pergunta: {item.question}\nResposta: {item.answer}")
    print(f"Tem de citar: {_cites(item.must_cite)} · pode citar: {_cites(item.may_cite)}")
    print(f"Fonte: {item.source.url}\nNotas: {item.notes or '-'}")
    if item.status == "validated":
        print(f"(já validado por {item.validated_by} a {item.validated_on})")
    if input(f"Valida este item, como {by}? [s/n] > ").strip().lower() != "s":
        return 0
    mark_validated(item_id, by, dt.date.today(), data_dir)
    card.refresh(card_path, data_dir)
    print(f"{item_id} validado por {by}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lex.bench")
    commands = ["validate", "assign", "index", "card", "stamp", "review", "snapshot"]
    parser.add_argument("command", choices=commands)
    parser.add_argument("item", nargs="?", help="review: the item's id")
    parser.add_argument("--by", help="review: the legal reviewer's name")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--corpus", type=Path, default=CORPUS, help="the ingested corpus")
    parser.add_argument("--index", type=Path, default=INDEX, help="the corpus's committed index")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "public", help="snapshot")
    parser.add_argument("--dataset", type=Path, default=ROOT / "build" / "hf", help="HF dataset")
    parser.add_argument("--card", type=Path, default=card.CARD, help="the dataset card")
    args = parser.parse_args(argv)

    if args.command == "stamp":  # each ACT FAQ item's entry date (ADR 0008)
        faq = args.corpus / "act_faq.jsonl"
        if not faq.exists():
            print(f"no {faq}: python -m lex.ingest act-faq first", file=sys.stderr)
            return 1
        rows = [json.loads(line) for line in faq.read_text(encoding="utf-8").splitlines() if line]
        dates = {row["url"]: dt.date.fromisoformat(row["modified"]) for row in rows}
        print(f"stamped {stamp(dates, args.data_dir)} item(s) with their FAQ entry's date")
        card.refresh(args.card, args.data_dir, faq)
        return 0
    if args.command == "review":
        if not args.item or not args.by:
            parser.error("review needs an item id and --by NAME")
        return review(args.item, args.by, args.data_dir, args.card)

    versions = sorted(args.corpus.glob("*/versions.jsonl"))
    if args.command == "index":  # after an ingestion: what CI checks citations against
        if not versions:
            print(f"no corpus in {args.corpus} to index", file=sys.stderr)
            return 1
        lines = index_lines(versions)
        args.index.parent.mkdir(parents=True, exist_ok=True)
        args.index.write_text("".join(f"{line}\n" for line in lines), "utf-8", newline="\n")
        args.index.with_name(TEXT.name).write_bytes(joined_text(versions))
        print(f"wrote {len(lines)} article versions to {args.index}, and their text beside it")
        return 0
    problems = check(args.data_dir)
    items = items_by_file(args.data_dir)
    if versions:
        problems += check_citations(items, load_periods(versions))
        indexed = args.index.read_text("utf-8").splitlines() if args.index.exists() else []
        text = args.index.with_name(TEXT.name)
        same_text = text.exists() and gzip.decompress(text.read_bytes()) == gzip.decompress(
            joined_text(versions)
        )
        if indexed != index_lines(versions) or not same_text:
            problems.append(f"{args.index.name} is not the corpus's: python -m lex.bench index")
    elif args.index.exists():
        problems += check_citations(items, load_periods([args.index]))
        print(f"no corpus in {args.corpus}: citations checked against {args.index.name}\n")
    else:
        print(f"no corpus in {args.corpus} and no index: citations not checked\n")
    rewrites_card = args.command in ("card", "assign")
    faq = args.corpus / "act_faq.jsonl"
    if not rewrites_card and not card.is_current(args.card, args.data_dir, faq):
        problems.append(f"{args.card.name}'s counts are out of date: python -m lex.bench card")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    if to_review := refusals_to_review(items):
        print(
            f"{len(to_review)} unanswerable item(s) speak of tenancy, which the corpus now holds;"
            f" a person should check that refusing is still right: {', '.join(to_review)}\n"
        )
    if pairs := cross_split_pairs(args.data_dir):
        print(f"{len(pairs)} dev and test item pair(s) share a page or a must_cite article:")
        print("\n".join(f"  {pair}" for pair in pairs) + "\n")
    if args.command == "snapshot":  # the public mirror (ADR 0016)
        leaks = snapshot(ROOT, args.out, args.data_dir)
        if leaks:
            print("\n".join(leaks), file=sys.stderr)
            return 1
        dataset(args.out, args.dataset)
        print(f"wrote the public snapshot to {args.out}: every tracked file but the test split")
        print(
            f"and the Hugging Face dataset's folder to {args.dataset}: the card, dev, the licence"
        )
        return 0
    if args.command == "assign":
        moved = assign(args.data_dir)
        print(f"moved {moved['dev']} to dev, {moved['test']} to test\n")
    if rewrites_card:
        card.refresh(args.card, args.data_dir, faq)
        print(f"wrote the counts in {args.card.name}\n")
    print(summary(args.data_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
