"""The public demo as a FastAPI app on Vercel (ADR 0014), which finds `app` in this file.

Built by lex.api.__main__.demo_app, which `python -m lex.api --demo` runs locally, from the
article versions and their Gemini Embedding 2 vectors shipped next to this file. The same code
paths are scored by python -m lex.eval answers --retriever dense-gemini+refs.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lex.api.__main__ import demo_app  # noqa: E402

app = demo_app(
    versions=[ROOT / "data" / "versions.jsonl"],  # every diploma's, joined by assemble.py
    vectors=ROOT / "data" / "vectors.npz",
    results=ROOT / "results",
    static=ROOT / "web",  # the built page; Vercel serves its files from the CDN
    answers=ROOT / "data" / "answers.json",  # the examples, answered at deploy
    build=ROOT / "data" / "build.json",  # the commit and corpus deployed
)
