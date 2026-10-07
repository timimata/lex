import json
from pathlib import Path
from typing import Any

from lex.eval.check import check_results


def write(path: Path, run: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run), encoding="utf-8")


def retrieval_run(recall_at_1: float) -> dict[str, Any]:
    items = [
        {"id": "ct-0001", "type": "simple", "recall": {"1": 1.0}, "retrieved": [], "expected": []},
        {"id": "ct-0002", "type": "simple", "recall": {"1": 0.0}, "retrieved": [], "expected": []},
    ]
    summary = {
        "all": {"items": 2, "recall@1": recall_at_1},
        "simple": {"items": 2, "recall@1": 0.5},
    }
    return {"split": "dev", "bench": {"sha": "a"}, "config": {}, "summary": summary, "items": items}


def test_results_that_add_up_on_one_split_pass(tmp_path: Path) -> None:
    write(tmp_path / "dev" / "bm25.json", retrieval_run(0.5))
    write(tmp_path / "test" / "2026-10-06T1200-bm25.json", {"bench": {"sha": "b"}})
    write(tmp_path / "test" / "v1" / "2026-10-01T1200-bm25.json", {"bench": {"sha": "old"}})

    assert check_results(tmp_path, tmp_path / "no-data") == []


def test_an_edited_number_and_mixed_splits_are_named(tmp_path: Path) -> None:
    write(tmp_path / "dev" / "bm25.json", retrieval_run(0.75))  # the items add up to 0.5
    write(tmp_path / "test" / "2026-10-06T1200-bm25.json", {"bench": {"sha": "b"}})
    write(tmp_path / "test" / "2026-10-01T1200-bm25.json", {"bench": {"sha": "old"}})

    problems = check_results(tmp_path, tmp_path / "no-data")

    assert problems[0] == "bm25.json: its summary is not what its items add up to"
    assert problems[1].startswith("results/test/ mixes test split versions")
