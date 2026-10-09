"""python -m lex.api [--demo] [--host 127.0.0.1] [--port 8000] [--static DIR]

Serves the reference system (BGE-M3 dense retrieval on Postgres, reranked, with the reference
parser: ADRs 0004, 0007, 0010), or with --demo the public demo's system (ADR 0014): Gemini
Embedding 2 over the corpus in memory, with the reference parser. Both answer with the model
`.env` names (ADR 0011). The leaderboard is read from results/test/.

demo_app() builds the demo; vercel/index.py calls it too, so what runs here is what is deployed.
"""

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI

from lex.api.app import Limits, create_app, leaderboard
from lex.domain import Answer, Citation
from lex.generation import llm
from lex.generation.agent import AgentSystem
from lex.generation.answer import ReferenceSystem
from lex.retrieval.dense import ApiEmbedder, BgeM3, Dense, embed_missing
from lex.retrieval.memory import DenseInMemory, Vectors
from lex.retrieval.references import WithReferences
from lex.retrieval.rerank import BgeReranker, Reranked
from lex.store import db
from lex.store.memory import Corpus, corpus_files
from lex.store.models import ArticleVersion

ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"  # one folder per diploma, vectors beside


def limits() -> Limits:
    return Limits(
        per_visitor_per_hour=int(os.environ.get("LEX_ANSWERS_PER_VISITOR_PER_HOUR", 20)),
        # Gemini's free tier embeds 1000 texts a day per account: the demo stays under it.
        per_day=int(os.environ.get("LEX_ANSWERS_PER_DAY", 400)),
    )


def demo_system(
    corpus: Corpus, vectors: Path, patient: bool = False
) -> ReferenceSystem | AgentSystem:
    """The demo's system (ADR 0014). It never waits on a rate limit or a slow request: past the
    quota, or after the timeouts below (which fit Vercel's 30 s), the page says to try later. An
    overloaded model, which answers at once that it is, is asked twice more within 3 s.
    It answers as the agent (ADR 0018), its prompt as measured (three requests), but no request
    followed after 9 s, so that one more call (18 s at most) still fits; LEX_ANSWER_FORMAT=claims
    brings back the per-sentence answer. `patient` is for answering the examples at deploy, with
    no visitor waiting: the same answers, but slow or overloaded calls are waited out."""
    key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("LLM_API_KEY", "")
    embedder = ApiEmbedder(api_key=key, waits=(), timeout=8, max_retries=0)
    retriever = WithReferences(
        DenseInMemory(corpus, embedder, Vectors.load(vectors)), corpus.article_at
    )
    model = (
        llm.from_env(timeout=120, overload_waits=llm.OVERLOAD_WAITS)
        if patient
        else llm.from_env(
            waits=(),
            timeout=18,
            max_retries=0,
            overload_waits=(1, 2),
            quick_failure=llm.QUICK_FAILURE,
        )
    )
    format = os.environ.get("LEX_ANSWER_FORMAT", "agent")  # ADR 0018, amended 2026-10-07

    def article_at(c: Citation, day: dt.date) -> ArticleVersion | None:
        return corpus.article_at(c.diploma, c.article, day)

    if format == "agent":
        budget = None if patient else 9.0
        return AgentSystem(retriever, article_at, model, budget=budget)  # the prompt measured
    return ReferenceSystem(retriever, article_at, model, format=format)


def answer_row(question: str, as_of: dt.date, answer: Answer) -> dict[str, Any]:
    """An answer made at deploy, as `load_answers` reads it back: JSON, dates as text, and no
    refusal's own reason, which a visitor never sees (ROADMAP 11.7)."""
    return {
        "question": question,
        "as_of": as_of.isoformat(),
        "answer": answer.model_copy(update={"reason": ""}).model_dump(mode="json"),
    }


def load_answers(path: Path | None) -> dict[tuple[str, dt.date], Answer]:
    """Answers made at deploy (vercel/assemble.py --warm), keyed by question and date."""
    if path is None or not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {
        (r["question"], dt.date.fromisoformat(r["as_of"])): Answer.model_validate(r["answer"])
        for r in rows
    }


def demo_app(
    versions: list[Path],
    vectors: Path,
    results: Path,
    static: Path | None,
    answers: Path | None = None,
    build: Path | None = None,
) -> FastAPI:
    """The public demo: the demo's system, the article library and search, the leaderboard;
    `build` names what was deployed (vercel/assemble.py writes it)."""
    corpus = Corpus.load(*versions)
    deployed = json.loads(build.read_text(encoding="utf-8")) if build and build.exists() else None
    return create_app(
        demo_system(corpus, vectors),
        library=corpus.versions_of,
        find=corpus.search_words,
        changes=corpus.changes,
        leaderboard=leaderboard(results),
        limits=limits(),
        static=static,
        preload=load_answers(answers),
        serial=False,  # nothing in it is shared unsafely between threads
        # Vercel sets VERCEL=1 in its functions, and the visitor's address in x-real-ip.
        behind_proxy=os.environ.get("VERCEL") == "1",
        build=deployed,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lex.api")
    parser.add_argument("--demo", action="store_true", help="the deployed demo's system")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--static", type=Path, help="the built web page, served from /")
    parser.add_argument("--results", type=Path, default=ROOT / "results" / "test")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")

    import uvicorn  # the optional `api` extra

    if args.demo:
        vectors = PROCESSED / "vectors-gemini-embedding-2-768.npz"
        app = demo_app(corpus_files(PROCESSED), vectors, args.results, args.static)
        uvicorn.run(app, host=args.host, port=args.port)
        return 0
    with db.connect() as conn:
        conn.autocommit = True  # no transaction left open between requests
        embedder = BgeM3()
        embed_missing(conn, embedder)
        ranked = Reranked(Dense(conn, embedder), BgeReranker(), conn)
        system = ReferenceSystem(
            WithReferences(ranked, lambda d, a, day: db.article_at(conn, d, a, day)),
            lambda c, as_of: db.article_at(conn, c.diploma, c.article, as_of),
            llm.from_env(),
        )
        app = create_app(
            system,
            library=lambda diploma, article: db.versions_of(conn, diploma, article),
            find=Corpus.load(*corpus_files(PROCESSED)).search_words,
            leaderboard=leaderboard(args.results),
            limits=limits(),
            static=args.static,
        )
        uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
