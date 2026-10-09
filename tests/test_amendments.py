from pathlib import Path

import pytest

from lex.ingest import amendments
from lex.ingest.codes import CODES

FIXTURES = Path(__file__).parent / "fixtures" / "pgdl"


def listed(key: str) -> list[str]:
    return amendments.parse((FIXTURES / f"{key}-amendments.html").read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", sorted(CODES))
def test_each_diplomas_list_is_the_one_the_corpus_was_built_with(key: str) -> None:
    assert listed(key) == amendments.known(amendments.known_path(CODES[key]))


def test_the_list_of_amendments_is_read_from_the_real_pages() -> None:
    ct = listed("ct")
    assert ct[0] == "Lei n.º 32/2025, de 27/03"
    assert "Retificação n.º 13/2023, de 29/05" in ct
    assert "Rect. n.º 21/2009, de 18/03" in ct  # abbreviated, and missed until 2026-10-01
    assert ct[-1] == "Lei n.º 7/2009, de 12/02"
    # Older acts have two-digit years, and numbers with letters.
    cc = listed("cc")
    assert "DL n.º 321-B/90, de 15/10" in cc and cc[-1] == "DL n.º 47344/66, de 25/11"
    assert "Rect. n.º 24/2006, de 17/04" in listed("nrau")


def test_a_new_amendment_is_reported_and_a_changed_page_is_an_error() -> None:
    known = ["Lei n.º 32/2025, de 27/03", "Lei n.º 7/2009, de 12/02"]
    current = ["Lei n.º 5/2027, de 10/01", *known]
    assert amendments.new_since(current, known) == ["Lei n.º 5/2027, de 10/01"]
    assert amendments.new_since(known, known) == []
    with pytest.raises(ValueError):
        amendments.parse("<html>nothing here</html>")


def test_an_act_of_a_kind_the_check_cannot_read_fails_it() -> None:
    page = (FIXTURES / "ct-amendments.html").read_text(encoding="utf-8")
    assert amendments.unknown(page) == []
    # A kind no pattern reads, slipped into the list as the page writes its rows.
    odd = (
        '<a  href= "lei_mostra_articulado.php?nid=1&tabela=leis">Resolução n.º 9/2026, de 01/02</a>'
    )
    strange = page.replace("<a  href=", odd + "<br>&nbsp;&nbsp;  - <a  href=", 1)
    assert amendments.unknown(strange) == ["Resolução n.º 9/2026, de 01/02"]
    # Two numberless declarations the Código Civil's page has always listed are read now.
    assert "Declaração de 31/12 de 1986" in listed("cc")


def test_the_drs_own_list_of_amending_acts_is_read() -> None:
    text = "\n".join(
        [
            "Alterações",
            "2025-03-27",
            "Lei n.º 32/2025 - 1.ª Série",
            "Promoção dos direitos das pessoas com endometriose",
            "Ver detalhes das alterações ",
            "2013-10-24",
            "Acórdão do Tribunal Constitucional n.º 602/2013 - 1.ª Série",
            "Declara a inconstitucionalidade",
            "Ver detalhes das alterações ",
        ]
    )
    assert amendments.dr_acts(text) == [
        "2025-03-27 Lei n.º 32/2025",
        "2013-10-24 Acórdão do Tribunal Constitucional n.º 602/2013",
    ]
    for key in sorted(CODES):  # a list kept for each diploma, from the corpus's own render
        assert amendments.known(amendments.dr_known_path(CODES[key]))
