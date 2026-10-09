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
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psycopg
from dotenv import load_dotenv

from lex.bench.corpus_check import INDEX, load_periods
from lex.bench.schema import Item
from lex.bench.splits import load
from lex.domain import Citation, Retriever
from lex.eval import compare, judge, report, results
from lex.eval.check import check_results
from lex.eval.gates import (
    CHECK,
    JUDGED,
    checked_as,
    demo_dev_run,
    dev_run,
    judge_name,
    judge_params,
    justifying_dev_run,
    measured_judge,
    prompt_version,
)
from lex.eval.harness import (
    KS,
    AnswerResult,
    run_answers,
    run_retrieval,
    summarise,
    summarise_answers,
)
from lex.eval.outside import FileSystem, HttpSystem
from lex.generation import llm
from lex.generation.agent import AGENT_SYSTEM, AgentSystem, agent_prompt
from lex.generation.answer import (
    CLAIMS_SYSTEM,
    COVER_SYSTEM,
    FORMATS,
    SYSTEM,
    K,
    ReferenceSystem,
    prompt,
)
from lex.retrieval import cache
from lex.retrieval.bm25 import Bm25
from lex.retrieval.crossrefs import PER_ARTICLE, TOP, WithCrossReferences
from lex.retrieval.decompose import Decomposed
from lex.retrieval.dense import (
    GEMINI_DOCUMENT,
    GEMINI_QUERY,
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
    # Where each model the retriever calls sends its requests (ADR 0016, amended).
    endpoints: dict[str, dict[str, str]] = field(default_factory=dict)
    versions: dict[str, int] = field(default_factory=dict)  # the store's, per diploma
    embedder: cache.CachedEmbedder | None = None  # an embedder billed per token, if one

    def corpus(self) -> dict[str, Any]:
        """What a run records of the corpus it ran on (ROADMAP, Phase 10)."""
        return {"fingerprint": self.store, "versions": self.versions}


def on_postgres(stores: Stores, retriever: Retriever, config: dict[str, Any]) -> Built:
    conn = stores.conn
    return Built(
        retriever,
        config,
        lambda d, a, day: db.article_at(conn, d, a, day),
        db.fingerprint(conn),
        versions=db.counts(conn),
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
    api = ApiEmbedder(api_key=key, document_format=document_format)
    embedder = cache.CachedEmbedder(api, results.ROOT / ".cache" / "embeddings")
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
        DenseInMemory(corpus, embedder, vectors),
        config,
        corpus.article_at,
        corpus.fingerprint(),
        {"embeddings": llm.endpoint(api.base_url, api.model)},
        corpus.counts(),
        embedder,
    )


def dense_api_titled(stores: Stores) -> Built:
    """The same, documents written as Google's guide writes them (ADR 0014, 2026-10-06)."""
    return dense_api(stores, GEMINI_DOCUMENT)


def with_references(base: Callable[[Stores], Built]) -> Callable[[Stores], Built]:
    def build(stores: Stores) -> Built:
        b = base(stores)
        config = {**b.config, "references": "ADR 0004 parser"}
        return replace(b, retriever=WithReferences(b.retriever, b.article_at), config=config)

    return build


def with_cross_references(base: Callable[[Stores], Built]) -> Callable[[Stores], Built]:
    def build(stores: Stores) -> Built:
        b = base(stores)
        config = {**b.config, "cross_references": f"top {TOP}, {PER_ARTICLE} per article"}
        return replace(b, retriever=WithCrossReferences(b.retriever, b.article_at), config=config)

    return build


def with_decomposition(base: Callable[[Stores], Built]) -> Callable[[Stores], Built]:
    def build(stores: Stores) -> Built:
        b = base(stores)
        model = llm.Cached(
            llm.from_env(overload_waits=llm.OVERLOAD_WAITS),
            results.ROOT / ".cache" / "llm" / stores.split,
        )
        config = {**b.config, "decomposition": model.name}
        endpoints = {**b.endpoints, "decomposition": llm.endpoint(model.base_url, model.name)}
        retriever = Decomposed(b.retriever, model)
        return replace(b, retriever=retriever, config=config, endpoints=endpoints)

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


def cost(usage: dict[str, int], model: str, questions: int) -> dict[str, Any] | None:
    """The run's cost at the paid prices, total and per question; a lower bound while some
    calls' thinking was not recorded (cached before it was)."""
    usd = llm.usd(usage, model)
    if usd is None or not questions:
        return None
    per_input, per_output = llm.PRICES[model]
    return {
        "usd_per_million": {"input": per_input, "output": per_output},
        "usd": round(usd, 6),
        "usd_per_question": round(usd / questions, 6),
        "lower_bound": usage["thinking_unrecorded"] > 0,
    }


def embedding_cost(embedder: cache.CachedEmbedder, questions: int) -> dict[str, Any]:
    """What the texts a run embedded (its questions, as written for the model, and any search
    the agent asked for) cost at the paid price, tokens counted by the provider."""
    tokens = embedder.tokens(embedder.used)
    price = llm.PRICES.get(embedder.base.name.split("@")[0]) if tokens is not None else None
    usd = tokens * price[0] / 1_000_000 if tokens is not None and price else None
    return {
        "texts": len(embedder.used),
        "tokens": tokens,
        "usd": None if usd is None else round(usd, 8),
        "usd_per_question": None if usd is None or not questions else round(usd / questions, 8),
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


@dataclass(frozen=True)
class Verdict:
    id: str
    type: str
    verdict: str
    human: str | None  # the hand label, where there is one
    reason: str = ""


def judge_url() -> str:
    """Google's API, or JUDGE_BASE_URL from `.env`: a server on this machine."""
    return os.environ.get("JUDGE_BASE_URL") or llm.GEMINI_OPENAI_URL


def judge_model(split: str = "dev", sample: str = "", repeat: int = 0) -> llm.Cached:
    """The judge, a different model from the one that answers; its calls are cached like every
    other eval call, per split (`sample`: see llm.Cached)."""
    model = llm.OpenAiCompatible(
        model=judge_name(),
        base_url=judge_url(),
        api_key=os.environ.get("LLM_API_KEY", ""),
        params=judge_params(),  # a temperature; Gemma takes no reasoning effort
        overload_waits=llm.OVERLOAD_WAITS,
        system_as_user=True,  # nor system instructions, on Gemini's API
    )
    return llm.Cached(model, results.ROOT / ".cache" / "llm" / split, repeat, sample)


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
        found = j.judged(items[r["id"]], r["text"], r["refused"])
        human = labels.get((r["id"], judge.answer_sha(r["text"])))
        verdicts.append(Verdict(r["id"], r["type"], found.verdict, human, found.reason))
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
        "judge_params": model.params,
        "judged_system": system,
        "endpoints": {"judge": llm.endpoint(model.base_url, model.name)},
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
        found = j.judged(items[case.id], case.answer, refused=False)
        right = found.verdict in case.expected
        checked.append(
            judge.Checked(case.id, case.kind, case.answer, found.verdict, right, found.reason)
        )
    summary = judge.check_summary(checked)
    config = {
        "judge": model.name,
        "judge_prompt": prompt_version(),
        "judge_params": model.params,
        "pass_share": judge.CHECK_PASS,
        "endpoints": {"judge": llm.endpoint(model.base_url, model.name)},
        "unparsed": j.unparsed,
        "usage": model.usage(),
    }
    path = results.write("dev", checked_as(model.params), config, summary, checked)
    for group in ("reference", "number", "yes-no", "altered", "contradicted", "other", "lenient"):
        if group not in summary:
            continue  # no dev reference had a quantity, or a yes or no, to alter
        row = summary[group]
        verdicts = ", ".join(f"{v} {row[v]}" for v in judge.VERDICTS)
        print(f"{group:>10}: {row['as_expected']} of {row['cases']} as expected ({verdicts})")
    outcome = "passed" if summary["passed"] else "failed"
    print(
        f"{outcome}: references, altered and lenient cases must each reach {judge.CHECK_PASS:.0%}"
    )
    print(f"written to {path.relative_to(results.ROOT)}")
    return 0 if summary["passed"] else 1


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


@dataclass
class AnswerRun:
    name: str
    config: dict[str, Any]
    summary: dict[str, Any]
    items: list[AnswerResult]
    retriever: cache.Cached | None  # None for a system scored from outside


def answer_run(
    stores: Stores,
    items: list[Item],
    split: str,
    retriever_name: str,
    format: str,
    k: int,
    repeat: int,
    judged: bool,
    fresh: bool = False,
    judge_samples: int = 1,
) -> AnswerRun:
    """Answers every item with the named system and scores it, judged if asked; writes nothing.
    `fresh` asks the model and the judge again rather than answer from the cache, as a milestone
    does (ROADMAP, Phase 9): a sample named for the day, which a re-run that day reuses."""
    sample = f"fresh-{dt.date.today().isoformat()}" if fresh else ""
    # Per split: test prompts hold test questions, and only the harness reads them.
    model = llm.Cached(
        llm.from_env(overload_waits=llm.OVERLOAD_WAITS),
        results.ROOT / ".cache" / "llm" / split,
        repeat=repeat,
        sample=sample,
    )
    retriever, built = build(stores, retriever_name, split)
    article_at = built.article_at
    if built.embedder is not None:
        built.embedder.used.clear()  # the corpus, embedded while building, is not the run's
    endpoints = {**built.endpoints, "answers": llm.endpoint(model.base_url, model.name)}
    if judged:
        endpoints["judge"] = llm.endpoint(judge_url(), judge_name())
    results.ensure_private(split, endpoints)  # before any test item is sent

    def read(c: Citation, day: dt.date) -> ArticleVersion | None:
        return article_at(c.diploma, c.article, day)

    system: ReferenceSystem | AgentSystem = (
        AgentSystem(retriever, read, model, k=k)
        if format == "agent"  # Phase 7: it may ask for more articles first
        else ReferenceSystem(retriever, read, model, k=k, format=format)
    )
    if repeat:
        system.name += f"+repeat-{repeat}"
    # On dev, another judging is kept apart from the run of record; a test run is the run of
    # record, its samples in its config (`judge.samples`).
    if split == "dev" and judged and (judge_samples > 1 or checked_as(judge_params()) != CHECK):
        system.name += f"+judge-{judge_samples}" + checked_as(judge_params())[len(CHECK) :]
    # Checked before any answer is paid for.
    justified = (
        justifying_dev_run(
            system.name,
            {
                **built.config,
                "llm": model.name,
                "llm_params": model.params,
                "k": k,
                "format": format,
                "prompts": fingerprint(format),
            },
        )
        if split == "test"
        else None
    )
    measured = measured_judge(system.name) if judged else None
    # The corpus index says which version was in force on each date (Phase 9).
    periods = load_periods([INDEX]) if INDEX.exists() else None
    answer_results = run_answers(items, system, periods)
    summary: dict[str, Any] = dict(summarise_answers(answer_results))
    config = {
        **built.config,
        "task": "answers",
        "llm": model.name,
        "llm_params": model.params,
        "k": k,
        "format": format,
        "prompts": fingerprint(format),
        "corpus": built.corpus(),
        "endpoints": endpoints,
        "justified_by": justified,  # test runs: the dev run they stand on
        "repeat": repeat,
        "usage": model.usage(),
        "cost": cost(model.usage(), model.name, len(items)),  # the answers'
        "counts": system.counts,  # what turned answers into refusals; the agent's asks
        "cache": {"answers": model.dates()},  # when the responses used were made
    }
    # A question's whole cost (ROADMAP, Phase 10): the answer's calls and the embedding of
    # what was searched for; the judge's apart, as judging is not answering.
    costs: dict[str, Any] = {"answers": config["cost"]}
    if built.embedder is not None:
        costs["embeddings"] = embedding_cost(built.embedder, len(items))
    parts = [costs["answers"], costs.get("embeddings")]
    known = [p["usd_per_question"] for p in parts if p and p.get("usd_per_question") is not None]
    costs["usd_per_question"] = (
        round(sum(known), 8) if len(known) == len([p for p in parts if p]) else None
    )
    config["costs"] = costs
    if measured is not None:
        answer_results = judge_answers(
            answer_results, items, split, sample, judge_samples, measured, config, summary
        )
    return AnswerRun(system.name, config, summary, answer_results, retriever)


def judge_answers(
    answer_results: list[AnswerResult],
    items: list[Item],
    split: str,
    sample: str,
    judge_samples: int,
    measured: dict[str, Any],
    config: dict[str, Any],
    summary: dict[str, Any],
) -> list[AnswerResult]:
    """The judge's verdict on every answerable item, kept with each answer; correctness, the
    judge's measurement, samples, failures and tokens written into `summary` and `config`."""
    # The first sample is the one a single-sample run asks; the others are other draws, and
    # a reply with no verdict is asked once more, of a draw of its own.
    judging = judge_model(split, sample)
    others = [judge_model(split, sample, repeat=n) for n in range(1, judge_samples)]
    retry = judge_model(split, f"{sample}retry")
    j = judge.Judge(judging, others, retry)
    by_id = {i.id: i for i in items}
    # Each verdict and its reason stay with the answer, so check-results can recompute
    # correctness from the items (test runs keep the verdict, not the reason).
    answer_results = [
        r
        if r.type == "unanswerable"
        else replace(r, **asdict(j.judged(by_id[r.id], r.text, r.refused)))
        for r in answer_results
    ]
    verdicts = {r.id: r.verdict for r in answer_results if r.verdict is not None}
    types = {r.id: r.type for r in answer_results}
    summary["correctness"] = judge.correctness(verdicts, types)
    config["judge"] = {
        "model": j.name,
        "prompt": prompt_version(),
        "params": judging.params,
        "measured_on_dev": measured,
        "samples": judge_samples,
        "disagreed": j.disagreed,  # answers whose samples differ: the judge's own noise
        "unparsed": j.unparsed,
        "unparsed_ids": j.unparsed_ids,
        "retried_ids": j.retried_ids,
    }
    config["cache"]["judge"] = judging.dates()
    spent_judging = [judging.usage(), *(o.usage() for o in others), retry.usage()]
    judge_tokens = {
        key: sum(u.get(key, 0) for u in spent_judging)
        for key in ("calls", "prompt_tokens", "completion_tokens", "thinking_tokens")
    }
    config["costs"]["judge"] = {
        "usage": judge_tokens,
        "usd": None,  # Gemma 4 has no paid tier on Google's API: not priced
        "priced": j.name in llm.PRICES,
    }
    if split == "test" and j.unparsed_ids:
        raise SystemExit(
            f"the judge gave no verdict on {', '.join(j.unparsed_ids)}, even asked again: "
            "no test number counts an unread verdict as wrong; nothing written"
        )
    return answer_results


def outside_run(
    items: list[Item],
    split: str,
    system: FileSystem | HttpSystem,
    judged: bool,
    judge_samples: int,
    operator: str | None,
) -> AnswerRun:
    """A system scored from outside (ROADMAP, Phase 12): answers from a file, or from an endpoint
    with /api/answer's contract, scored and judged as the reference systems are."""
    if isinstance(system, HttpSystem):
        tier = "agreed" if operator else "unagreed"
        where: dict[str, str] = {"url": system.url, "tier": tier, "operator": operator or ""}
    else:
        where = {"url": "", "tier": "local"}  # answers already made, read from a file
    endpoints = {"answers": where}
    if judged:
        endpoints["judge"] = llm.endpoint(judge_url(), judge_name())
    results.ensure_private(split, endpoints)
    justified = justifying_dev_run(system.name, {}) if split == "test" else None
    measured = measured_judge(system.name) if judged else None
    periods = load_periods([INDEX]) if INDEX.exists() else None
    answer_results = run_answers(items, system, periods)
    summary: dict[str, Any] = dict(summarise_answers(answer_results))
    config: dict[str, Any] = {
        "task": "answers",
        "outside": "file" if isinstance(system, FileSystem) else "http",
        "endpoints": endpoints,
        "justified_by": justified,
    }
    if isinstance(system, FileSystem):
        config["missing"] = system.missing  # items the file gives no answer for: refusals
    if measured is not None:
        answer_results = judge_answers(
            answer_results, items, split, "", judge_samples, measured, config, summary
        )
    return AnswerRun(system.name, config, summary, answer_results, None)


# The demo's system (ADR 0014, ADR 0018): what `prompt_guard` and `regress` watch.
DEMO_RETRIEVER, DEMO_FORMAT = "dense-gemini+refs", "agent"


def fingerprint(format: str) -> str:
    """A hash of what the model is told for an answer format: the system prompts, a user prompt
    rendered from fixed inputs (so its template counts too), and the judge's prompt."""
    sample: list[tuple[Citation, Any]] = [
        (
            Citation(diploma="lei-7-2009", article="238"),
            SimpleNamespace(
                heading="Epígrafe",
                text="Texto.",
                valid_from=dt.date(2009, 2, 17),
                notes=["Nota."],  # so a change to how notes are written changes the fingerprint
            ),
        )
    ]
    day = dt.date(2020, 1, 1)
    if format == "agent":
        texts = [AGENT_SYSTEM, CLAIMS_SYSTEM, agent_prompt("P?", day, sample, ["pesquisar «x»"])]
    else:
        systems = {"answer": SYSTEM, "claims": CLAIMS_SYSTEM, "claims-cover": COVER_SYSTEM}
        texts = [systems[format], prompt("P?", day, sample)]
    joined = json.dumps([*texts, judge.SYSTEM], ensure_ascii=False)
    return hashlib.sha256(joined.encode()).hexdigest()[:12]


def prompt_guard() -> list[str]:
    """The demo's prompts and query format against those its last dev run used: a change to
    either ships only with a new dev run (Phase 8)."""
    path = demo_dev_run()
    if path is None:
        return ["no dev answers run of the demo's system in results/dev/"]
    config = json.loads(path.read_text(encoding="utf-8"))["config"]
    problems = []
    if config.get("prompts") != fingerprint(DEMO_FORMAT):
        problems.append(
            f"{path.name}: the demo's prompts changed since this run; run "
            f"python -m lex.eval answers --retriever {DEMO_RETRIEVER} --format {DEMO_FORMAT} "
            "--judge (or regress first)"
        )
    if config.get("query") != GEMINI_QUERY:
        problems.append(f"{path.name}: the demo's query format changed since this run")
    return problems


def regress(stores: Stores, items: list[Item]) -> int:
    """The demo's system on dev now, judged, against its committed dev run; writes nothing."""
    path = demo_dev_run()
    if path is None:
        raise SystemExit("no committed dev run of the demo's system to compare with")
    before = json.loads(path.read_text(encoding="utf-8"))
    if not any(i.get("verdict") for i in before["items"]):
        raise SystemExit(f"{path.name} keeps no verdicts by item: run it again to compare with")
    run = answer_run(stores, items, "dev", DEMO_RETRIEVER, DEMO_FORMAT, K, 0, True)
    now = [asdict(r) for r in run.items]
    for measure in ("correct", "refused"):
        p = compare.paired(before["items"], now, measure)
        print(
            f"{measure}: {p.items} items in both; only before {len(p.only_a)}, only now "
            f"{len(p.only_b)} (sign test p = {p.p_value():.3f})"
        )
    worse = compare.regressed(before["items"], now)
    print("\n".join(f"regression: {w}" for w in worse) or "no regression beyond the noise")
    return 1 if worse else 0


def compare_runs(first: Path, second: Path) -> int:
    """Two runs' items paired by id: where they disagree, and how likely by chance."""
    a, b = (json.loads(path.read_text(encoding="utf-8")) for path in (first, second))
    if a["bench"].get("scored") != b["bench"].get("scored"):
        print("the two runs are on different versions of their split: only shared ids compared")
    for measure in ("correct", "refused"):
        p = compare.paired(a["items"], b["items"], measure)
        print(f"{measure}, {p.items} answerable items in both (sign test p = {p.p_value():.3f}):")
        print(f"  only {first.name}: {len(p.only_a)} {' '.join(p.only_a)}")
        print(f"  only {second.name}: {len(p.only_b)} {' '.join(p.only_b)}")
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
    answers.add_argument(
        "--fresh", action="store_true", help="ask the model and judge again, as a milestone does"
    )
    answers.add_argument(
        "--judge-samples", type=int, default=1, help="N verdicts per answer; the median counts"
    )
    outside = answers.add_mutually_exclusive_group()
    outside.add_argument("--from", dest="from_file", type=Path, help="answers in a JSONL file")
    outside.add_argument("--http", help="an endpoint with /api/answer's contract")
    answers.add_argument("--name", help="the outside system's name in results/")
    answers.add_argument(
        "--operator-agrees", help="who agreed, for an --http system on test (ADR 0016)"
    )
    labeling = commands.add_parser("label", help="hand-label a system's dev answers")
    labeling.add_argument("system", help="a results/dev/<system>.json answers run")
    judging = commands.add_parser("judge", help="judge dev answers and measure the judge")
    judging.add_argument("system", help="a results/dev/<system>.json answers run")
    judging.add_argument("--minimum", type=int, default=20, help="hand labels needed")
    commands.add_parser("judge-check", help="measure the judge on known-answer dev cases")
    commands.add_parser("check-results", help="check results/ against itself; no model, for CI")
    reporting = commands.add_parser("report", help="the README's results tables, from results/")
    reporting.add_argument("--write", action="store_true", help="rewrite them; else check them")
    commands.add_parser("regress", help="the demo's system on dev against its committed run")
    comparing = commands.add_parser("compare", help="two runs item by item, with a sign test")
    comparing.add_argument("first", type=Path, help="a results/ file")
    comparing.add_argument("second", type=Path, help="another, on the same split")
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
        problems = check_results(results.RESULTS, results.BENCH) + prompt_guard()
        problems += report.stale()
        print("\n".join(problems) or "results/ adds up, and its test runs share one split")
        return 1 if problems else 0
    if args.command == "report":
        if args.write:
            report.write()
        problems = report.stale()
        print("\n".join(problems) or f"{report.README.name}'s results tables are current")
        return 1 if problems else 0
    if args.command == "latency":
        return latency(args.url, args.n)
    if args.command == "compare":
        return compare_runs(args.first, args.second)

    split = "dev" if args.command == "regress" else args.split
    results.ensure_reproducible(split)
    items = load(split)
    stores = Stores(split)
    try:
        if args.command == "retrieval":
            retriever, built = build(stores, args.system, args.split)
            results.ensure_private(args.split, built.endpoints)
            justified = (
                justifying_dev_run(retriever.name, built.config) if args.split == "test" else None
            )
            item_results = run_retrieval(items, retriever)
            summary: dict[str, Any] = dict(summarise(item_results))
            config = {**built.config, "ks": list(KS), "corpus": built.corpus()}
            config["justified_by"] = justified
            if built.endpoints:
                config["endpoints"] = built.endpoints
            path = results.write(args.split, retriever.name, config, summary, item_results)
            answerable = len(item_results)
            print(f"{retriever.name} on {args.split}: {len(items)} items, {answerable} answerable")
            table(summary, ["items", *(f"recall@{k}" for k in KS)])
        elif args.command == "regress":
            return regress(stores, items)
        elif args.from_file or args.http:
            outsider: FileSystem | HttpSystem = (
                FileSystem(args.from_file, items, args.name)
                if args.from_file
                else HttpSystem(args.http, args.name)
            )
            run = outside_run(
                items, args.split, outsider, args.judge, args.judge_samples, args.operator_agrees
            )
            retriever = None
            path = results.write(args.split, run.name, run.config, run.summary, run.items)
            print(f"{run.name} on {args.split}: {len(items)} items")
            table(
                {k: v for k, v in run.summary.items() if k != "correctness"},
                ["items", "refused", "cited", "citation_precision", "citation_recall"],
            )
            if "correctness" in run.summary:
                table(run.summary["correctness"], ["items", *judge.VERDICTS])
        else:
            run = answer_run(
                stores,
                items,
                args.split,
                args.retriever,
                args.format,
                args.k,
                args.repeat,
                args.judge,
                args.fresh,
                args.judge_samples,
            )
            retriever = run.retriever
            path = results.write(args.split, run.name, run.config, run.summary, run.items)
            print(f"{run.name} on {args.split}: {len(items)} items")
            scores = {k: v for k, v in run.summary.items() if k != "correctness"}
            columns = ["items", "refused", "cited", "citation_precision", "citation_recall"]
            if "given_recall" in scores.get("answerable", {}):
                columns += ["given_recall", "unsupported", "version_right"]
                for row in scores.values():  # unanswerable rows: "-"
                    for column in columns:
                        row.setdefault(column, None)
            table(scores, columns)
            if "correctness" in run.summary:
                measured = run.config["judge"]["measured_on_dev"]
                print(f"correctness, judged by {judge_name()}, measured on dev by {measured}:")
                table(run.summary["correctness"], ["items", *judge.VERDICTS])
            print(f"llm usage: {run.config['usage']}; {run.config['counts']}")
            print(f"cost at paid prices: {run.config['cost']}")
    finally:
        stores.close()
    if retriever is not None:
        print(f"retrieval cache: {retriever.hits} hits, {retriever.misses} misses")
    print(f"written to {path.relative_to(results.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
