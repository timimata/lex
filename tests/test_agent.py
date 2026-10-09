import datetime as dt
import json
from dataclasses import dataclass
from typing import Any

import pytest

from lex.domain import Citation
from lex.generation.agent import AGENT_SYSTEM, AgentSystem, BudgetTimeout
from lex.generation.answer import CLAIMS_SYSTEM
from lex.generation.llm import Completion

TODAY = dt.date(2026, 10, 1)


def cite(article: str, diploma: str = "lei-7-2009") -> Citation:
    return Citation(diploma=diploma, article=article)


@dataclass(frozen=True)
class Version:
    heading: str
    text: str
    valid_from: dt.date


SINCE = dt.date(2009, 2, 17)
LAW = {
    cite("244"): Version("Alteração do período de férias", "Suspensão das férias.", SINCE),
    cite("251"): Version("Faltas por motivo de falecimento", "Até cinco dias.", SINCE),
    cite("238"): Version("Duração do período de férias", "22 dias úteis.", SINCE),
    cite("9", "lei-6-2006"): Version("Forma da comunicação", "Escrito.", SINCE),
}


def articles(citation: Citation, as_of: dt.date) -> Version | None:
    return LAW.get(citation)


class Ranked:
    """Retrieves 244 for the question; a search on deaths finds 251, others nothing new."""

    name = "ranked"

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        self.queries.append(question)
        if "falecimento" in question:
            return [cite("251"), cite("244")][:k]
        return [cite("244")][:k]


class Scripted:
    """Replies in turn with the given texts, and remembers what it was asked."""

    name = "scripted"

    def __init__(self, *replies: str) -> None:
        self.params: dict[str, Any] = {}
        self.replies = list(replies)
        self.asked: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> Completion:
        self.asked.append((system, user))
        return Completion(self.replies.pop(0), prompt_tokens=100, completion_tokens=20)


def claims(*sentences: tuple[str, list[str]]) -> str:
    return json.dumps(
        {"frases": [{"texto": t, "artigos": a} for t, a in sentences], "recusa": False}
    )


QUESTION = "Se o pai de um trabalhador morrer durante as férias, as férias ficam suspensas?"


def test_an_answer_straight_away_is_the_demos_answer() -> None:
    model = Scripted(claims(("As férias suspendem-se.", ["CT 244"])))
    system = AgentSystem(Ranked(), articles, model)

    answer = system.answer(QUESTION, TODAY)

    assert system.name == "ranked+scripted+agent"
    assert answer.citations == [cite("244")] and len(model.asked) == 1
    system_prompt, user = model.asked[0]
    assert system_prompt == AGENT_SYSTEM.replace("{pedidos}", "3")
    assert "Pedidos já feitos" not in user and answer.requests == []
    assert set(answer.timings) == {"retrieval", "generation"}


def test_a_search_adds_the_missing_article_for_the_answer_to_cite() -> None:
    retriever = Ranked()
    model = Scripted(
        json.dumps({"acao": "pesquisar", "consulta": "faltas por falecimento de pai"}),
        claims(
            ("As férias suspendem-se.", ["CT 244"]),
            ("O trabalhador pode faltar até cinco dias.", ["CT 251"]),
        ),
    )
    system = AgentSystem(retriever, articles, model)

    answer = system.answer(QUESTION, TODAY)

    assert answer.citations == [cite("244"), cite("251")]
    assert retriever.queries == [QUESTION, "faltas por falecimento de pai"]
    _, second = model.asked[1]
    assert 'id="CT 251"' in second
    assert "pesquisar «faltas por falecimento de pai»: CT 251" in second  # 244 was given
    assert answer.requests == ["pesquisar «faltas por falecimento de pai»: CT 251"]
    assert system.counts["searches"] == 1 and system.counts["added"] == 1


def test_a_read_adds_articles_by_id_and_a_bare_number_by_the_question() -> None:
    model = Scripted(
        json.dumps({"acao": "ler", "artigos": ["CT 238", "999"]}),
        claims(("São 22 dias úteis.", ["CT 238"]), ("Sem apoio.", ["CT 999"])),
    )
    system = AgentSystem(Ranked(), articles, model)

    answer = system.answer(QUESTION, TODAY)

    assert answer.citations == [cite("238")]  # 999 exists nowhere: neither read nor cited
    assert "ler CT 238, 999: CT 238" in model.asked[1][1]
    assert system.counts["dropped_sentences"] == 1

    # A bare number goes to the diploma the question speaks of: here, tenancy.
    tenancy = Scripted(
        json.dumps({"acao": "ler", "artigos": ["9"]}),
        claims(("Por escrito.", ["NRAU 9"])),
    )
    answer = AgentSystem(Ranked(), articles, tenancy).answer(
        "Como se comunica com o senhorio?", TODAY
    )
    assert answer.citations == [cite("9", "lei-6-2006")]


def test_after_its_requests_the_model_must_answer() -> None:
    search = json.dumps({"acao": "pesquisar", "consulta": "férias"})
    model = Scripted(search, search, claims(("As férias suspendem-se.", ["CT 244"])))
    system = AgentSystem(Ranked(), articles, model, steps=2)

    answer = system.answer(QUESTION, TODAY)

    assert [s for s, _ in model.asked] == [
        AGENT_SYSTEM.replace("{pedidos}", "2"),
        AGENT_SYSTEM.replace("{pedidos}", "1"),
        CLAIMS_SYSTEM,  # no more requests: the plain per-sentence task
    ]
    assert "nada de novo" in model.asked[2][1]
    assert answer.citations == [cite("244")]


def test_a_reply_that_is_neither_request_nor_answer_is_a_refusal() -> None:
    model = Scripted("Não sei.")
    system = AgentSystem(Ranked(), articles, model)
    assert system.answer(QUESTION, TODAY).refused
    assert system.counts["malformed"] == 1


def test_past_its_budget_a_request_is_not_followed_and_the_answer_fails() -> None:
    model = Scripted(json.dumps({"acao": "pesquisar", "consulta": "falecimento"}))
    system = AgentSystem(Ranked(), articles, model, steps=1, budget=0.0)

    with pytest.raises(BudgetTimeout):
        system.answer(QUESTION, TODAY)
    assert len(model.asked) == 1 and system.counts["over_budget"] == 1
