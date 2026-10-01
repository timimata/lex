"""Writes the folder a Hugging Face Docker Space is built from (ADR 0013), and uploads it.

    python space/assemble.py [--out build/space] [--upload USER/SPACE]

The folder holds the code, the web page's source, the article versions and their embeddings (from
the running store), and the test runs' summaries for the leaderboard. It holds no benchmark item:
bench/ is never copied, and results/test/ files keep summaries only.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lex.store import db  # noqa: E402

VERSIONS = ROOT / "data" / "processed" / "ct" / "versions.jsonl"
WEB = ["package.json", "package-lock.json", "index.html", "tsconfig.json", "vite.config.ts", "src"]
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "dist")


def assemble(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in ["Dockerfile", "start.sh", "README.md"]:
        shutil.copy(ROOT / "space" / name, out / name)
    shutil.copy(ROOT / "pyproject.toml", out / "pyproject.toml")
    shutil.copytree(ROOT / "src", out / "src", ignore=SKIP)
    for name in WEB:
        source = ROOT / "web" / name
        if source.is_dir():
            shutil.copytree(source, out / "web" / name, ignore=SKIP)
        else:
            (out / "web").mkdir(exist_ok=True)
            shutil.copy(source, out / "web" / name)
    (out / "results").mkdir()
    for run in sorted((ROOT / "results" / "test").glob("*.json")):  # not superseded/
        assert "items" not in json.loads(run.read_text(encoding="utf-8")), run
        shutil.copy(run, out / "results" / run.name)
    (out / "data").mkdir()
    shutil.copy(VERSIONS, out / "data" / "versions.jsonl")
    with db.connect() as conn:
        rows = db.export_embeddings(conn)
    versions = len(VERSIONS.read_text(encoding="utf-8").splitlines())
    if len(rows) != versions:
        raise SystemExit(f"{len(rows)} embeddings for {versions} versions: run an eval first")
    (out / "data" / "embeddings.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8", newline="\n"
    )
    print(f"wrote {out}: {versions} versions and their embeddings")


def main() -> int:
    parser = argparse.ArgumentParser(prog="python space/assemble.py")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "space")
    parser.add_argument("--upload", metavar="USER/SPACE", help="push the folder to this Space")
    args = parser.parse_args()
    assemble(args.out)
    if args.upload:
        from huggingface_hub import HfApi

        api = HfApi()
        api.create_repo(args.upload, repo_type="space", space_sdk="docker", exist_ok=True)
        api.upload_folder(repo_id=args.upload, repo_type="space", folder_path=args.out)
        print(f"uploaded to https://huggingface.co/spaces/{args.upload}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
