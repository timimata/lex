import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from lex.bench.corpus_check import check_citations
from lex.bench.schema import Item
from lex.bench.splits import assign, check, split_for


def make(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": "ct-0001",
        "question": "Quantos dias úteis de férias tem, no mínimo, um trabalhador por ano?",
        "as_of": "2026-09-29",
        "type": "simple",
        "must_cite": [{"diploma": "lei-7-2009", "article": "238"}],
        "answer": "O período anual de férias tem a duração mínima de 22 dias úteis.",
        "source": {"url": "https://example.org/faq", "title": "FAQ", "retrieved": "2026-09-29"},
        "reviewed_by": "Tiago Machado",
    }
    return item | overrides


def write(path: Path, items: list[dict[str, Any]]) -> None:
    lines = (json.dumps(item, ensure_ascii=False) + "\n" for item in items)
    path.write_text("".join(lines), encoding="utf-8")


def test_a_well_formed_item_parses() -> None:
    Item.model_validate(make())


@pytest.mark.parametrize(
    "overrides",
    [
        {"type": "unanswerable"},
        {"must_cite": []},
        {"may_cite": [{"diploma": "lei-7-2009", "article": "238"}]},
        {"status": "validated"},
        {"must_cite": [{"diploma": "Lei 7/2009", "article": "238"}]},
        {"must_cite": [{"diploma": "lei-7-2009", "article": "238.º"}]},
        {"id": "CT-1"},
        {"split": "dev"},
        {"reviewed_by": ""},
    ],
    ids=[
        "unanswerable-with-citations",
        "answerable-without-citations",
        "same-article-must-and-may",
        "validated-by-nobody",
        "diploma-not-a-slug",
        "article-with-ordinal",
        "bad-id",
        "unknown-field",
        "reviewed-by-nobody",
    ],
)
def test_inconsistent_items_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Item.model_validate(make(**overrides))


def test_an_unanswerable_item_cites_nothing() -> None:
    Item.model_validate(make(type="unanswerable", must_cite=[]))


def on_article(n: int, **overrides: Any) -> Item:
    return Item.model_validate(
        make(
            id=f"ct-{n:04d}",
            question=f"Pergunta de teste número {n}",
            must_cite=[{"diploma": "lei-7-2009", "article": str(n)}],
            **overrides,
        )
    )


def test_the_split_is_stable_and_roughly_even() -> None:
    items = [on_article(n) for n in range(1, 1001)]
    assert [split_for(i) for i in items] == [split_for(i) for i in items]
    assert 0.4 < sum(split_for(i) == "test" for i in items) / len(items) < 0.6


def test_items_about_the_same_article_always_share_a_split() -> None:
    splits = {
        split_for(
            Item.model_validate(make(id=f"ct-{n:04d}", question=f"Pergunta {n} sobre férias"))
        )
        for n in range(1, 50)
    }
    assert len(splits) == 1  # all cite article 238 first
    unanswerable = [
        Item.model_validate(make(id=f"ct-{n:04d}", type="unanswerable", must_cite=[]))
        for n in range(1, 50)
    ]
    assert {split_for(i) for i in unanswerable} == {"dev", "test"}  # grouped by id instead


