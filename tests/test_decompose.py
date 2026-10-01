import datetime as dt
import json
from dataclasses import dataclass

from lex.domain import Citation
from lex.retrieval.decompose import Decomposed, parts

TODAY = dt.date(2026, 10, 1)


def cite(article: str) -> Citation:
    return Citation(diploma="lei-7-2009", article=article)


@dataclass(frozen=True)
class Reply:
    text: str


class Scripted:
    name = "scripted"

    def __init__(self, found: list[str]) -> None:
        self.reply = json.dumps({"partes": found})
        self.asked: list[str] = []

    def complete(self, system: str, user: str) -> Reply:
        self.asked.append(user)
        return Reply(self.reply)


class ByQuery:
    """A retriever with a set ranking per query."""

    name = "by-query"
    RANKINGS = {  # noqa: RUF012
        "whole": ["244", "237", "238"],
        "férias suspensas": ["244", "241", "242"],
        "falta por falecimento": ["251", "249", "250"],
    }

    def __init__(self) -> None:
        self.searched: list[str] = []

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        self.searched.append(question)
        return [cite(a) for a in self.RANKINGS.get(question, [])[:k]]


def test_parts_are_searched_and_interleaved_after_the_whole_question() -> None:
    base = ByQuery()
    retriever = Decomposed(base, Scripted(["férias suspensas", "falta por falecimento"]))

    assert retriever.name == "by-query+decomp"
    assert retriever.search("whole", TODAY, 5) == [
        cite("244"),  # first of the whole question (and of a part: kept once)
        cite("251"),  # first of the second part, found by no other ranking this high
        cite("237"),
        cite("241"),
        cite("249"),
    ]
    assert base.searched == ["whole", "férias suspensas", "falta por falecimento"]


def test_a_question_kept_whole_is_searched_as_before() -> None:
    base = ByQuery()
    assert Decomposed(base, Scripted(["whole"])).search("whole", TODAY, 3) == [
        cite("244"),
        cite("237"),
        cite("238"),
    ]
    assert base.searched == ["whole"]
    assert Decomposed(ByQuery(), Scripted([])).search("whole", TODAY, 1) == [cite("244")]


def test_parts_are_read_from_whatever_the_model_wraps_them_in() -> None:
    assert parts('```json\n{"partes": ["a", " b ", "a", ""]}\n```') == ["a", "b"]
    assert parts("sem JSON") == []
    assert parts('{"partes": "não é lista"}') == []
