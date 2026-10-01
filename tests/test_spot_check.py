import datetime as dt
from pathlib import Path

import psycopg
import pytest

from lex.ingest import dr
from lex.ingest.spot_check import check_one, compare
from lex.store import db
from lex.store.models import ArticleVersion

AS_OF_2012 = Path(__file__).parent / "fixtures" / "dr" / "ct_as_of_2012-07-31_excerpt.txt"


def test_the_dr_history_view_states_the_period_in_force_apart_from_the_text() -> None:
    article = dr.parse_code(AS_OF_2012.read_text(encoding="utf-8"))["370"]
    assert article.window == (dt.date(2012, 8, 1), dt.date(2019, 9, 30))
    assert article.text.startswith("1 - Nos 10 dias posteriores")


@pytest.mark.parametrize(
    ("store_text", "dr_text", "result"),
    [
        ("1 - Texto igual.", "1 -  Texto igual.", "same"),
        ("4 - (Revogado.)", "4 - (Revogado).", "same"),
        ("a) Alínea;", "a) Alínea.", "punctuation only"),
        ("1 - 22 dias úteis.", "1 - 25 dias úteis.", "differs"),
        ("(Revogado.)", "", "revoked on both"),
    ],
)
def test_texts_are_compared_leniently_only_where_it_is_safe(
    store_text: str, dr_text: str, result: str
) -> None:
    assert compare(store_text, dr_text)[0] == result


def stored(start: dt.date, end: dt.date | None, text: str) -> ArticleVersion:
    return ArticleVersion(
        diploma="lei-7-2009",
        article="370",
        heading="Consultas em caso de despedimento por extinção de posto de trabalho",
        path=[],
        text=text,
        valid_from=start,
        valid_to=end,
        introduced_by="lei-23-2012",
        source_url="https://example.org",
        fetched=dt.date(2026, 9, 29),
    )


def test_a_stated_period_is_checked_against_the_store_dates(conn: psycopg.Connection) -> None:
    shown = dr.parse_code(AS_OF_2012.read_text(encoding="utf-8"))["370"]
    right = stored(dt.date(2012, 8, 1), dt.date(2019, 10, 1), shown.text)
    db.load(conn, [right])
    check = check_one(conn, "lei-7-2009", "370", dt.date(2012, 7, 31), shown)
    assert (check.result, check.stated) == ("same", "2012-08-01 to 2019-09-30")

    db.load(conn, [stored(dt.date(2012, 8, 1), dt.date(2019, 9, 1), shown.text)])
    assert check_one(conn, "lei-7-2009", "370", dt.date(2012, 7, 31), shown).result == (
        "dates differ"
    )
