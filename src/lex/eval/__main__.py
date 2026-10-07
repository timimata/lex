"""python -m lex.eval retrieval RETRIEVER [--split dev|test]
python -m lex.eval answers [--retriever RETRIEVER] [--k K] [--split dev|test]

This module is where systems are built and handed to the harness; the harness itself only knows
the protocols in lex.domain. Retrievers run on the Postgres store, or on the corpus in memory
(the serverless demo's, ADR 0014); Postgres is connected to only when a retriever needs it.
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import psycopg
from dotenv import load_dotenv

from lex.bench.splits import load
from lex.domain import Citation, Retriever
from lex.eval import judge, results
from lex.eval.check import check_results
from lex.eval.harness import KS, run_answers, run_retrieval, summarise, summarise_answers
from lex.generation import llm
from lex.generation.agent import AgentSystem
from lex.generation.answer import FORMATS, K, ReferenceSystem
from lex.retrieval import cache
from lex.retrieval.bm25 import Bm25
from lex.retrieval.crossrefs import PER_ARTICLE, TOP, WithCrossReferences
from lex.retrieval.decompose import Decomposed
from lex.retrieval.dense import (
    GEMINI_DOCUMENT,
    PLAIN_DOCUMENT,
    ApiEmbedder,
    BgeM3,
    Dense,
    embed_missing,
)
from lex.retrieval.hybrid import Hybrid
from lex.retrieval.memory import DenseInMemory, embed_corpus
from lex.retrieval.references import WithReferences
from lex.retrieval.rerank import BgeReranker, Reranked
from lex.store import db
from lex.store.memory import Corpus, corpus_files
from lex.store.models import ArticleAt, ArticleVersion

PROCESSED = results.ROOT / "data" / "processed"  # one folder per diploma, vectors beside


class Stores:
    """The Postgres store and the corpus in memory, each opened the first time it is asked for."""

    def __init__(self, split: str = "dev") -> None:
        self.split = split  # for the caches of models a retriever calls
        self._conn: psycopg.Connection | None = None
        self._corpus: Corpus | None = None

    @property
    def conn(self) -> psycopg.Connection:
        if self._conn is None:
            self._conn = db.connect()
        return self._conn

    @property
    def corpus(self) -> Corpus:
        if self._corpus is None:
            self._corpus = Corpus.load(*corpus_files(PROCESSED))
        return self._corpus

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()


@dataclass
class Built:
    retriever: Retriever
    config: dict[str, Any]
    article_at: ArticleAt  # from the store the retriever searched, for the answer model to read
    store: str  # that store's fingerprint, for the ranking cache


def on_postgres(stores: Stores, retriever: Retriever, config: dict[str, Any]) -> Built:
    conn = stores.conn
    return Built(
        retriever, config, lambda d, a, day: db.article_at(conn, d, a, day), db.fingerprint(conn)
    )


def bm25(stores: Stores) -> Built:
    return on_postgres(stores, Bm25(stores.conn), {"index": "pg_search bm25, stemmer=portuguese"})


def dense(stores: Stores) -> Built:
    embedder = BgeM3()
    embedded = embed_missing(stores.conn, embedder)
    print(f"embedded {embedded} article versions that had no up-to-date embedding")
    return on_postgres(stores, Dense(stores.conn, embedder), {"model": embedder.name})


def dense_api(stores: Stores, document_format: str = PLAIN_DOCUMENT) -> Built:
    """Gemini Embedding 2 over the corpus in memory: the serverless demo's retriever."""
    corpus = stores.corpus
    key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("LLM_API_KEY", "")
    embedder = cache.CachedEmbedder(
        ApiEmbedder(api_key=key, document_format=document_format),
        results.ROOT / ".cache" / "embeddings",
    )
    path = PROCESSED / f"vectors-{embedder.name.replace('@', '-')}.npz"
    vectors, embedded = embed_corpus(corpus, embedder, path)
    print(f"embedded {embedded} article versions that had no up-to-date vector")
    config = {
        "model": embedder.name,
        "store": "memory",
        "query": embedder.query_format,
        "document": embedder.document_format,
    }
    return Built(
        DenseInMemory(corpus, embedder, vectors), config, corpus.article_at, corpus.fingerprint()
    )


