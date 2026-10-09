"""Writes the folder the Vercel demo is deployed from (ADR 0014).

    python vercel/assemble.py [--out build/vercel] [--warm]
    cd build/vercel && npx vercel deploy --prod

The folder holds the FastAPI app (index.py), the lex package, the built web page, the article
versions,
their Gemini Embedding 2 vectors, and the test runs' summaries for the leaderboard. It holds no
benchmark item: bench/ data is never copied, and results/test/ files keep summaries only.
"""

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"  # one folder per diploma, vectors beside
VECTORS = PROCESSED / "vectors-gemini-embedding-2-768.npz"
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc")


def assemble(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.iterdir():  # all but .vercel, which links the folder to its Vercel project
        if old.name != ".vercel":
            shutil.rmtree(old) if old.is_dir() else old.unlink()
    for name in ["index.py", "requirements.txt", ".vercelignore"]:
        shutil.copy(ROOT / "vercel" / name, out / name)
    # The security headers the API sends, for the page's files too, which the CDN serves.
    sys.path.insert(0, str(ROOT / "src"))
    from lex.api.app import SECURITY_HEADERS

    config = json.loads((ROOT / "vercel" / "vercel.json").read_text(encoding="utf-8"))
    headers = [{"key": k, "value": v} for k, v in SECURITY_HEADERS.items()]
    config["headers"] = [{"source": "/(.*)", "headers": headers}]
    (out / "vercel.json").write_text(json.dumps(config, indent=2) + "\n", "utf-8", newline="\n")
    # The Python CI tests, not Vercel's default (3.12): it reads .python-version (ADR 0019).
    shutil.copy(ROOT / ".python-version", out / ".python-version")
    shutil.copytree(ROOT / "src" / "lex", out / "lex", ignore=SKIP)
    # The page is built here, a few seconds of Node, and shipped as static files.
    web = ROOT / "web"
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=web, check=True)
    subprocess.run([npm, "run", "build"], cwd=web, check=True)
    shutil.copytree(web / "dist", out / "web")
    (out / "results").mkdir()
    for run in sorted((ROOT / "results" / "test").glob("*.json")):  # not superseded/
        # The leaderboard reads summaries; the per-item scores (ids only) stay behind.
        record = json.loads(run.read_text(encoding="utf-8"))
        record.pop("items", None)
        text = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        (out / "results" / run.name).write_text(text, encoding="utf-8", newline="\n")
    (out / "data").mkdir()
    # Every diploma's versions in one file, in the order the vectors follow.
    files = sorted(PROCESSED.glob("*/versions.jsonl"))  # as lex.store.memory.corpus_files
    joined = "".join(f.read_text(encoding="utf-8") for f in files)
    (out / "data" / "versions.jsonl").write_text(joined, encoding="utf-8", newline="\n")
    # The demo's only store is this file in memory: what Postgres would refuse is refused here,
    # before a deploy rather than at a visitor's first request.
    sys.path.insert(0, str(ROOT / "src"))
    from lex.store.memory import Corpus

    corpus = Corpus.load(out / "data" / "versions.jsonl")

    # What runs, as /api/health says it: the commit, whether its tree was clean, the corpus.
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    build = {
        "commit": git("rev-parse", "HEAD"),
        "clean": not git("status", "--porcelain"),
        "corpus": corpus.fingerprint(),
        "versions": len(corpus.versions),
        "assembled_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    (out / "data" / "build.json").write_text(json.dumps(build, indent=2) + "\n", "utf-8")
    if not VECTORS.exists():
        raise SystemExit(f"no {VECTORS.name}: run python -m lex.eval retrieval dense-gemini+refs")
    shutil.copy(VECTORS, out / "data" / "vectors.npz")
    print(f"wrote {out}")


def warm(out: Path) -> None:
    """Answer the page's examples once, with the demo's system, so the deployed demo starts with
    them in its cache: an instant first answer, and 4 model calls per deploy instead of 4 per
    cold start. Needs LLM_API_KEY and spends 4 of the day's quota."""
    sys.path.insert(0, str(ROOT / "src"))
    from dotenv import load_dotenv

    from lex.api.__main__ import demo_system
    from lex.store.memory import Corpus, corpus_files

    load_dotenv(ROOT / ".env")
    system = demo_system(Corpus.load(*corpus_files(PROCESSED)), VECTORS, patient=True)
    rows = []
    for example in json.loads((ROOT / "web" / "src" / "examples.json").read_text(encoding="utf-8")):
        as_of = dt.date.fromisoformat(example["asOf"])  # each has its date (Phase 11)
        answer = system.answer(example["question"], as_of)
        rows.append(
            {
                "question": example["question"],
                "as_of": as_of.isoformat(),
                "answer": answer.model_dump(),
            }
        )
        print(
            f"  {as_of} {example['question'][:50]}: {'refused' if answer.refused else 'answered'}"
        )
    (out / "data" / "answers.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="python vercel/assemble.py")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "vercel")
    parser.add_argument("--warm", action="store_true", help="answer the page's examples now")
    args = parser.parse_args()
    assemble(args.out)
    if args.warm:
        warm(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
