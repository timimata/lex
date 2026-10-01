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
CORPUS = ROOT / "data" / "processed" / "ct"
VECTORS = CORPUS / "vectors-gemini-embedding-2-768.npz"
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc")


def assemble(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.iterdir():  # all but .vercel, which links the folder to its Vercel project
        if old.name != ".vercel":
            shutil.rmtree(old) if old.is_dir() else old.unlink()
    for name in ["index.py", "vercel.json", "requirements.txt", ".vercelignore"]:
        shutil.copy(ROOT / "vercel" / name, out / name)
    shutil.copytree(ROOT / "src" / "lex", out / "lex", ignore=SKIP)
    # The page is built here, a few seconds of Node, and shipped as static files.
    web = ROOT / "web"
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=web, check=True)
    subprocess.run([npm, "run", "build"], cwd=web, check=True)
    shutil.copytree(web / "dist", out / "web")
    (out / "results").mkdir()
    for run in sorted((ROOT / "results" / "test").glob("*.json")):  # not superseded/
        assert "items" not in json.loads(run.read_text(encoding="utf-8")), run
        shutil.copy(run, out / "results" / run.name)
    (out / "data").mkdir()
    shutil.copy(CORPUS / "versions.jsonl", out / "data" / "versions.jsonl")
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
    from lex.api.app import lisbon_today
    from lex.store.memory import Corpus

    load_dotenv(ROOT / ".env")
    system = demo_system(Corpus.load(CORPUS / "versions.jsonl"), VECTORS)
    today = lisbon_today()
    rows = []
    for example in json.loads((ROOT / "web" / "src" / "examples.json").read_text(encoding="utf-8")):
        as_of = dt.date.fromisoformat(example["asOf"]) if example.get("asOf") else today
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
