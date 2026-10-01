from pathlib import Path

import pytest

from lex.ingest import amendments

FIXTURE = Path(__file__).parent / "fixtures" / "pgdl" / "ct-amendments.html"


def test_the_list_of_amendments_is_read_from_the_real_page() -> None:
    found = amendments.parse(FIXTURE.read_text(encoding="utf-8"))
    assert found[0] == "Lei n.º 32/2025, de 27/03"
    assert "Retificação n.º 13/2023, de 29/05" in found
    assert found[-1] == "Lei n.º 7/2009, de 12/02"
    assert found == amendments.known()  # the list the corpus was built with


def test_a_new_amendment_is_reported_and_a_changed_page_is_an_error() -> None:
    known = ["Lei n.º 32/2025, de 27/03", "Lei n.º 7/2009, de 12/02"]
    current = ["Lei n.º 5/2027, de 10/01", *known]
    assert amendments.new_since(current, known) == ["Lei n.º 5/2027, de 10/01"]
    assert amendments.new_since(known, known) == []
    with pytest.raises(ValueError):
        amendments.parse("<html>nothing here</html>")
