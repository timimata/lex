import json
from pathlib import Path
from typing import Any

from lex.eval import report


def _run(
    path: Path,
    system: str,
    run_at: str,
    summary: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> None:
    run = {
        "split": "test",
        "bench": {"items": 3, "sha": "aaaaaaaaaaaa", "scored": "c5bfe8bbb906"},
        "system": system,
        "config": config or {},
        "run_at": run_at,
        "summary": summary,
    }
    path.write_text(json.dumps(run), encoding="utf-8")


RETRIEVAL: dict[str, Any] = {
    "all": {"items": 3, "recall@1": 1 / 3, "recall@10": 1.0},
    "explicit_reference": {"items": 1, "recall@1": 1.0, "recall@10": 1.0},
}
ANSWERS: dict[str, Any] = {
    "answerable": {
        "items": 2,
        "refused": 0.5,
        "cited": 1,
        "citation_precision": 1.0,
        "citation_recall": 0.5,
    },
    "unanswerable": {"items": 1, "refused": 1.0, "cited": 0},
    "correctness": {"answerable": {"items": 2, "correta": 0.5, "parcial": 0.0, "errada": 0.5}},
}


def _results(tmp_path: Path) -> Path:
    test = tmp_path / "results" / "test"
    test.mkdir(parents=True)
    _run(test / "a.json", "bm25", "2026-10-01T10:00", RETRIEVAL)
    old = {**RETRIEVAL, "all": {"items": 3, "recall@1": 0.0, "recall@10": 0.0}}
    _run(test / "b.json", "bm25", "2026-09-01T10:00", old)  # an older run of the same system
    answers = {"task": "answers", "k": 5, "llm": "gemini-3.1-flash-lite"}
    _run(test / "c.json", "someone-else", "2026-10-01T10:00", ANSWERS, answers)
    return tmp_path / "results"


def test_block_takes_each_systems_latest_run(tmp_path: Path) -> None:
    text = report.block(_results(tmp_path))
    assert text.startswith(report.START) and text.endswith(report.END)
    assert "benchmark v3 (3 questions never used to tune anything, 2 answerable and 1 not" in text
    assert "| BM25 | 0.33 | 1.00 | 1 of 1 |" in text
    assert "Answers (top 5 articles, Gemini 3.1 Flash-Lite)" in text
    assert "| `someone-else` | 0.50 | 0.00 | 0.50 | 0.50 | 1.00 | 1 of 2 | 1 of 1 |" in text


def test_stale_until_written(tmp_path: Path) -> None:
    results = _results(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(f"# x\n\n{report.START}\nold\n{report.END}\n\nafter\n", encoding="utf-8")
    assert report.stale(readme, results)
    report.write(readme, results)
    assert report.stale(readme, results) == []
    assert readme.read_text(encoding="utf-8").endswith(f"{report.END}\n\nafter\n")


def test_a_readme_without_the_block_is_reported(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# x\n", encoding="utf-8")
    assert report.stale(readme, _results(tmp_path))


def test_the_readme_is_current() -> None:
    assert report.stale() == []