def dense_api_titled(stores: Stores) -> Built:
    """The same, documents written as Google's guide writes them (ADR 0014, 2026-10-06)."""
    return dense_api(stores, GEMINI_DOCUMENT)


def with_references(base: Callable[[Stores], Built]) -> Callable[[Stores], Built]:
    def build(stores: Stores) -> Built:
        b = base(stores)
        config = {**b.config, "references": "ADR 0004 parser"}
        return Built(WithReferences(b.retriever, b.article_at), config, b.article_at, b.store)

    return build


def with_cross_references(base: Callable[[Stores], Built]) -> Callable[[Stores], Built]:
    def build(stores: Stores) -> Built:
        b = base(stores)
        config = {**b.config, "cross_references": f"top {TOP}, {PER_ARTICLE} per article"}
        return Built(WithCrossReferences(b.retriever, b.article_at), config, b.article_at, b.store)

    return build


def with_decomposition(base: Callable[[Stores], Built]) -> Callable[[Stores], Built]:
    def build(stores: Stores) -> Built:
        b = base(stores)
        model = llm.Cached(
            llm.from_env(overload_waits=llm.OVERLOAD_WAITS),
            results.ROOT / ".cache" / "llm" / stores.split,
        )
        config = {**b.config, "decomposition": model.name}
        return Built(Decomposed(b.retriever, model), config, b.article_at, b.store)

    return build


def hybrid(stores: Stores) -> Built:
    lexical, semantic = bm25(stores), dense(stores)
    retriever = Hybrid([lexical.retriever, semantic.retriever])
    config = {**semantic.config, "fusion": f"rrf k={retriever.k} depth={retriever.depth}"}
    return on_postgres(stores, retriever, config)


def dense_reranked(stores: Stores) -> Built:
    semantic = dense(stores)
    scorer = BgeReranker()
    retriever = Reranked(semantic.retriever, scorer, stores.conn)
    config = {**semantic.config, "reranker": scorer.name, "rerank_depth": retriever.depth}
    return on_postgres(stores, retriever, config)


RETRIEVERS: dict[str, Callable[[Stores], Built]] = {
    "bm25": bm25,
    "dense": dense,
    "bm25+refs": with_references(bm25),
    "dense+refs": with_references(dense),
    "hybrid+refs": with_references(hybrid),
    "dense+rerank+refs": with_references(dense_reranked),
    "dense-gemini": dense_api,
    "dense-gemini+refs": with_references(dense_api),
    "dense-gemini-titled+refs": with_references(dense_api_titled),
    "dense-gemini+xrefs+refs": with_references(with_cross_references(dense_api)),
    "dense-gemini+decomp+refs": with_references(with_decomposition(dense_api)),
    "dense+rerank+xrefs+refs": with_references(with_cross_references(dense_reranked)),
}


# USD per million tokens on the paid tier, input and output (thinking is billed as output), from
# ai.google.dev/gemini-api/docs/pricing, read 2026-10-06. The demo runs on the free tier, so
# this is what its answers would cost, not what they cost.
PRICES = {"gemini-3.1-flash-lite": (0.25, 1.50)}


def cost(usage: dict[str, int], model: str, questions: int) -> dict[str, Any] | None:
    """The run's cost at the paid prices, total and per question; a lower bound while some
    calls' thinking was not recorded (cached before it was)."""
    if model not in PRICES or not questions:
        return None
    per_input, per_output = PRICES[model]
    output = usage["completion_tokens"] + usage["thinking_tokens"]
    usd = (usage["prompt_tokens"] * per_input + output * per_output) / 1_000_000
    return {
        "usd_per_million": {"input": per_input, "output": per_output},
        "usd": round(usd, 6),
        "usd_per_question": round(usd / questions, 6),
        "lower_bound": usage["thinking_unrecorded"] > 0,
    }


