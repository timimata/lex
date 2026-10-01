import datetime as dt

from lex.domain import Citation
from lex.retrieval.hybrid import Hybrid


def cite(article: str) -> Citation:
    return Citation(diploma="lei-7-2009", article=article)


class Fixed:
    def __init__(self, name: str, ranking: list[str]) -> None:
        self.name = name
        self.ranking = [cite(a) for a in ranking]

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        return self.ranking[:k]


def test_rank_fusion_rewards_agreement_between_rankings() -> None:
    hybrid = Hybrid([Fixed("a", ["1", "2", "3"]), Fixed("b", ["2", "4", "5"])])
    # 2 is in both rankings (1/62 + 1/61) and beats 1, first in only one of them (1/61).
    assert hybrid.search("q", dt.date(2026, 9, 30), 5)[:2] == [cite("2"), cite("1")]
    assert set(hybrid.search("q", dt.date(2026, 9, 30), 5)) == {cite(a) for a in "12345"}
    assert hybrid.name == "hybrid-a-b"


def test_ties_keep_the_first_retrievers_order() -> None:
    hybrid = Hybrid([Fixed("a", ["1", "2"]), Fixed("b", ["2", "1"])])
    assert hybrid.search("q", dt.date(2026, 9, 30), 2) == [cite("1"), cite("2")]
