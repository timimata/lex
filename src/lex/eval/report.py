"""The README's results tables, written from the test runs in results/test/ (ROADMAP 12.1).

`python -m lex.eval report --write` rewrites the block between the markers; `check-results`
fails when the block is not what the runs give, so no number in it is typed by hand. The prose
around the tables is not generated: what it quotes is checked by reading it against these runs.
"""

import json
from pathlib import Path
from typing import Any

from lex.eval.results import RESULTS, ROOT

README = ROOT / "README.md"
START = (
    "<!-- results: written by python -m lex.eval report --write; edit the code, not this block -->"
)
END = "<!-- /results -->"

# Each leaderboard system's row label, in the order the rows are shown. A run of a system not
# listed gets a row under its own name, after these.
RETRIEVAL = {
    "bm25": "BM25",
    "dense-bge-m3": "Dense (BGE-M3)",
    "dense-bge-m3+rerank+refs": "Dense + reranker + reference parser (reference system)",
    "dense-gemini-embedding-2+refs": "Gemini Embedding 2 + reference parser (the demo)",
}
ANSWERS = {
    "dense-gemini-embedding-2+refs+gemini-3.1-flash-lite+agent": (
        "**The demo: Gemini Embedding 2, the agent's prompt** "
        "([ADR 0018](docs/decisions/0018-agent.md))"
    ),
    "dense-gemini-embedding-2+refs+gemini-3.1-flash-lite+claims": (
        "Gemini Embedding 2, a citation per sentence"
    ),
    "dense-bge-m3+rerank+refs+gemini-3.1-flash-lite": "Reference retrieval (BGE-M3 and reranker)",
}
MODELS = {"gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite"}
# Benchmark versions by the test split's `scored` hash (results.bench_version), as the roadmap
# names them; the mirror's tags carry the same names (ROADMAP 12.4).
VERSIONS = {"c5bfe8bbb906": "v3", "49bb84b5aec7": "v4"}


def leaderboard(results_dir: Path = RESULTS) -> list[dict[str, Any]]:
    """The latest test run of each system (results/test/*.json; earlier versions' runs live in
    subfolders, and latency records have no system)."""
    latest: dict[str, dict[str, Any]] = {}
    for path in sorted((results_dir / "test").glob("*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        system = run.get("system")
        if system and (system not in latest or run["run_at"] > latest[system]["run_at"]):
            latest[system] = run
    return list(latest.values())


def _ordered(
    runs: list[dict[str, Any]], labels: dict[str, str]
) -> list[tuple[str, dict[str, Any]]]:
    order = list(labels)
    runs = sorted(
        runs,
        key=lambda r: (
            order.index(r["system"]) if r["system"] in order else len(order),
            r["system"],
        ),
    )
    return [(labels.get(r["system"], f"`{r['system']}`"), r) for r in runs]


def _share(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _of(share: float, items: int) -> str:
    """A share as a count, which it is: the items it was taken over are whole."""
    count = share * items
    if abs(count - round(count)) > 1e-6:
        return f"{share:.2f} of {items}"
    return f"{round(count)} of {items}"


def block(results_dir: Path = RESULTS) -> str:
    runs = leaderboard(results_dir)
    retrieval = [r for r in runs if r["config"].get("task", "retrieval") == "retrieval"]
    answers = [r for r in runs if r["config"].get("task") == "answers"]
    lines = [START]
    if not runs:
        return "\n".join([*lines, "Not measured yet.", END])
    scored = runs[0]["bench"].get("scored") or runs[0]["bench"]["sha"]
    split = f"the held-out test split of benchmark {VERSIONS.get(scored, f'`{scored}`')}"
    if answers:
        summary = answers[0]["summary"]
        total = summary["answerable"]["items"] + summary["unanswerable"]["items"]
        lines.append(
            f"On {split} ({total} questions never used to tune anything, "
            f"{summary['answerable']['items']} answerable and {summary['unanswerable']['items']} "
            "not; `results/test/`):"
        )
    else:
        lines.append(
            f"On {split} ({retrieval[0]['bench']['items']} questions never used "
            "to tune anything; `results/test/`):"
        )
    if retrieval:
        lines += [
            "",
            "| Retrieval | recall@1 | recall@10 | questions naming their article, ranked first |",
            "|---|---|---|---|",
        ]
        for label, run in _ordered(retrieval, RETRIEVAL):
            every, named = run["summary"]["all"], run["summary"].get("explicit_reference")
            lines.append(
                f"| {label} | {_share(every['recall@1'])} | {_share(every['recall@10'])} | "
                f"{_of(named['recall@1'], named['items']) if named else '-'} |"
            )
    if answers:
        settings = {(r["config"]["k"], r["config"]["llm"]) for r in answers}
        title = "Answers"
        if len(settings) == 1:
            k, llm = settings.pop()
            title = f"Answers (top {k} articles, {MODELS.get(llm, llm)})"
        lines += [
            "",
            f"| {title} | Correct (LLM judge) | Partial | Wrong | Citation recall | "
            "Citation precision | Answerable wrongly refused | Unanswerable refused |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for label, run in _ordered(answers, ANSWERS):
            s = run["summary"]
            judged = s.get("correctness", {}).get("answerable", {})
            answerable, unanswerable = s["answerable"], s["unanswerable"]
            lines.append(
                f"| {label} | {_share(judged.get('correta'))} | {_share(judged.get('parcial'))} | "
                f"{_share(judged.get('errada'))} | {_share(answerable['citation_recall'])} | "
                f"{_share(answerable['citation_precision'])} | "
                f"{_of(answerable['refused'], answerable['items'])} | "
                f"{_of(unanswerable['refused'], unanswerable['items'])} |"
            )
    return "\n".join([*lines, END])


def _split(text: str) -> tuple[str, str, str] | None:
    start, end = text.find(START), text.find(END)
    if start < 0 or end < start:
        return None
    return text[:start], text[start : end + len(END)], text[end + len(END) :]


def stale(readme: Path = README, results_dir: Path = RESULTS) -> list[str]:
    parts = _split(readme.read_text(encoding="utf-8"))
    if parts is None:
        return [f"{readme.name} has no results block ({START})"]
    if parts[1] != block(results_dir):
        return [
            f"{readme.name}'s results tables are not what results/test/ gives: "
            "python -m lex.eval report --write"
        ]
    return []


def write(readme: Path = README, results_dir: Path = RESULTS) -> None:
    parts = _split(readme.read_text(encoding="utf-8"))
    if parts is None:
        raise ValueError(f"{readme.name} has no results block ({START})")
    before, _, after = parts
    readme.write_text(before + block(results_dir) + after, encoding="utf-8", newline="\n")
