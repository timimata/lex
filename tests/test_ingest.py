import dataclasses
import datetime as dt
from pathlib import Path

import pytest

from lex.ingest import dr, pgdl
from lex.ingest.build import CT_IN_FORCE, _start_of, build
from lex.ingest.codes import CC, NRAU, Code
from lex.ingest.fetch import Page
from lex.ingest.labels import diploma_id

FIXTURES = Path(__file__).parent / "fixtures"


def page(name: str) -> str:
    return pgdl.decode((FIXTURES / "pgdl" / name).read_bytes())


def dr_excerpt() -> dict[str, dr.Article]:
    return dr.parse_code((FIXTURES / "dr" / "ct_excerpt.txt").read_text(encoding="utf-8"))


def dr_page(name: str, code: Code) -> dict[str, dr.Article]:
    text = (FIXTURES / "dr" / name).read_text(encoding="utf-8")
    return dr.parse_code(text, code.start, code.stop, code.quotes)


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
        ("DL n.º 47344/66, de 25/11", "dl-47344-1966"),
        ("Decreto-Lei n.º 321-B/90, de 15/10", "dl-321-b-1990"),  # not DL n.º 321/90
        ("Decreto-Lei n.º 329-A/95 (1.ª Parte)", "dl-329-a-1995"),
        ("Declaração de Rectificação n.º 20-AS/2001", "retificacao-20-as-2001"),
        ("Lei n.º 24-D/2022, de 30/12", "lei-24-d-2022"),
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


def test_the_civil_code_page_reads_old_journals_and_rulings() -> None:
    articles = dr_page("cc_excerpt.txt", CC)

    # Decreto-Lei n.º 47344's own articles, which come first, are not the code's.
    assert list(articles) == ["1", "2", "1022", "1023", "1024", "1083", "1084", "1091", "1605"]
    fired = articles["1083"]
    assert fired.path[-3:] == (
        "Secção VII - Arrendamento de prédios urbanos",
        "Subsecção IV - Cessação",
        "Divisão III - Resolução",
    )
    # Revoked by the RAU in a 1990 supplement, with no date; restored by the NRAU in Série I-A.
    assert [(n.kind, n.diploma, n.in_force) for n in fired.notes][-3:] == [
        ("alterado", "lei-6-2006", dt.date(2006, 6, 27)),
        ("revogado", "dl-321-b-1990", None),
        ("alterado", "lei-46-1985", dt.date(1985, 9, 21)),
    ]
    assert [(n.kind, n.diploma) for n in articles["1605"].notes][2:] == [
        ("alterado", "dl-561-1976"),
        ("retificado", "retificacao-dg-236-1975"),  # numbered by its Diário do Governo issue
        ("retificado", "retificacao-dg-141-1975"),
        ("alterado", "dl-261-1975"),
    ]
    ruling = articles["1091"].rulings[0]  # on part III of the ruling's decision
    assert ruling.startswith("III, Acórdão do Tribunal Constitucional n.º 299/2020 - Diário")
    assert articles["2"].rulings[0].startswith("Acórdão n.º 743/96 - Diário da República")
    assert articles["2"].text == "" and articles["2"].notes[0].diploma == "dl-329-a-1995"


def test_an_amending_law_quotes_other_articles_without_taking_their_numbers() -> None:
    articles = dr_page("nrau_excerpt.txt", NRAU)

    # Not the Código Civil's 1024.º that art. 2.º quotes, nor the 1022.º the annex republishes.
    assert list(articles) == ["1", "2", "8", "9", "12", "15", "65"]
    quoting = articles["2"].text.splitlines()
    assert "«Artigo 1024.º" in quoting and quoting[-1] == "d) ...»"
    assert articles["65"].text.splitlines()[-1] == (
        "2 - As restantes disposições entram em vigor 120 dias após a sua publicação."
    )  # and not the signatures after it
    assert ("retificado", "retificacao-24-2006", dt.date(2006, 6, 28)) in [
        (n.kind, n.diploma, n.in_force) for n in articles["12"].notes
    ]
    assert articles["15"].remarks == (
        "Artigo 54.º, Lei n.º 56/2023 - Diário da República n.º 194/2023, Série I de 2023-10-06"
        " As alterações produzidas no n.º 7 do presente artigo, produzem efeitos no dia 3.2.2024.",
    )