def table(summary: dict[str, dict[str, Any]], columns: list[str]) -> None:
    print(f"{'':>18}  " + "  ".join(f"{c[:18]:>18}" for c in columns))
    for group, row in summary.items():
        cells = [
            "-" if row[c] is None else f"{row[c]:.2f}" if isinstance(row[c], float) else row[c]
            for c in columns
        ]
        print(f"{group:>18}  " + "  ".join(f"{c:>18}" for c in cells))


def build(stores: Stores, name: str, split: str) -> tuple[cache.Cached, Built]:
    """The named retriever behind a ranking cache, per split like the LLM cache."""
    built = RETRIEVERS[name](stores)
    directory = results.ROOT / ".cache" / "retrieval" / split
    return cache.Cached(built.retriever, directory, cache.version(built.config, built.store)), built


JUDGED = "judge-{}"  # results/dev/judge-<system>.json: verdicts on dev and their agreement
CHECK = "judge-check"  # results/dev/judge-check.json: the judge on known-answer cases


@dataclass(frozen=True)
class Verdict:
    id: str
    type: str
    verdict: str
    human: str | None  # the hand label, where there is one


def judge_model(split: str = "dev") -> llm.Cached:
    """The judge, a different model from the one that answers; its calls are cached like every
    other eval call, per split."""
    model = llm.OpenAiCompatible(
        model=judge.JUDGE_MODEL,
        api_key=os.environ.get("LLM_API_KEY", ""),
        params={},  # Gemma takes no reasoning effort
        overload_waits=llm.OVERLOAD_WAITS,
        system_as_user=True,  # nor system instructions, on Gemini's API
    )
    return llm.Cached(model, results.ROOT / ".cache" / "llm" / split)


def prompt_version() -> str:
    return hashlib.sha256(judge.SYSTEM.encode()).hexdigest()[:12]


def dev_run(system: str) -> dict[str, Any]:
    path = results.RESULTS / "dev" / f"{system}.json"
    if not path.exists():
        raise SystemExit(f"no dev answers for {system}: run python -m lex.eval answers first")
    run: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if run["config"].get("task") != "answers":
        raise SystemExit(f"{path.name} is not an answers run")
    return run


def label(system: str) -> int:
    """Hand labels for a system's dev answers, asked one by one in the terminal."""
    run, items = dev_run(system), {i.id: i for i in load("dev")}
    labels = judge.load_labels()
    # Refusals are wrong without the judge, so labelling them would only inflate agreement.
    todo = [
        r
        for r in run["items"]
        if r["type"] != "unanswerable"
        and not r["refused"]
        and (r["id"], judge.answer_sha(r["text"])) not in labels
    ]
    if not todo:
        print("Todas as respostas deste sistema já têm rótulo.")
        return 0
    by = input("O teu nome (fica registado como quem rotulou): ").strip()
    if not by:
        return 1
    print(
        "\ncorreta: diz o essencial da referência sem a contradizer\n"
        "parcial: acerta em parte, falta algo pedido ou tem um erro menor\n"
        "errada: contradiz a referência, erra o que muda a conclusão, ou não responde"
    )
    keys = {"c": "correta", "p": "parcial", "e": "errada"}
    for n, r in enumerate(todo, start=1):
        item = items[r["id"]]
        print(f"\n[{n}/{len(todo)}] {item.id} · {item.type} · lei em vigor a {item.as_of:%d/%m/%Y}")
        print(f"Pergunta: {item.question}\nReferência: {item.answer}")
        print(f"Sistema{' (recusou)' if r['refused'] else ''}:\n{r['text']}")
        print(f"Cita: {', '.join(r['cited']) or '-'} · devia citar: {', '.join(r['expected'])}")
        while True:
            key = (
                input("[c]orreta · [p]arcial · [e]rrada · [s]altar · [q] sair > ")
                .strip()[:1]
                .lower()
            )
            if key in keys:
                judge.add_label(item.id, system, r["text"], keys[key], by)
                break
            if key == "s":
                break
            if key == "q":
                return 0
    return 0


