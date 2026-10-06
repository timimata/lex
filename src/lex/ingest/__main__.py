"""python -m lex.ingest ct | code KEY | act-faq | spot-check N [--seed S] [--code KEY], each
with [--offline]"""

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from lex.ingest import act_faq, amendments, dr, pgdl, spot_check
from lex.ingest.build import build
from lex.ingest.codes import CODES, Code
from lex.ingest.fetch import MIN_INTERVAL_S, Fetcher, Page
from lex.store.memory import Corpus

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
DOCS = ROOT / "docs"


def ingest_code(code: Code, offline: bool) -> int:
    """A diploma's articles, every version, from the PGDL, dated and checked against the DR
    (ADR 0005); codes.py says which diploma and which of its articles."""
    out = DATA / "processed" / code.key
    fetcher = Fetcher(DATA / "raw" / "pgdl", offline=offline)
    dr_text, dr_fetched = dr.cached_render(
        code.dr_url, DATA / "raw" / "dr" / f"{code.key}.txt", offline=offline
    )
    parsed = dr.parse_code(dr_text, code.start, code.stop, code.quotes)
    reference = {number: article for number, article in parsed.items() if code.keep(number)}

    def fetch(url: str) -> tuple[str, Page]:
        page = fetcher.get(url)
        if fetcher.requests and fetcher.requests % 25 == 0:
            print(f"  {fetcher.requests} requests", flush=True)
        return pgdl.decode(page.body), page

    own, own_page = fetch(pgdl.diploma_url(code.nid))
    ids = [i for i in pgdl.article_ids(own) if code.keep(pgdl.article_number(i))]
    if not ids:
        print(f"no articles listed on {own_page.url}; is nid {code.nid} right?", file=sys.stderr)
        return 1
    current: dict[str, tuple[pgdl.Article, Page]] = {}
    for article_id in ids:
        if article_id not in current:
            text, page = fetch(pgdl.window_url(article_id, code.nid))
            for article in pgdl.parse_window(text, code.nid):
                if code.keep(pgdl.article_number(article.article_id)):
                    current.setdefault(article.article_id, (article, page))
    # Where the PGDL fails to serve an article's window ('A query falhou!', as for the NRAU's
    # art. 1.º), the article is read from the diploma's own page, if it is there.
    for article in pgdl.parse_window(own, code.nid):
        if article.article_id in ids:
            current.setdefault(article.article_id, (article, own_page))
    current = {i: current[i] for i in ids if i in current}  # the code's order

    old: dict[tuple[str, int], tuple[pgdl.OldVersion, Page]] = {}
    for article_id, (article, _) in current.items():
        for ref in article.old_versions:
            text, page = fetch(pgdl.old_version_url(article_id, ref.number, code.nid))
            old[(article_id, ref.number)] = (pgdl.parse_old_version(text), page)

    versions, report = build(current, old, reference, dr_fetched, code)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "versions.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        f.writelines(v.model_dump_json() + "\n" for v in versions)
    (out / "report.json").write_text(
        json.dumps(dataclasses.asdict(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    missing = [i for i in ids if i not in current]
    print(f"PGDL ids {len(ids)}, parsed {len(current)}, missing {len(missing)} {missing[:5]}")
    print(f"DR articles {len(reference)}; network requests this run {fetcher.requests}")
    print(f"articles {report.articles}, versions {report.versions}")
    print(f"problems {len(report.problems)}, dates resolved by rule {len(report.resolved)}")
    print(f"articles whose PGDL texts were credited as the DR lists {len(report.relabelled)}")
    print(f"articles where the PGDL lacks a change the DR lists {len(report.gaps)}")
    print(f"articles with incomplete history {sorted(set(report.incomplete_history))}")
    print(f"articles with no version stored {report.missing_current}")
    print(f"PGDL current texts differing from the DR {len(report.text_mismatches)}")
    print(f"articles with Constitutional Court rulings {len(report.rulings)}")
    print(f"articles with deferred or suspended effects {sorted(report.remarks)}")
    print(f"written to {out}")
    return 0


def run_spot_check(n: int, seed: int, out: Path | None, code: Code, offline: bool) -> int:
    """The ingestion output against the DR's history view, read in memory (no Postgres)."""
    corpus = Corpus.load(DATA / "processed" / code.key / "versions.jsonl")
    checks, drawn_from = spot_check.run(
        corpus.versions, n, seed, DATA / "raw" / "dr", corpus.article_at, code, offline=offline
    )
    name = "phase1-spot-check.md" if code.key == "ct" else f"{code.key}-spot-check.md"
    out = out or DOCS / "checks" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    report = spot_check.report(checks, n, seed, drawn_from, code)
    out.write_text(report, encoding="utf-8", newline="\n")
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
    """Exit 1 when the PGDL lists, for any diploma of the corpus, an amendment the corpus was
    built without. One request per diploma, MIN_INTERVAL_S apart."""
    outdated = 0
    for n, code in enumerate(CODES.values()):
        if n:
            time.sleep(MIN_INTERVAL_S)
        current = amendments.parse(amendments.fetch(code))
        new = amendments.new_since(current, amendments.known(amendments.known_path(code)))
        if new:
            outdated += 1
            print(f"the {code.name} has {len(new)} amendment(s) the corpus lacks: {new}")
            print(
                f"check which articles they change, rebuild (python -m lex.ingest code "
                f"{code.key}) and update {amendments.known_path(code).name}"
            )
        else:
            print(f"{code.name}: no new amendments, {len(current)} listed, newest {current[0]}")
    return 1 if outdated else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lex.ingest")
    commands = parser.add_subparsers(dest="command", required=True)
    ct = commands.add_parser("ct", help="fetch (or rebuild from cache) the Código do Trabalho")
    ct.add_argument("--offline", action="store_true", help="use the raw cache only")
    one = commands.add_parser("code", help="fetch (or rebuild from cache) a diploma of codes.py")
    one.add_argument("key", choices=sorted(CODES))
    one.add_argument("--offline", action="store_true", help="use the raw cache only")
    faq = commands.add_parser("act-faq", help="fetch the ACT's FAQ, a source of benchmark items")
    faq.add_argument("--offline", action="store_true", help="use the raw cache only")
    sc = commands.add_parser(
        "spot-check", help="compare random earlier versions in the store with the DR's history"
    )
    sc.add_argument("n", type=int)
    sc.add_argument("--seed", type=int, default=2026)
    sc.add_argument("--code", choices=sorted(CODES), default="ct")
    sc.add_argument("--out", type=Path, help="default docs/checks/<code>-spot-check.md")
    sc.add_argument("--offline", action="store_true", help="use the raw cache only")
    commands.add_parser("check-updates", help="has a diploma been amended since the corpus?")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    if args.command == "ct":
        return ingest_code(CODES["ct"], args.offline)
    if args.command == "code":
        return ingest_code(CODES[args.key], args.offline)
    if args.command == "act-faq":
        return ingest_act_faq(args.offline)
    if args.command == "check-updates":
        return check_updates()
    return run_spot_check(args.n, args.seed, args.out, CODES[args.code], args.offline)


if __name__ == "__main__":
    sys.exit(main())