def test_each_code_dates_its_own_text_and_its_corrections() -> None:
    resolved: list[str] = []

    def start(by: str, article: str, noted: dt.date | None, code: Code) -> dt.date | None:
        return _start_of(by, article, {by: noted}, {}, resolved, code)

    assert start("lei-6-2006", "9", None, NRAU) == dt.date(2006, 6, 27)  # 120 days after
    assert start("lei-6-2006", "63", None, NRAU) == dt.date(2006, 2, 28)  # the next day
    # The DR's own notes, where they are wrong, give way to the corrections in codes.py.
    assert start("retificacao-24-2006", "12", dt.date(2006, 6, 28), NRAU) == dt.date(2006, 6, 27)
    assert start("lei-6-2006", "1073", dt.date(2007, 6, 27), CC) == dt.date(2006, 6, 27)
    assert start("lei-6-2006", "1074", dt.date(2006, 6, 27), CC) == dt.date(2006, 6, 27)
    assert start("dl-47344-1966", "1022", None, CC) == dt.date(1967, 6, 1)
    assert [r.split(":")[0] for r in resolved] == ["63", "12", "1073"]


def _nrau_9() -> tuple[
    dict[str, tuple[pgdl.Article, Page]],
    dict[tuple[str, int], tuple[pgdl.OldVersion, Page]],
    dr.Article,
]:
    """The NRAU's art. 9.º as the two sources tell it, with short stand-in texts: the PGDL
    credits the 2012 text to Lei n.º 79/2014, which republished the whole law, while the DR
    lists Leis n.os 31/2012 and 43/2017 as the article's only changes."""
    day = dt.date(2026, 10, 1)
    article = pgdl.Article(
        article_id="691A0009",
        heading="Forma da comunicação",
        text="1 - Texto de 2017.",
        added_by=None,
        amended_by=("Lei n.º 31/2012, de 14/08", "Lei n.º 43/2017, de 14/06"),
        old_versions=(
            pgdl.OldVersionRef(1, "Lei n.º 6/2006, de 27/02"),
            pgdl.OldVersionRef(3, "Lei n.º 79/2014, de 19/12"),
        ),
    )
    old = {
        ("691A0009", n): (pgdl.OldVersion("Forma da comunicação", text, by), Page("", b"", day))
        for n, text, by in [
            (1, "1 - Texto de 2006.", "Lei n.º 6/2006, de 27/02"),
            (3, "1 - Texto de 2012.", "Lei n.º 79/2014, de 19/12"),
        ]
    }
    reference = dr.Article(
        article="9",
        heading="Forma da comunicação",
        text="1 - Texto de 2017.",
        path=(),
        notes=(  # newest first, as on the page
            dr.Note("alterado", "lei-43-2017", dt.date(2017, 6, 14), dt.date(2017, 6, 15)),
            dr.Note("alterado", "lei-31-2012", dt.date(2012, 8, 14), dt.date(2012, 11, 12)),
        ),
        rulings=(),
    )
    return {"691A0009": (article, Page("", b"", day))}, old, reference


def test_texts_the_pgdl_credits_to_a_republication_are_credited_as_the_dr_lists() -> None:
    current, old, reference = _nrau_9()
    versions, report = build(current, old, {"9": reference}, dt.date(2026, 10, 1), NRAU)

    assert [(v.introduced_by, v.valid_from, v.valid_to, v.text) for v in versions] == [
        ("lei-6-2006", dt.date(2006, 6, 27), dt.date(2012, 11, 12), "1 - Texto de 2006."),
        ("lei-31-2012", dt.date(2012, 11, 12), dt.date(2017, 6, 15), "1 - Texto de 2012."),
        ("lei-43-2017", dt.date(2017, 6, 15), None, "1 - Texto de 2017."),
    ]
    assert report.problems == [] and [r.split(":")[0] for r in report.relabelled] == ["9"]


