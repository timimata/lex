import datetime as dt
import io
import json
from pathlib import Path
from typing import Any

import pytest

from lex.bench.schema import Item
from lex.eval.harness import run_answers, summarise_answers
from lex.eval.outside import FileSystem, HttpSystem


def item(item_id: str, article: str, as_of: str = "2026-09-29") -> Item:
    return Item.model_validate(
        {
            "id": item_id,
            "question": f"Pergunta {item_id}?",
            "as_of": as_of,
            "type": "temporal" if as_of < "2026-09-29" else "simple",
            "must_cite": [{"diploma": "lei-7-2009", "article": article}],
            "answer": "Resposta.",
            "source": {"url": "https://example.org", "title": "F", "retrieved": "2026-09-29"},
            "reviewed_by": "test",
        }
    )


def test_a_file_of_answers_is_scored_as_any_system(tmp_path: Path) -> None:
    items = [item("ct-0001", "238"), item("ct-0002", "251", "2011-06-01"), item("ct-0003", "9")]
    rows = [
        {
            "id": "ct-0001",
            "text": "Vinte e dois dias.",
            "refused": False,
            "citations": [{"diploma": "lei-7-2009", "article": "238", "valid_from": "2023-05-01"}],
        },
        {  # today's version, cited for 2011
            "id": "ct-0002",
            "text": "Cinco dias.",
            "refused": False,
            "citations": [{"diploma": "lei-7-2009", "article": "251", "valid_from": "2023-05-01"}],
        },
    ]
    path = tmp_path / "answers.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    system = FileSystem(path, items, name="outro")
    assert system.missing == ["ct-0003"]  # no answer given: scored as a refusal

    periods: dict[tuple[str, str], list[tuple[str, str | None]]] = {
        ("lei-7-2009", "238"): [("2009-02-17", "2023-05-01"), ("2023-05-01", None)],
        ("lei-7-2009", "251"): [("2009-02-17", "2023-05-01"), ("2023-05-01", None)],
    }
    scored = run_answers(items, system, periods)
    assert [(r.recall, r.refused, r.version_right) for r in scored] == [
        (1.0, False, 1.0),
        (1.0, False, 0.0),
        (0.0, True, None),
    ]
    assert summarise_answers(scored)["temporal"]["version_right"] == 0.0


def test_an_endpoint_with_the_demos_contract_is_asked_each_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[dict[str, Any]] = []

    class Reply(io.BytesIO):
        def __enter__(self) -> "Reply":
            return self

        def __exit__(self, *args: object) -> None:
            self.close()

    def urlopen(request: Any, timeout: float) -> Reply:
        asked.append(json.loads(request.data))
        answer = {
            "text": "Sim.",
            "refused": False,
            "citations": [{"diploma": "lei-7-2009", "article": "238"}],
        }
        return Reply(json.dumps({"answer": answer}).encode())

    monkeypatch.setattr("lex.eval.outside.urllib.request.urlopen", urlopen)
    system = HttpSystem("https://outro.example/", name="outro")
    answer = system.answer("Pergunta?", dt.date(2026, 10, 8))
    assert asked == [{"question": "Pergunta?", "as_of": "2026-10-08"}]
    assert answer.citations[0].article == "238" and answer.cited_versions == []


def test_an_endpoint_on_test_needs_its_operators_agreement() -> None:
    from lex.eval import results

    with pytest.raises(SystemExit):
        results.ensure_private("test", {"answers": {"url": "https://x", "tier": "unagreed"}})
    results.ensure_private("test", {"answers": {"url": "https://x", "tier": "agreed"}})