def judge_dev(system: str, minimum: int) -> int:
    """Judge a system's dev answers, and measure the judge against the hand labels."""
    run, items = dev_run(system), {i.id: i for i in load("dev")}
    labels = judge.load_labels()
    labelled = [
        r
        for r in run["items"]
        if not r["refused"] and (r["id"], judge.answer_sha(r["text"])) in labels
    ]
    if len(labelled) < minimum:
        print(
            f"{len(labelled)} hand labels for these answers, {minimum} needed to measure the "
            f"judge: python -m lex.eval label {system}"
        )
        return 1
    model = judge_model("dev")
    j = judge.Judge(model)
    verdicts = []
    for r in run["items"]:
        if r["type"] == "unanswerable":
            continue
        found = j.verdict(items[r["id"]], r["text"], r["refused"])
        human = labels.get((r["id"], judge.answer_sha(r["text"])))
        verdicts.append(Verdict(r["id"], r["type"], found, human))
    # Only answers the judge read: a refusal's verdict is not the judge's (see label()).
    refused = {r["id"] for r in run["items"] if r["refused"]}
    pairs = [(v.human, v.verdict) for v in verdicts if v.human is not None and v.id not in refused]
    agreement = judge.agreement(pairs)
    correct = judge.correctness(
        {v.id: v.verdict for v in verdicts}, {v.id: v.type for v in verdicts}
    )
    summary: dict[str, Any] = {"agreement": agreement, **correct}
    config = {
        "judge": model.name,
        "judge_prompt": prompt_version(),
        "judged_system": system,
        "unparsed": j.unparsed,
        "usage": model.usage(),
    }
    path = results.write("dev", JUDGED.format(system), config, summary, verdicts)
    print(f"judge {model.name} on {system}, dev: agreement with hand labels {agreement}")
    table(correct, ["items", *judge.VERDICTS])
    print(f"written to {path.relative_to(results.ROOT)}")
    return 0


def judge_check() -> int:
    """The judge on answers whose verdict is known by construction (ADR 0015): each answerable dev
    item's reference answer as it is, and with a quantity changed or its yes or no turned over."""
    items = {i.id: i for i in load("dev")}
    model = judge_model("dev")
    j = judge.Judge(model)
    checked = []
    for case in judge.known_cases(items.values()):
        found = j.verdict(items[case.id], case.answer, refused=False)
        checked.append(
            judge.Checked(case.id, case.kind, case.answer, found, found in case.expected)
        )
    summary = judge.check_summary(checked)
    config = {
        "judge": model.name,
        "judge_prompt": prompt_version(),
        "pass_share": judge.CHECK_PASS,
        "unparsed": j.unparsed,
        "usage": model.usage(),
    }
    path = results.write("dev", CHECK, config, summary, checked)
    for group in ("reference", "number", "yes-no", "altered"):
        if group not in summary:
            continue  # no dev reference had a quantity, or a yes or no, to alter
        row = summary[group]
        verdicts = ", ".join(f"{v} {row[v]}" for v in judge.VERDICTS)
        print(f"{group:>10}: {row['as_expected']} of {row['cases']} as expected ({verdicts})")
    outcome = "passed" if summary["passed"] else "failed"
    print(f"{outcome}: references and altered answers must each reach {judge.CHECK_PASS:.0%}")
    print(f"written to {path.relative_to(results.ROOT)}")
    return 0 if summary["passed"] else 1


def measured_judge(system: str) -> dict[str, Any]:
    """How the judge, with today's model and prompt, was measured on dev: its agreement with hand
    labels on this system's answers or, without them, the known-answer checks it passed (ADR
    0015). Without either, correctness is not reported (CLAUDE.md)."""
    current = (judge.JUDGE_MODEL, prompt_version())
    labelled = results.RESULTS / "dev" / f"{JUDGED.format(system)}.json"
    if labelled.exists():
        run = json.loads(labelled.read_text(encoding="utf-8"))
        if (run["config"]["judge"], run["config"]["judge_prompt"]) != current:
            raise SystemExit("the judge or its prompt changed since it was measured: judge again")
        return {"hand_labels": run["summary"]["agreement"]}
    checked = results.RESULTS / "dev" / f"{CHECK}.json"
    if checked.exists():
        run = json.loads(checked.read_text(encoding="utf-8"))
        if (run["config"]["judge"], run["config"]["judge_prompt"]) != current:
            raise SystemExit("the judge or its prompt changed since its check: judge-check again")
        if not run["summary"]["passed"]:
            raise SystemExit(
                "the judge failed its known-answer checks: correctness is not reported"
            )
        s = run["summary"]
        return {
            "known_answer_checks": {
                group: {"as_expected": s[group]["as_expected"], "cases": s[group]["cases"]}
                for group in ("reference", "altered")
            }
        }
    raise SystemExit(
        f"the judge is not measured: python -m lex.eval judge {system} (after hand labels), "
        "or python -m lex.eval judge-check"
    )


