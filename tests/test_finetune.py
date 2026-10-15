import json
from pathlib import Path

from lex.finetune.__main__ import in_force, parse, prompt


def test_only_articles_in_force_with_text_are_asked_about(tmp_path: Path) -> None:
    rows = [
        {
            "diploma": "lei-7-2009",
            "article": "238",
            "heading": "Férias",
            "text": "1 - " + "x" * 50,
            "valid_to": None,
        },
        {
            "diploma": "lei-7-2009",
            "article": "237",
            "heading": "Antes",
            "text": "y" * 60,
            "valid_to": "2012-08-01",
        },
        {
            "diploma": "lei-7-2009",
            "article": "9",
            "heading": "",
            "text": "(Revogado.)",
            "valid_to": None,
        },
    ]
    (tmp_path / "ct").mkdir()
    (tmp_path / "ct" / "versions.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    assert [r["article"] for r in in_force(tmp_path)] == ["238"]
    assert '<artigo id="lei-7-2009:238">' in prompt(in_force(tmp_path))


def test_a_reply_gives_pairs_only_for_the_articles_asked() -> None:
    rows = [{"diploma": "lei-7-2009", "article": "238"}]
    reply = (
        'Aqui está: [{"id": "lei-7-2009:238", "perguntas": ["Quantos dias de férias?", " "]},'
        ' {"id": "lei-7-2009:999", "perguntas": ["Inventada?"]}]'
    )
    assert parse(reply, rows) == [
        {"question": "Quantos dias de férias?", "article": "lei-7-2009:238"}
    ]
    assert parse("sem JSON", rows) == [] and parse("[{", rows) == []