def test_assign_moves_every_item_to_its_split(tmp_path: Path) -> None:
    items = [on_article(n).model_dump(mode="json") for n in range(1, 21)]
    write(tmp_path / "incoming.jsonl", items)

    moved = assign(tmp_path)

    assert moved["dev"] + moved["test"] == 20
    assert (tmp_path / "incoming.jsonl").read_text(encoding="utf-8") == ""
    for split in ("dev", "test"):
        lines = (tmp_path / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()
        assert all(split_for(Item.model_validate_json(line)) == split for line in lines)
    assert check(tmp_path) == []


def test_check_catches_an_item_in_the_wrong_split(tmp_path: Path) -> None:
    item = make()
    wrong = "dev" if split_for(Item.model_validate(item)) == "test" else "test"
    write(tmp_path / f"{wrong}.jsonl", [item])
    assert check(tmp_path)


def test_as_of_follows_the_item_type() -> None:
    with pytest.raises(ValidationError):  # not temporal, but about another day
        Item.model_validate(make(as_of="2020-01-01"))
    with pytest.raises(ValidationError):  # temporal, but about the day it was written
        Item.model_validate(make(type="temporal"))
    Item.model_validate(make(type="temporal", as_of="2020-01-01"))


def test_check_catches_a_question_repeated_under_another_id(tmp_path: Path) -> None:
    first, second = make(id="ct-0001"), make(id="ct-0002", question=make()["question"].upper())
    write(tmp_path / "incoming.jsonl", [first, second])
    assert any("repeats" in p for p in check(tmp_path))


def test_check_catches_an_faq_entry_asked_twice_about_the_present(tmp_path: Path) -> None:
    entry = {
        "url": "https://portal.act.gov.pt/_api/web/lists/getByTitle('FAQs')/items(194)",
        "title": "ACT, Perguntas Frequentes",
        "retrieved": "2026-09-29",
    }
    first = make(id="ct-0001", source=entry)
    # Written another day, about the present again: the same question.
    reworded = make(
        id="ct-0002",
        source=entry | {"retrieved": "2026-10-01"},
        question="Quantos dias de férias há por ano?",
        as_of="2026-10-01",
    )
    earlier = make(
        id="ct-0003", source=entry, question="E em 2011?", type="temporal", as_of="2011-06-01"
    )
    write(tmp_path / "incoming.jsonl", [first, reworded, earlier])

    assert [p for p in check(tmp_path) if "FAQ entry" in p] == [
        "ct-0002 comes from the same FAQ entry, about the same date, as ct-0001"
    ]


def test_check_catches_an_id_in_two_files(tmp_path: Path) -> None:
    item = make()
    write(tmp_path / f"{split_for(Item.model_validate(item))}.jsonl", [item])
    write(tmp_path / "incoming.jsonl", [make(question="Outra pergunta qualquer sobre férias")])
    assert any("both" in p for p in check(tmp_path))


def test_problems_never_echo_item_content(tmp_path: Path) -> None:
    secret = make(
        id="ct-0003",
        question="SEGREDO do conjunto de teste",
        answer="SEGREDO",
        must_cite=[{"diploma": "SEGREDO", "article": "238"}],
    )
    write(tmp_path / "test.jsonl", [secret])
    problems = check(tmp_path)
    assert problems
    assert "SEGREDO" not in "\n".join(problems)


def test_citations_are_checked_against_the_corpus_without_naming_the_article() -> None:
    periods: dict[str, list[tuple[str, str | None]]] = {
        "238": [("2009-02-17", "2012-08-01"), ("2012-08-01", None)],
        "401": [("2009-02-17", None)],
    }
    good = Item.model_validate(make())
    missing = Item.model_validate(
        make(id="ct-0002", must_cite=[{"diploma": "lei-7-2009", "article": "999"}])
    )
    too_early = Item.model_validate(
        make(id="ct-0003", type="temporal", as_of="2008-06-01")
    )  # before the code existed
    elsewhere = Item.model_validate(
        make(id="ct-0004", may_cite=[{"diploma": "lei-23-2012", "article": "10"}])
    )  # other diplomas are outside the corpus by design

    problems = check_citations({"test": [good, missing, too_early, elsewhere]}, periods)

    assert problems == [
        "test ct-0002: must_cite[0] is not in the corpus",
        "test ct-0003: must_cite[0] has no version in force on as_of",
    ]
    assert "999" not in "\n".join(problems)


def test_a_snapshot_is_refused_while_a_file_holds_test_content_or_a_key() -> None:
    from lex.bench.snapshot import find_leaks

    secret = Item.model_validate(make())
    texts = {
        "docs/example.md": f"Por exemplo: «{secret.question}»",
        "notes.txt": "chave AIza" + "x" * 35,
        "README.md": "Nada a esconder aqui.",
    }

    assert find_leaks(texts, [secret]) == [
        "docs/example.md holds test content",
        "notes.txt holds a string shaped like an API key",
    ]
    assert find_leaks({"README.md": "Nada a esconder aqui."}, [secret]) == []


def test_the_dataset_folder_has_the_card_dev_and_the_licence(tmp_path: Path) -> None:
    from lex.bench.snapshot import ADR, ADR_ONLINE, dataset

    public = tmp_path / "public"
    (public / "bench" / "data").mkdir(parents=True)
    (public / "bench" / "DATASET_CARD.md").write_text("license: cc-by-4.0", encoding="utf-8")
    (public / "bench" / "data" / "dev.jsonl").write_text("{}", encoding="utf-8")
    (public / "bench" / "LICENSE.md").write_text(f"See [ADR 0016]({ADR}).", encoding="utf-8")
    hf = tmp_path / "hf"

    dataset(public, hf)

    files = sorted(p.relative_to(hf).as_posix() for p in hf.rglob("*.*"))
    assert files == ["LICENSE.md", "README.md", "data/dev.jsonl"]
    assert ADR_ONLINE in (tmp_path / "hf" / "LICENSE.md").read_text(encoding="utf-8")
    assert "test.jsonl" not in files
