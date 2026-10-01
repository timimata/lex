import dataclasses
import datetime as dt
from pathlib import Path

import pytest

from lex.ingest import dr, pgdl
from lex.ingest.build import CT_IN_FORCE, _start_of, build
from lex.ingest.fetch import Page
from lex.ingest.labels import diploma_id

FIXTURES = Path(__file__).parent / "fixtures"


def page(name: str) -> str:
    return pgdl.decode((FIXTURES / "pgdl" / name).read_bytes())


def dr_excerpt() -> dict[str, dr.Article]:
    return dr.parse_code((FIXTURES / "dr" / "ct_excerpt.txt").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Lei n.º 23/2012, de 25/06", "lei-23-2012"),
        ("Lei n.º 7/2009, de 12 de Fevereiro", "lei-7-2009"),
        ("Rect. n.º 21/2009, de 18/03", "retificacao-21-2009"),
        ("Declaração de Retificação n.º 13/2023", "retificacao-13-2023"),
        ("Declaração de Rectificação n.º 21/2009", "retificacao-21-2009"),
        ("Acórdão do Tribunal Constitucional n.º 338/2010", "acordao-tc-338-2010"),
        ("Decreto Legislativo Regional n.º 23/2021/A", "dlr-23-2021"),
    ],
)
def test_diploma_labels_become_ids(label: str, expected: str) -> None:
    assert diploma_id(label) == expected


@pytest.mark.parametrize(("article_id", "number"), [("1047A0368", "368"), ("1047A0252B", "252-B")])
def test_pgdl_article_ids_become_article_numbers(article_id: str, number: str) -> None:
    assert pgdl.article_number(article_id) == number


def test_a_pgdl_window_yields_its_articles_with_history() -> None:
    articles = {a.article_id: a for a in pgdl.parse_window(page("window_1047A0368.html"))}

    assert "1047A0364" in articles and "1047A0373" in articles
    art = articles["1047A0368"]
    assert art.heading == "Requisitos de despedimento por extinção de posto de trabalho"
    assert art.text.startswith("1 - O despedimento por extinção de posto de trabalho")
    assert art.text.splitlines()[-1].startswith("6 - Constitui contra-ordenação grave")
    assert [diploma_id(label) for label in art.amended_by] == ["lei-23-2012", "lei-27-2014"]
    assert [(r.number, diploma_id(r.introduced_by)) for r in art.old_versions] == [
        (1, "lei-7-2009"),
        (2, "lei-23-2012"),
    ]


def test_pgdl_text_is_cleaned_of_its_quirks() -> None:
    assert (
        pgdl.clean("pelo menos 10 /prct. dos trabalhadores") == "pelo menos 10 % dos trabalhadores"
    )
    assert pgdl.decode(b"5 \x96 (Revogado.)") == f"5 {chr(0x2013)} (Revogado.)"  # en dash


def test_the_article_selector_lists_the_whole_code() -> None:
    ids = pgdl.article_ids(page("window_1047A0368.html"))
    assert len(ids) == 601 and ids[0] == "1047A0001" and "1047A0252B" in ids


def test_an_old_pgdl_version_has_its_text_and_author() -> None:
    first = pgdl.parse_old_version(page("old_1047A0368_v1.html"))
    assert diploma_id(first.introduced_by) == "lei-7-2009"
    assert "a) Menor antiguidade no posto de trabalho;" in first.text.splitlines()


def test_the_dr_page_gives_articles_their_place_dates_and_rulings() -> None:
    articles = dr_excerpt()

    assert articles["1"].heading == "Fontes específicas"  # the code's, not Lei n.º 7/2009's
    assert articles["1"].path[:2] == (
        "Livro I - Parte geral",
        "Título I - Fontes e aplicação do direito do trabalho",
    )
    added = articles["252-B"]
    assert [(n.kind, n.diploma, n.in_force) for n in added.notes] == [
        ("aditado", "lei-32-2025", dt.date(2025, 4, 26))
    ]
    assert added.text.startswith("1 - A trabalhadora que sofra de dores graves")
    assert articles["366-A"].text == ""
    assert [n.kind for n in articles["366-A"].notes] == ["revogado", "aditado"]
    fired = articles["368"]
    assert fired.path[-1] == "Divisão III - Despedimento por extinção de posto de trabalho"
    assert {n.diploma: n.in_force for n in fired.notes} == {
        "lei-27-2014": dt.date(2014, 6, 1),
        "lei-23-2012": dt.date(2012, 8, 1),
    }
    assert fired.rulings and "602/2013" in fired.rulings[0]