def test_a_change_the_pgdl_lacks_cuts_the_history_before_it() -> None:
    """The Código Civil's art. 1080.º: revoked in 1975 and restored by the NRAU in 2006, but the
    PGDL goes from the 1966 text straight to the 2006 one."""
    day = dt.date(2026, 10, 1)
    article = pgdl.Article(
        article_id="775A1080",
        heading="Efeitos da cessação",
        text="Texto de 2012.",
        added_by=None,
        amended_by=("Lei n.º 6/2006, de 27/02", "Lei n.º 31/2012, de 14/08"),
        old_versions=(
            pgdl.OldVersionRef(1, "DL n.º 47344/66, de 25/11"),
            pgdl.OldVersionRef(2, "Lei n.º 6/2006, de 27/02"),
        ),
    )
    old = {
        ("775A1080", n): (pgdl.OldVersion("Efeitos da cessação", text, by), Page("", b"", day))
        for n, text, by in [
            (1, "Texto de 1966.", "DL n.º 47344/66, de 25/11"),
            (2, "Texto de 2006.", "Lei n.º 6/2006, de 27/02"),
        ]
    }
    reference = dr.Article(
        article="1080",
        heading="Efeitos da cessação",
        text="Texto de 2012.",
        path=(),
        notes=(
            dr.Note("alterado", "lei-31-2012", dt.date(2012, 8, 14), dt.date(2012, 11, 12)),
            dr.Note("alterado", "lei-6-2006", dt.date(2006, 2, 27), dt.date(2006, 6, 27)),
            dr.Note("revogado", "dl-201-1975", dt.date(1975, 4, 15), dt.date(1975, 4, 30)),
        ),
        rulings=(),
    )

    versions, report = build(
        {"775A1080": (article, Page("", b"", day))}, old, {"1080": reference}, day, CC
    )

    # Not the 1966 text from 1967 to 2006: it was revoked from 1975.
    assert [(v.introduced_by, v.valid_from, v.valid_to) for v in versions] == [
        ("lei-6-2006", dt.date(2006, 6, 27), dt.date(2012, 11, 12)),
        ("lei-31-2012", dt.date(2012, 11, 12), None),
    ]
    assert report.incomplete_history == ["1080"] and report.problems == []
    assert [g.split(":")[0] for g in report.gaps] == ["1080"]


def test_when_the_sources_agree_on_nothing_only_the_current_text_is_kept() -> None:
    current, old, reference = _nrau_9()
    other = dr.Note("alterado", "lei-56-2023", dt.date(2023, 10, 6), dt.date(2023, 10, 7))
    disagreeing = dataclasses.replace(reference, notes=(other,))
    versions, report = build(current, old, {"9": disagreeing}, dt.date(2026, 10, 1), NRAU)

    # The DR's text, credited to the change the DR names, and nothing the PGDL dated otherwise.
    assert [(v.introduced_by, v.valid_from, v.valid_to) for v in versions] == [
        ("lei-56-2023", dt.date(2023, 10, 7), None)
    ]
    assert report.incomplete_history == ["9"] and len(report.problems) == 1


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


def test_the_drs_notes_go_with_the_versions_they_concern() -> None:
    import datetime as dt

    from lex.ingest import dr
    from lex.ingest.build import attach_notes
    from lex.ingest.codes import CT
    from lex.store.models import ArticleVersion

    def version(start: str, end: str | None, by: str) -> ArticleVersion:
        return ArticleVersion(
            diploma="lei-7-2009",
            article="368",
            heading="H",
            path=[],
            text=f"Texto de {by}.",
            valid_from=dt.date.fromisoformat(start),
            valid_to=dt.date.fromisoformat(end) if end else None,
            introduced_by=by,
            source_url="u",
            fetched=dt.date(2026, 9, 29),
        )

    versions = [
        version("2009-02-17", "2012-08-01", "lei-7-2009"),
        version("2012-08-01", "2014-06-01", "lei-23-2012"),
        version("2014-06-01", None, "lei-27-2014"),
    ]
    ruling = (
        "Acórdão do Tribunal Constitucional n.º 602/2013 - Diário da República n.º 206/2013, "
        "Série I de 2013-10-24 Declarada a inconstitucionalidade"
    )
    remark = (
        "Artigo 9.º, Lei n.º 27/2014 - Diário da República n.º 87/2014, Série I de 2014-05-08 "
        "Produz efeitos mais tarde."
    )
    reference = {"368": dr.Article("368", "H", "", (), (), (ruling,), (remark,))}
    noted = attach_notes(versions, reference, CT)
    # The ruling with the version in force the day it was published; the remark with the
    # version its diploma introduced.
    assert [v.notes for v in noted] == [[], [ruling], [remark]]
