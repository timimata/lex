"""python -m lex.bench validate | assign | snapshot [--out DIR]"""

import argparse
import sys
from pathlib import Path

from lex.bench.corpus_check import check_citations, load_periods, refusals_to_review
from lex.bench.snapshot import dataset, snapshot
from lex.bench.splits import DATA_DIR, assign, check, items_by_file, summary

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "data" / "processed"  # one folder per diploma, each with its versions.jsonl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lex.bench")
    parser.add_argument("command", choices=["validate", "assign", "snapshot"])
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--corpus", type=Path, default=CORPUS, help="the ingested corpus")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "public", help="snapshot")
    parser.add_argument("--dataset", type=Path, default=ROOT / "build" / "hf", help="HF dataset")
    args = parser.parse_args(argv)

    problems = check(args.data_dir)
    items = items_by_file(args.data_dir)
    versions = sorted(args.corpus.glob("*/versions.jsonl"))
    if versions:
        problems += check_citations(items, load_periods(versions))
    else:
        print(f"no corpus in {args.corpus}: citations not checked against it\n")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    if review := refusals_to_review(items):
        print(
            f"{len(review)} unanswerable item(s) speak of tenancy, which the corpus now holds;"
            f" a person should check that refusing is still right: {', '.join(review)}\n"
        )
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
    print(summary(args.data_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