def percentile(values: list[float], share: float) -> float:
    """The value below which `share` of the values fall (nearest rank)."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]


def latency(url: str, n: int) -> int:
    """How long the deployed demo takes to answer: n dev questions, asked one at a time, each on
    its own date. The first may meet a cold function, so it is reported apart. Spends n of the
    demo's daily embeddings and answers."""
    base = url.rstrip("/")
    with urllib.request.urlopen(f"{base}/api/health", timeout=30) as response:
        system = json.loads(response.read())["system"]
    asked = [i for i in load("dev") if i.type != "unanswerable"][:n]
    rows = []
    for item in asked:
        body = json.dumps({"question": item.question, "as_of": item.as_of.isoformat()}).encode()
        request = urllib.request.Request(
            f"{base}/api/answer", data=body, headers={"Content-Type": "application/json"}
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                reply = json.loads(response.read())
            status = 200
        except urllib.error.HTTPError as error:
            reply, status = {}, error.code
        rows.append(
            {
                "status": status,
                "total": round(time.perf_counter() - started, 2),
                "server": reply.get("seconds"),
                "cached": reply.get("cached", False),
                **reply.get("answer", {}).get("timings", {}),
            }
        )
    fresh = [r for r in rows[1:] if r["status"] == 200 and not r["cached"]]
    summary: dict[str, Any] = {
        "asked": len(rows),
        "failed": sum(r["status"] != 200 for r in rows),
        "first_total": rows[0]["total"] if rows else None,
        "measured": len(fresh),
    }
    for key in ("total", "server", "retrieval", "generation"):
        values = [float(r[key]) for r in fresh if r.get(key) is not None]
        if values:
            summary[f"{key}_p50"] = percentile(values, 0.5)
            summary[f"{key}_p95"] = percentile(values, 0.95)
    record = {
        "url": base,
        "system": system,
        "measured_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": summary,
        "requests": rows,
    }
    path = results.RESULTS / "dev" / f"latency-{system}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{system} at {base}: {summary}")
    print(f"written to {path.relative_to(results.ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lex.eval")
    commands = parser.add_subparsers(dest="command", required=True)
    retrieval = commands.add_parser("retrieval", help="score a retriever's recall@k")
    retrieval.add_argument("system", choices=sorted(RETRIEVERS))
    retrieval.add_argument("--split", choices=["dev", "test"], default="dev")
    answers = commands.add_parser("answers", help="score the reference system's answers")
    answers.add_argument("--retriever", choices=sorted(RETRIEVERS), default="dense+rerank+refs")
    answers.add_argument("--k", type=int, default=K, help="article versions given to the model")
    answers.add_argument("--split", choices=["dev", "test"], default="dev")
    answers.add_argument("--judge", action="store_true", help="also judge correctness")
    answers.add_argument(
        "--format",
        choices=[*FORMATS, "agent"],
        default="answer",
        help="claims: per sentence; agent: claims, after asking for more articles",
    )
    answers.add_argument(
        "--repeat", type=int, default=0, help="N: ask the model again, to measure run-to-run noise"
    )
    labeling = commands.add_parser("label", help="hand-label a system's dev answers")
    labeling.add_argument("system", help="a results/dev/<system>.json answers run")
    judging = commands.add_parser("judge", help="judge dev answers and measure the judge")
    judging.add_argument("system", help="a results/dev/<system>.json answers run")
    judging.add_argument("--minimum", type=int, default=20, help="hand labels needed")
    commands.add_parser("judge-check", help="measure the judge on known-answer dev cases")
    commands.add_parser("check-results", help="check results/ against itself; no model, for CI")
    timing = commands.add_parser("latency", help="time the deployed demo on dev questions")
    timing.add_argument("url", help="e.g. https://lex-beryl.vercel.app")
    timing.add_argument("--n", type=int, default=15, help="questions (and quota) to spend")
    args = parser.parse_args(argv)
    load_dotenv(results.ROOT / ".env")

    if args.command == "label":
        return label(args.system)
    if args.command == "judge":
        return judge_dev(args.system, args.minimum)
    if args.command == "judge-check":
        return judge_check()
    if args.command == "check-results":
        problems = check_results(results.RESULTS, results.BENCH)
        print("\n".join(problems) or "results/ adds up, and its test runs share one split")
        return 1 if problems else 0
    if args.command == "latency":
        return latency(args.url, args.n)

    results.ensure_reproducible(args.split)
    items = load(args.split)
    stores = Stores(args.split)
    try:
        if args.command == "retrieval":
            retriever, built = build(stores, args.system, args.split)
            item_results = run_retrieval(items, retriever)
            summary: dict[str, Any] = dict(summarise(item_results))
            config = {**built.config, "ks": list(KS)}
            path = results.write(args.split, retriever.name, config, summary, item_results)
            answerable = len(item_results)
            print(f"{retriever.name} on {args.split}: {len(items)} items, {answerable} answerable")
            table(summary, ["items", *(f"recall@{k}" for k in KS)])
        else:
            # Per split: test prompts hold test questions, and only the harness reads them.
            model = llm.Cached(
                llm.from_env(overload_waits=llm.OVERLOAD_WAITS),
                results.ROOT / ".cache" / "llm" / args.split,
                repeat=args.repeat,
            )
            retriever, built = build(stores, args.retriever, args.split)
            article_at = built.article_at

            def read(c: Citation, day: dt.date) -> ArticleVersion | None:
                return article_at(c.diploma, c.article, day)

            system: ReferenceSystem | AgentSystem = (
                AgentSystem(retriever, read, model, k=args.k)
                if args.format == "agent"  # Phase 7: it may ask for more articles first
                else ReferenceSystem(retriever, read, model, k=args.k, format=args.format)
            )
            if args.repeat:
                system.name += f"+repeat-{args.repeat}"
            # Checked before any answer is paid for.
            measured = measured_judge(system.name) if args.judge else None
            answer_results = run_answers(items, system)
            summary = dict(summarise_answers(answer_results))
            config = {
                **built.config,
                "task": "answers",
                "llm": model.name,
                "llm_params": model.params,
                "k": args.k,
                "format": args.format,
                "repeat": args.repeat,
                "usage": model.usage(),
                "cost": cost(model.usage(), model.name, len(items)),
                "counts": system.counts,  # what turned answers into refusals; the agent's asks
            }
            if measured is not None:
                j = judge.Judge(judge_model(args.split))
                by_id = {i.id: i for i in items}
                verdicts = {
                    r.id: j.verdict(by_id[r.id], r.text, r.refused)
                    for r in answer_results
                    if r.type != "unanswerable"
                }
                types = {r.id: r.type for r in answer_results}
                summary["correctness"] = judge.correctness(verdicts, types)
                config["judge"] = {
                    "model": j.name,
                    "prompt": prompt_version(),
                    "measured_on_dev": measured,
                    "unparsed": j.unparsed,
                }
            path = results.write(args.split, system.name, config, summary, answer_results)
            print(f"{system.name} on {args.split}: {len(items)} items")
            table(
                {k: v for k, v in summary.items() if k != "correctness"},
                ["items", "refused", "cited", "citation_precision", "citation_recall"],
            )
            if "correctness" in summary:
                print(f"correctness, judged by {judge.JUDGE_MODEL}, measured on dev by {measured}:")
                table(summary["correctness"], ["items", *judge.VERDICTS])
            print(f"llm usage: {model.usage()}; {system.counts}")
            print(f"cost at paid prices: {config['cost']}")
    finally:
        stores.close()
    print(f"retrieval cache: {retriever.hits} hits, {retriever.misses} misses")
    print(f"written to {path.relative_to(results.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
