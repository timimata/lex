import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from lex.bench import card
from lex.bench.corpus_check import Periods, check_citations, refusals_to_review
from lex.bench.schema import Item
from lex.bench.splits import (
    assign,
    check,
    cross_split_pairs,
    split_for,
)


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
        "modified": "2023-04-30",
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
    periods: Periods = {
        ("lei-7-2009", "238"): [("2009-02-17", "2012-08-01"), ("2012-08-01", None)],
        ("lei-7-2009", "401"): [("2009-02-17", None)],
        ("lei-6-2006", "9"): [("2006-06-27", None)],
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
    tenancy = Item.model_validate(
        make(id="ct-0005", may_cite=[{"diploma": "lei-6-2006", "article": "99"}])
    )  # but every diploma the corpus holds is checked

    problems = check_citations({"test": [good, missing, too_early, elsewhere, tenancy]}, periods)

    assert problems == [
        "test ct-0002: must_cite[0] is not in the corpus",
        "test ct-0003: must_cite[0] has no version in force on as_of",
        "test ct-0005: may_cite[0] is not in the corpus",
    ]
    assert "999" not in "\n".join(problems)


def test_refusals_about_tenancy_are_named_for_review_by_id_only() -> None:
    labour = Item.model_validate(
        make(id="ct-0006", type="unanswerable", must_cite=[], question="Que seguro cobre isto?")
    )
    tenancy = Item.model_validate(
        make(
            id="ct-0007",
            type="unanswerable",
            must_cite=[],
            question="SEGREDO: o senhorio pode aumentar a renda?",
        )
    )

    flagged = refusals_to_review({"test": [labour, tenancy]})

    assert flagged == ["test ct-0007"] and "SEGREDO" not in "\n".join(flagged)


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


def _articles_by_split() -> tuple[str, str]:
    """An article whose group hashes to dev, and one that hashes to test."""
    split = {n: split_for(on_article(n)) for n in range(1, 40)}
    return (
        str(next(n for n, s in split.items() if s == "dev")),
        str(next(n for n, s in split.items() if s == "test")),
    )


def citing(item_id: str, *articles: str, **overrides: Any) -> dict[str, Any]:
    must = [{"diploma": "lei-7-2009", "article": a} for a in articles]
    own = {"url": f"https://example.org/{item_id}", "title": "Fonte", "retrieved": "2026-09-29"}
    fields = {"source": own} | overrides
    return make(id=item_id, question=f"Pergunta {item_id}", must_cite=must, **fields)


def test_an_item_citing_another_main_article_joins_its_group_in_dev(tmp_path: Path) -> None:
    dev_article, test_article = _articles_by_split()
    on_dev = citing("ct-0001", dev_article)
    # Its own main article hashes to test, but it must cite dev's main article: one group.
    linked = citing("ct-0002", test_article, dev_article)
    alone = citing("ct-0003", test_article)
    write(tmp_path / "dev.jsonl", [on_dev])
    write(tmp_path / "test.jsonl", [linked, alone])

    # Since v4 a test item in a group with dev items is a fault; ct-0003 shares ct-0002's group.
    assert check(tmp_path) == [
        "ct-0002 is in test, but its group puts it in dev",
        "ct-0003 is in test, but its group puts it in dev",
    ]
    assert cross_split_pairs(tmp_path) == ["ct-0001 (dev) ~ ct-0002 (test): a must_cite article"]


def test_assign_puts_a_new_item_in_its_group_and_refuses_one_linking_both(
    tmp_path: Path,
) -> None:
    dev_article, test_article = _articles_by_split()
    write(tmp_path / "dev.jsonl", [citing("ct-0001", dev_article)])
    write(tmp_path / "test.jsonl", [citing("ct-0002", test_article)])
    # Main article on test's side, but it must cite dev's: it goes to dev.
    write(tmp_path / "incoming.jsonl", [citing("ct-0003", test_article, dev_article)])
    problems = check(tmp_path)
    assert problems == ["ct-0003 (incoming) links items in dev and in test"]

    write(tmp_path / "incoming.jsonl", [citing("ct-0004", "999", dev_article)])
    assert check(tmp_path) == []
    assert assign(tmp_path) == {"dev": 1}


def test_a_faq_entry_links_its_items_and_a_shared_page_is_only_listed(tmp_path: Path) -> None:
    dev_article, test_article = _articles_by_split()
    entry = {
        "url": "https://portal.act.gov.pt/_api/web/lists/getByTitle('FAQs')/items(7)",
        "title": "ACT",
        "retrieved": "2026-09-29",
        "modified": "2026-09-01",
    }
    page = {"url": "https://example.org/guia", "title": "Guia", "retrieved": "2026-09-29"}
    write(tmp_path / "dev.jsonl", [citing("ct-0001", dev_article, source=entry)])
    earlier = citing("ct-0002", test_article, source=entry, type="temporal", as_of="2011-06-01")
    write(tmp_path / "test.jsonl", [earlier])
    assert check(tmp_path) == ["ct-0002 is in test, but its group puts it in dev"]

    write(tmp_path / "dev.jsonl", [citing("ct-0001", dev_article, source=page)])
    write(tmp_path / "test.jsonl", [citing("ct-0002", test_article, source=page)])
    assert check(tmp_path) == []
    assert cross_split_pairs(tmp_path) == ["ct-0001 (dev) ~ ct-0002 (test): the same page"]


def test_the_leak_scan_catches_rewording_and_an_id_beside_its_article() -> None:
    from lex.bench.snapshot import find_leaks

    secret = Item.model_validate(
        make(
            id="zz-9042",
            question="O trabalhador que perde o filho tem direito a quantos dias de faltas "
            "justificadas?",
            answer="Tem direito a faltar justificadamente até vinte dias consecutivos por "
            "falecimento de filho.",
            must_cite=[{"diploma": "lei-7-2009", "article": "251"}],
        )
    )
    # A dev item: what it shares with the test item is public already, and proves nothing.
    public = Item.model_validate(
        make(
            id="zz-9043",
            question="Quantos dias de faltas justificadas tem o trabalhador que perde o filho?",
            answer="Tem direito a faltar justificadamente até vinte dias consecutivos.",
        )
    )
    texts = {
        "reworded-question.md": "Pergunta-se se o trabalhador que perde o filho tem direito a "
        "quantos dias de faltas justificadas, e com que prova.",
        "reworded-answer.md": "Faltar justificadamente até vinte dias consecutivos por "
        "falecimento de filho: é o que a lei dá.",
        "sheet.md": "| zz-9042 | composto | art. 251.º |",
        "other-article.md": "| zz-9042 | composto | art. 2510.º | art. 251.º-A |",
        "dev-only.md": "Tem direito a faltar justificadamente até vinte dias consecutivos.",
    }
    assert find_leaks(texts, [secret], [public.question, public.answer]) == [
        "reworded-question.md holds test content",
        "reworded-answer.md holds test content",
        "sheet.md holds a test id beside an article it must cite",
    ]


def test_without_the_corpus_validate_checks_citations_against_the_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from lex.bench.__main__ import main

    data, empty = tmp_path / "data", tmp_path / "no-corpus"
    data.mkdir()
    empty.mkdir()
    item = make()  # article 238, asked about 2026-09-29
    write(data / f"{split_for(Item.model_validate(item))}.jsonl", [item])
    index, card_path = tmp_path / "index.jsonl", tmp_path / "card.md"
    card_path.write_text(f"{card.START}\n{card.END}\n", encoding="utf-8")
    card.refresh(card_path, data)
    row = {"diploma": "lei-7-2009", "article": "238", "introduced_by": "lei-7-2009"}
    args = ["validate", "--data-dir", str(data), "--corpus", str(empty), "--index", str(index)]
    args += ["--card", str(card_path)]

    write(index, [row | {"valid_from": "2009-02-17", "valid_to": None, "sha256": "x"}])
    assert main(args) == 0
    write(index, [row | {"valid_from": "2027-01-01", "valid_to": None, "sha256": "x"}])
    assert main(args) == 1
    assert "has no version in force on as_of" in capsys.readouterr().err


def test_a_reviewers_sign_off_changes_the_card_but_not_what_runs_are_compared_by(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from lex.bench.__main__ import main
    from lex.eval.results import bench_version

    item = make()
    split = split_for(Item.model_validate(item))
    write(tmp_path / f"{split}.jsonl", [item, make(id="ct-0002", question="Outra pergunta?")])
    card_path = tmp_path / "card.md"
    card_path.write_text(f"Antes.\n{card.START}\n{card.END}\nDepois.\n", encoding="utf-8")
    card.refresh(card_path, tmp_path)
    before = bench_version(split, tmp_path)
    assert "Validated by a legal reviewer" in card_path.read_text(encoding="utf-8")

    monkeypatch.setattr("builtins.input", lambda prompt: "s")
    args = ["review", "ct-0001", "--by", "Ana Jurista", "--data-dir", str(tmp_path)]
    assert main([*args, "--card", str(card_path)]) == 0
    shown = capsys.readouterr().out
    assert item["question"] in shown and "validado por Ana Jurista" in shown

    signed = Item.model_validate_json(
        (tmp_path / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert (signed.status, signed.validated_by) == ("validated", "Ana Jurista")
    assert signed.validated_on is not None
    after = bench_version(split, tmp_path)
    assert after["sha"] != before["sha"] and after["scored"] == before["scored"]
    text = card_path.read_text(encoding="utf-8")
    assert text.startswith("Antes.") and text.endswith("Depois.\n")
    assert f"1 of the 2 {split} items" in text or "1 of the 2 dev items" in text

    # A correction is what runs are compared by.
    corrected = make(answer="O período anual de férias tem a duração mínima de 25 dias úteis.")
    write(tmp_path / f"{split}.jsonl", [corrected, make(id="ct-0002", question="Outra pergunta?")])
    assert bench_version(split, tmp_path)["scored"] != before["scored"]


def test_a_validated_item_names_who_and_when() -> None:
    with pytest.raises(ValidationError):
        Item.model_validate(make(status="validated", validated_by="Ana Jurista"))
    Item.model_validate(
        make(status="validated", validated_by="Ana Jurista", validated_on="2026-10-08")
    )


def test_a_faq_item_records_its_entrys_date_and_stamp_writes_it(tmp_path: Path) -> None:
    import datetime as dt

    from lex.bench.splits import stamp
    from lex.eval.results import bench_version

    entry = "https://portal.act.gov.pt/_api/web/lists/getByTitle('FAQs')/items(194)"
    item = make(source={"url": entry, "title": "ACT", "retrieved": "2026-09-29"})
    split = split_for(Item.model_validate(item))
    write(tmp_path / f"{split}.jsonl", [item])
    assert any("records no source.modified" in p for p in check(tmp_path))
    before = bench_version(split, tmp_path)["scored"]

    assert (
        stamp(
            {Item.model_validate(item).source.url.unicode_string(): dt.date(2023, 4, 30)}, tmp_path
        )
        == 1
    )
    assert check(tmp_path) == []
    stamped = Item.model_validate_json((tmp_path / f"{split}.jsonl").read_text(encoding="utf-8"))
    assert stamped.source.modified == dt.date(2023, 4, 30)
    assert bench_version(split, tmp_path)["scored"] == before  # nothing a run reads changed


def test_the_cards_faq_line_is_left_out_where_the_faq_is_not(tmp_path: Path) -> None:
    write(tmp_path / f"{split_for(Item.model_validate(make()))}.jsonl", [make()])
    card_path = tmp_path / "card.md"
    card_path.write_text(f"{card.START}\n{card.END}\n", encoding="utf-8")
    faq = tmp_path / "act_faq.jsonl"
    faq.write_text('{"url": "https://example.org/faq", "question": "Outra?"}\n', encoding="utf-8")
    card.refresh(card_path, tmp_path, faq)
    assert card.VERBATIM in card_path.read_text(encoding="utf-8")
    assert card.is_current(card_path, tmp_path, tmp_path / "absent.jsonl")  # CI


def test_the_cards_test_counts_are_left_out_where_the_test_split_is_not(tmp_path: Path) -> None:
    dev_item = next(
        make(id=f"ct-{n:04d}", must_cite=[{"diploma": "lei-7-2009", "article": str(n)}])
        for n in range(1, 500)
        if split_for(
            Item.model_validate(make(must_cite=[{"diploma": "lei-7-2009", "article": str(n)}]))
        )
        == "dev"
    )
    write(tmp_path / "dev.jsonl", [dev_item])
    write(tmp_path / "test.jsonl", [make(id="zz-9001")])
    card_path = tmp_path / "card.md"
    card_path.write_text(f"{card.START}\n{card.END}\n", encoding="utf-8")
    absent = tmp_path / "absent.jsonl"
    card.refresh(card_path, tmp_path, absent)
    (tmp_path / "test.jsonl").unlink()  # the public mirror
    assert card.is_current(card_path, tmp_path, absent)
    write(tmp_path / "dev.jsonl", [dev_item, make(id="ct-0999")])  # a dev count still counts
    assert not card.is_current(card_path, tmp_path, absent)


def test_the_mirror_leaves_out_the_test_split_and_dependabot() -> None:
    from lex.bench.snapshot import tracked

    files = tracked(Path(__file__).resolve().parents[1])
    assert "bench/data/dev.jsonl" in files
    assert "bench/data/test.jsonl" not in files and ".github/dependabot.yml" not in files