def test_a_dr_note_without_a_date_is_a_note_not_text() -> None:
    added = dr_excerpt()["33-A"]
    assert added.text.splitlines()[-1].startswith("3 - Às situações de adoção")
    assert [(n.kind, n.diploma, n.in_force) for n in added.notes] == [
        ("aditado", "lei-90-2019", None)
    ]


def test_missing_dates_are_resolved_only_by_the_stated_rules() -> None:
    resolved: list[str] = []
    notes: dict[str, dt.date | None] = {"lei-13-2023": dt.date(2023, 5, 1), "lei-90-2019": None}
    by_diploma = {"lei-90-2019": dt.date(2019, 10, 4)}

    def start(by: str, article: str = "1") -> dt.date | None:
        return _start_of(by, article, notes, by_diploma, resolved)

    assert start("lei-7-2009") == CT_IN_FORCE
    assert start("lei-13-2023") == dt.date(2023, 5, 1)
    assert start("retificacao-13-2023") == dt.date(2023, 5, 1)
    assert start("lei-90-2019") == dt.date(2019, 10, 4)
    # Lei n.º 90/2019, art. 9.º, n.º 1: article 35.º changed with the 2020 State Budget.
    assert start("lei-90-2019", article="35") == dt.date(2020, 4, 1)
    assert start("lei-99-2099") is None
    assert len(resolved) == 3


def test_build_dates_each_version_from_the_dr() -> None:
    fetched = dt.date(2026, 9, 29)
    window = pgdl.parse_window(page("window_1047A0368.html"))
    current = {
        a.article_id: (a, Page("window-url", b"", fetched))
        for a in window
        if a.article_id == "1047A0368"
    }
    old = {
        ("1047A0368", n): (
            pgdl.parse_old_version(page(f"old_1047A0368_v{n}.html")),
            Page(f"old-url-{n}", b"", fetched),
        )
        for n in (1, 2)
    }
    versions, report = build(current, old, dr_excerpt(), fetched)

    assert report.problems == [] and report.resolved == [] and report.text_mismatches == []
    assert [(v.introduced_by, v.valid_from, v.valid_to) for v in versions] == [
        ("lei-7-2009", CT_IN_FORCE, dt.date(2012, 8, 1)),
        ("lei-23-2012", dt.date(2012, 8, 1), dt.date(2014, 6, 1)),
        ("lei-27-2014", dt.date(2014, 6, 1), None),
    ]
    in_2013 = next(v for v in versions if v.in_force_on(dt.date(2013, 1, 1)))
    assert "a) Pior avaliação de desempenho" not in in_2013.text
    assert versions[-1].source_url == dr.CT_URL  # the current text is the official one
    assert report.rulings["368"]


def test_an_undated_version_cuts_the_history_instead_of_stretching_the_one_before() -> None:
    fetched = dt.date(2026, 9, 29)
    window = pgdl.parse_window(page("window_1047A0368.html"))
    art = next(a for a in window if a.article_id == "1047A0368")
    old = {
        ("1047A0368", n): (
            pgdl.parse_old_version(page(f"old_1047A0368_v{n}.html")),
            Page("", b"", fetched),
        )
        for n in (1, 2)
    }
    fired = dr_excerpt()["368"]
    no_2012_date = dataclasses.replace(
        fired, notes=tuple(n for n in fired.notes if n.diploma != "lei-23-2012")
    )

    versions, report = build(
        {"1047A0368": (art, Page("", b"", fetched))}, old, {"368": no_2012_date}, fetched
    )

    assert [(v.introduced_by, v.valid_from, v.valid_to) for v in versions] == [
        ("lei-27-2014", dt.date(2014, 6, 1), None)
    ]
    assert report.incomplete_history == ["368"] and report.missing_current == []
