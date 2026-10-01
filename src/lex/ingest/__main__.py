"""python -m lex.ingest ct | act-faq | spot-check N [--seed S], each with [--offline]"""

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from lex.ingest import act_faq, amendments, dr, pgdl, spot_check
from lex.ingest.build import build
from lex.ingest.fetch import Fetcher, Page
from lex.store import db
from lex.store.models import ArticleVersion

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
DOCS = ROOT / "docs"
OUT = DATA / "processed" / "ct"


def ingest_ct(offline: bool) -> int:
    fetcher = Fetcher(DATA / "raw" / "pgdl", offline=offline)
    dr_text, dr_fetched = dr.cached_render(
        dr.CT_URL, DATA / "raw" / "dr" / "ct.txt", offline=offline
    )
    reference = dr.parse_code(dr_text)

    def fetch(url: str) -> tuple[str, Page]:
        page = fetcher.get(url)
        if fetcher.requests and fetcher.requests % 25 == 0:
            print(f"  {fetcher.requests} requests", flush=True)
        return pgdl.decode(page.body), page

    first, _ = fetch(pgdl.window_url("1047A0001"))
    ids = pgdl.article_ids(first)
    current: dict[str, tuple[pgdl.Article, Page]] = {}
    for article_id in ids:
        if article_id not in current:
            text, page = fetch(pgdl.window_url(article_id))
            for article in pgdl.parse_window(text):
                current.setdefault(article.article_id, (article, page))
    current = {i: current[i] for i in ids if i in current}  # the code's order

    old: dict[tuple[str, int], tuple[pgdl.OldVersion, Page]] = {}
    for article_id, (article, _) in current.items():
        for ref in article.old_versions:
            text, page = fetch(pgdl.old_version_url(article_id, ref.number))
            old[(article_id, ref.number)] = (pgdl.parse_old_version(text), page)

    versions, report = build(current, old, reference, dr_fetched)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "versions.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        f.writelines(v.model_dump_json() + "\n" for v in versions)
    (OUT / "report.json").write_text(
        json.dumps(dataclasses.asdict(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    missing = [i for i in ids if i not in current]
    print(f"PGDL ids {len(ids)}, parsed {len(current)}, missing {len(missing)} {missing[:5]}")
    print(f"DR articles {len(reference)}; network requests this run {fetcher.requests}")
    print(f"articles {report.articles}, versions {report.versions}")
    print(f"problems {len(report.problems)}, dates resolved by rule {len(report.resolved)}")
    print(f"articles with incomplete history {sorted(set(report.incomplete_history))}")
    print(f"articles with no version stored {report.missing_current}")
    print(f"PGDL current texts differing from the DR {len(report.text_mismatches)}")
    print(f"articles with Constitutional Court rulings {len(report.rulings)}")
    print(f"written to {OUT}")
    return 0


def run_spot_check(n: int, seed: int, out: Path, offline: bool) -> int:
    lines = (OUT / "versions.jsonl").read_text(encoding="utf-8").splitlines()
    versions = [ArticleVersion.model_validate_json(line) for line in lines]
    with db.connect() as conn:
        checks, drawn_from = spot_check.run(
            versions, n, seed, DATA / "raw" / "dr", conn, offline=offline
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(spot_check.report(checks, n, seed, drawn_from), encoding="utf-8", newline="\n")
    results = [c.result for c in checks]
    print({r: results.count(r) for r in sorted(set(results))})
    print(f"wrote {out}")
    return 0


def ingest_act_faq(offline: bool) -> int:
    fetcher = Fetcher(DATA / "raw" / "act-faq", offline=offline)
    faqs = act_faq.fetch(fetcher)
    out = DATA / "processed" / "act_faq.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.writelines(
            json.dumps(dataclasses.asdict(q), ensure_ascii=False, default=str) + "\n" for q in faqs
        )
    themes = {q.theme for q in faqs}
    print(f"{len(faqs)} FAQ entries in {len(themes)} themes; network requests {fetcher.requests}")
    print(f"written to {out}")
    return 0


def check_updates() -> int:
    """Exit 1 when the PGDL lists an amendment the corpus was built without."""
    current = amendments.parse(amendments.fetch())
    new = amendments.new_since(current, amendments.known())
    if new:
        print(f"the Código do Trabalho has {len(new)} amendment(s) the corpus lacks: {new}")
        print("rebuild the corpus (python -m lex.ingest ct) and docs/checks/ct-amendments.txt")
        return 1
    print(f"no new amendments: {len(current)} listed, the newest {current[0]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lex.ingest")
    commands = parser.add_subparsers(dest="command", required=True)
    ct = commands.add_parser("ct", help="fetch (or rebuild from cache) the Código do Trabalho")
    ct.add_argument("--offline", action="store_true", help="use the raw cache only")
    faq = commands.add_parser("act-faq", help="fetch the ACT's FAQ, a source of benchmark items")
    faq.add_argument("--offline", action="store_true", help="use the raw cache only")
    sc = commands.add_parser(
        "spot-check", help="compare random earlier versions in the store with the DR's history"
    )
    sc.add_argument("n", type=int)
    sc.add_argument("--seed", type=int, default=2026)
    sc.add_argument("--out", type=Path, default=DOCS / "checks" / "phase1-spot-check.md")
    sc.add_argument("--offline", action="store_true", help="use the raw cache only")
    commands.add_parser("check-updates", help="has the code been amended since the corpus?")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    if args.command == "ct":
        return ingest_ct(args.offline)
    if args.command == "act-faq":
        return ingest_act_faq(args.offline)
    if args.command == "check-updates":
        return check_updates()
    return run_spot_check(args.n, args.seed, args.out, args.offline)


if __name__ == "__main__":
    sys.exit(main())
