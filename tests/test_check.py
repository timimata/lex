import json
from pathlib import Path
from typing import Any

import pytest

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


def answers_run(verdicts: list[str], shares: dict[str, float], split: str) -> dict[str, Any]:
    from dataclasses import asdict

    from lex.eval.harness import AnswerResult, summarise_answers

    answers = [
        AnswerResult(f"ct-000{n}", "simple", False, 1.0, 1.0, verdict=v)
        for n, v in enumerate(verdicts, start=1)
    ]
    summary: dict[str, Any] = dict(summarise_answers(answers))
    summary["correctness"] = {
        "answerable": {"items": len(verdicts), **shares},
        "simple": {"items": len(verdicts), **shares},
    }
    return {
        "split": split,
        "bench": {"sha": "b"},
        "config": {"task": "answers"},
        "run_at": "2026-10-08T10:00:00+01:00",
        "commit": "0" * 40,  # in no history here: its source is not held to a commit
        "source": "made-here",
        "summary": summary,
        "items": [asdict(a) for a in answers],
    }


def test_correctness_is_recomputed_from_the_verdicts_kept_by_item(tmp_path: Path) -> None:
    right = {"correta": 0.5, "parcial": 0.5, "errada": 0.0}
    write(
        tmp_path / "test" / "2026-10-08T1000-x.json",
        answers_run(["correta", "parcial"], right, "test"),
    )
    assert check_results(tmp_path, tmp_path / "no-data") == []

    edited = {"correta": 1.0, "parcial": 0.0, "errada": 0.0}  # a verdict turned by hand
    write(
        tmp_path / "test" / "2026-10-08T1000-x.json",
        answers_run(["correta", "parcial"], edited, "test"),
    )
    assert check_results(tmp_path, tmp_path / "no-data") == [
        "2026-10-08T1000-x.json: its summary is not what its items add up to"
    ]
    run = answers_run(["correta", "parcial"], right, "test")
    run["items"] = [{k: v for k, v in i.items() if k != "verdict"} for i in run["items"]]
    write(tmp_path / "test" / "2026-10-08T1000-x.json", run)
    assert check_results(tmp_path, tmp_path / "no-data") == [
        "2026-10-08T1000-x.json: it reports correctness but keeps no verdicts"
    ]


def test_a_test_run_keeps_scores_by_id_and_nothing_an_item_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lex.eval import results
    from lex.eval.harness import AnswerResult

    (tmp_path / "test.jsonl").write_text('{"id": "ct-0001"}\n', encoding="utf-8")
    answer = AnswerResult(
        "ct-0001",
        "simple",
        False,
        1.0,
        1.0,
        given_recall=1.0,
        cited=["lei-7-2009/238"],
        expected=["lei-7-2009/238"],
        text="Texto da resposta.",
        verdict="correta",
        reason="Diz o essencial.",
        given=["lei-7-2009/238@2009-02-17"],
    )
    monkeypatch.setattr(results, "git_state", lambda: ("abc", False))
    path = results.write("test", "x", {}, {}, [answer], tmp_path, tmp_path)
    [kept] = json.loads(path.read_text(encoding="utf-8"))["items"]
    assert kept == {
        "id": "ct-0001",
        "type": "simple",
        "refused": False,
        "precision": 1.0,
        "recall": 1.0,
        "given_recall": 1.0,
        "version_right": None,
        "verdict": "correta",
        "verdicts": [],
    }


def test_the_leaderboard_runs_on_the_indexed_corpus(tmp_path: Path) -> None:
    index = tmp_path / "index.jsonl"
    row = {"diploma": "lei-7-2009", "article": "238", "valid_from": "2009-02-17"}
    index.write_text(json.dumps(row | {"valid_to": None, "sha256": "x"}) + "\n", "utf-8")
    from lex.bench.corpus_check import index_fingerprint

    current = index_fingerprint(index)
    run = {"bench": {"sha": "b"}, "config": {"corpus": {"fingerprint": current, "versions": {}}}}
    write(tmp_path / "test" / "2026-10-08T1000-a.json", run)
    assert check_results(tmp_path, tmp_path / "no-data", index) == []

    other = {"bench": {"sha": "b"}, "config": {"corpus": {"fingerprint": "old", "versions": {}}}}
    write(tmp_path / "test" / "2026-10-08T1100-b.json", other)
    problems = check_results(tmp_path, tmp_path / "no-data", index)
    assert problems[0].startswith("results/test/ mixes corpora")
    assert problems[1] == "test runs on a corpus other than index.jsonl's: 2026-10-08T1100-b.json"


def test_a_run_is_held_to_the_code_of_the_commit_that_adds_it(tmp_path: Path) -> None:
    import subprocess

    from lex.eval.results import source, source_sha

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.org")
    git("config", "user.name", "t")
    (tmp_path / "src" / "lex").mkdir(parents=True)
    (tmp_path / "src" / "lex" / "a.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "code")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()

    data = tmp_path / "bench"
    data.mkdir()
    (data / "dev.jsonl").write_text('{"id": "ct-0001"}\n', encoding="utf-8")
    from lex.eval.results import bench_version

    run = retrieval_run(0.5) | {
        "bench": bench_version("dev", data),
        "commit": head,
        "run_at": "2026-10-08T10:00:00+01:00",
        "source": source_sha(source(tmp_path)),
    }
    results = tmp_path / "results"
    write(results / "dev" / "bm25.json", run)
    assert check_results(results, data, tmp_path / "none", tmp_path) == []  # uncommitted yet
    git("add", "-A")
    git("commit", "-qm", "run, with the code that made it")
    assert check_results(results, data, tmp_path / "none", tmp_path) == []

    # The code changes, and the run is committed again without being made again.
    (tmp_path / "src" / "lex" / "a.py").write_text("X = 2\n", encoding="utf-8")
    write(results / "dev" / "bm25.json", run | {"run_at": "2026-10-08T11:00:00+01:00"})
    git("add", "-A")
    git("commit", "-qm", "run touched, code changed")
    assert check_results(results, data, tmp_path / "none", tmp_path) == [
        "bm25.json: it was made by code other than the commit's that adds it: run it again"
    ]

    # A run on another version of dev, and one that says nothing of its split.
    write(results / "dev" / "bm25.json", run | {"bench": {"sha": "s", "scored": "old"}})
    old = {k: v for k, v in run.items() if k != "bench"}
    write(results / "dev" / "dense.json", old)
    assert check_results(results, data, tmp_path / "none", tmp_path) == [
        "bm25.json: it ran on another version of dev: run it again, or archive it",
        "dense.json: it records no version of its split: run it again, or archive it",
    ]
