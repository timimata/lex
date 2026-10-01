"""python -m lex.bench validate | assign | snapshot [--out DIR]"""

import argparse
import sys
from pathlib import Path

from lex.bench.corpus_check import check_citations, load_periods
from lex.bench.snapshot import snapshot
from lex.bench.splits import DATA_DIR, assign, check, items_by_file, summary

ROOT = Path(__file__).resolve().parents[3]
VERSIONS = ROOT / "data" / "processed" / "ct" / "versions.jsonl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lex.bench")
    parser.add_argument("command", choices=["validate", "assign", "snapshot"])
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--versions", type=Path, default=VERSIONS, help="the ingested corpus")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "public", help="snapshot")
    args = parser.parse_args(argv)

    problems = check(args.data_dir)
    if args.versions.exists():
        problems += check_citations(items_by_file(args.data_dir), load_periods(args.versions))
    else:
        print(f"no corpus at {args.versions}: citations not checked against it\n")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    if args.command == "snapshot":  # the public mirror (ADR 0016)
        leaks = snapshot(ROOT, args.out, args.data_dir)
        if leaks:
            print("\n".join(leaks), file=sys.stderr)
            return 1
        print(f"wrote the public snapshot to {args.out}: every tracked file but the test split")
        return 0
    if args.command == "assign":
        moved = assign(args.data_dir)
        print(f"moved {moved['dev']} to dev, {moved['test']} to test\n")
    print(summary(args.data_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
