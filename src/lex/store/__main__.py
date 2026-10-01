"""python -m lex.store load [--versions FILE] | show ARTICLE [--as-of DATE] [--diploma ID]
python -m lex.store dump-embeddings FILE | load-embeddings FILE

The embedding files let the demo start with every article embedded (ADR 0013).
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from lex.store import db
from lex.store.models import ArticleVersion

ROOT = Path(__file__).resolve().parents[3]
VERSIONS = ROOT / "data" / "processed" / "ct" / "versions.jsonl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lex.store")
    commands = parser.add_subparsers(dest="command", required=True)
    ld = commands.add_parser("load", help=f"replace the store's contents with {VERSIONS.name}")
    ld.add_argument("--versions", type=Path, default=VERSIONS)
    dump = commands.add_parser("dump-embeddings", help="write every embedding to a JSONL file")
    dump.add_argument("file", type=Path)
    restore = commands.add_parser("load-embeddings", help="insert embeddings from a JSONL file")
    restore.add_argument("file", type=Path)
    sh = commands.add_parser("show", help="print an article as in force on a date")
    sh.add_argument("article", help="e.g. 238 or 252-B")
    sh.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.date.today())
    sh.add_argument("--diploma", default="lei-7-2009")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")

    with db.connect() as conn:
        db.create_schema(conn)
        if args.command == "load":
            lines = args.versions.read_text(encoding="utf-8").splitlines()
            count = db.load(conn, map(ArticleVersion.model_validate_json, lines))
            print(f"loaded {count} article versions")
            return 0
        if args.command == "dump-embeddings":
            rows = db.export_embeddings(conn)
            lines = [json.dumps(r) for r in rows]
            args.file.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            print(f"wrote {len(rows)} embeddings to {args.file}")
            return 0
        if args.command == "load-embeddings":
            lines = args.file.read_text(encoding="utf-8").splitlines()
            count = db.import_embeddings(conn, map(json.loads, lines))
            print(f"loaded {count} embeddings")
            return 0
        v = db.article_at(conn, args.diploma, args.article, args.as_of)
    if v is None:
        print(f"no version of article {args.article} in force on {args.as_of}", file=sys.stderr)
        return 1
    number, _, suffix = v.article.partition("-")
    until = v.valid_to.isoformat() if v.valid_to else "in force"
    print(f"Artigo {number}.º{'-' + suffix if suffix else ''} - {v.heading}")
    print(" > ".join(v.path))
    print(f"{v.valid_from} -> {until}, introduced by {v.introduced_by}\n\n{v.text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
