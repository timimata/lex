"""The agent (Phase 7): the demo's per-sentence answer, after the model has asked for the articles
it found missing.

A composite question needs several articles, and retrieval tends to find the first and miss the
second; deciding the parts before reading anything, or following every cross-reference, did not
help on dev (ROADMAP, Phase 4). Here the model reads what was retrieved and may ask, a few times,
for more: a search on a subject it names, or articles by id (those the given ones refer to). Then
it answers as the demo does, a citation per sentence, from the articles it was given and those it
asked for, and nothing else. Every call goes through the same model, cache and rules as the
reference system; the loop is a few lines, no framework (CLAUDE.md).
"""

import datetime as dt
import time

from lex.domain import Answer, Citation, Retriever
from lex.generation.answer import (
    CLAIMS_SYSTEM,
    Articles,
    K,
    Version,
    article_id,
    cited_articles,
    claims_answer,
    first_object,
    prompt,
    read,
    refusal,
)
from lex.generation.llm import Completion, Llm, spent
from lex.retrieval.references import diplomas_for

STEPS = 3  # requests the model may make before it must answer; set, not tuned
PER_SEARCH = 3  # new articles a search adds, at most


class BudgetTimeout(Exception):
    """The answer would outlast the caller's time (the demo's): a failure, not an answer, so the
    API answers 503, gives the visitor's admission back and caches nothing (ROADMAP, Phase 11).
    Its name says Timeout, which is how the API tells the visitor it took too long."""


AGENT_SYSTEM = CLAIMS_SYSTEM.replace(
    "\n\nRegras:\n",
    """

Antes de responder, vê se os artigos dados cobrem todas as partes da pergunta. Se faltar um \
artigo, podes pedir mais, com um destes objetos JSON e nada mais:
{"acao": "pesquisar", "consulta": "..."}: procura artigos sobre um assunto; escreve a consulta \
com as palavras que a lei usaria;
{"acao": "ler", "artigos": ["CT 238"]}: lê artigos pelo id, por exemplo os que um artigo dado \
refere.
Podes fazer até {pedidos} pedidos. Quando os artigos bastarem, ou se nenhum pedido ajudar, \
responde.

Regras:
""",
)


def agent_prompt(
    question: str,
    as_of: dt.date,
    given: list[tuple[Citation, Version]],
    asked: list[str],
) -> str:
    """The reference system's prompt, with what the model has already asked for."""
    base = prompt(question, as_of, given)
    if not asked:
        return base
    done = "\n".join(f"- {line}" for line in asked)
    return f"{base}\n\nPedidos já feitos:\n{done}"


def _action(reply: str) -> tuple[str, list[str]] | None:
    """A request in the reply: ("pesquisar", [query]) or ("ler", [ids]); None if the reply is an
    answer, or not a request it can read."""
    if first_object(reply, "frases") is not None:
        return None
    data = first_object(reply, "acao")
    if data is None:
        return None
    if data["acao"] == "pesquisar" and isinstance(data.get("consulta"), str):
        query = str(data["consulta"]).strip()
        return ("pesquisar", [query]) if query else None
    articles = data.get("artigos")
    if data["acao"] == "ler" and isinstance(articles, list):
        return "ler", [str(a) for a in articles][:PER_SEARCH]
    return None


class AgentSystem:
    def __init__(
        self,
        retriever: Retriever,
        articles: Articles,
        llm: Llm,
        k: int = K,
        steps: int = STEPS,
        budget: float | None = None,  # seconds after which a request is not followed
    ) -> None:
        self.retriever = retriever
        self.articles = articles
        self.llm = llm
        self.k = k
        self.steps = steps
        self.budget = budget
        self.name = f"{retriever.name}+{llm.name}+agent"
        self.counts = {
            "malformed": 0,
            "uncited": 0,
            "dropped_citations": 0,
            "dropped_sentences": 0,
            "searches": 0,
            "reads": 0,
            "added": 0,  # articles the requests added to what the model reads
            "over_budget": 0,  # requests not followed: the answer would come too late
        }

    def answer(self, question: str, as_of: dt.date) -> Answer:
        """The answer, with the seconds spent retrieving (searches included) and generating."""
        seconds = {"retrieval": 0.0, "generation": 0.0}
        calls: list[Completion] = []

        def timed(stage: str, started: float) -> None:
            seconds[stage] += time.perf_counter() - started

        started = time.perf_counter()
        given = self._in_force(self.retriever.search(question, as_of, self.k), as_of, [])
        timed("retrieval", started)
        answer = refusal(as_of) if not given else None
        asked: list[str] = []
        for step in range(self.steps + 1):
            if answer is not None:
                break
            left = self.steps - step
            system = AGENT_SYSTEM.replace("{pedidos}", str(left)) if left else CLAIMS_SYSTEM
            started = time.perf_counter()
            completion = self.llm.complete(system, agent_prompt(question, as_of, given, asked))
            calls.append(completion)
            reply = completion.text
            timed("generation", started)
            action = _action(reply) if left else None
            if action is None:
                answer = claims_answer(reply, as_of, given, self.counts)
                break
            if self.budget is not None and sum(seconds.values()) > self.budget:
                # Another call could outlast the caller's time (the demo's 30 s): fail now.
                self.counts["over_budget"] += 1
                raise BudgetTimeout(f"past the {self.budget} s budget, a request not followed")
            started = time.perf_counter()
            kind, values = action
            if kind == "pesquisar":
                self.counts["searches"] += 1
                found = self.retriever.search(values[0], as_of, self.k)
                new = self._in_force(found, as_of, given)[:PER_SEARCH]
                asked.append(f"pesquisar «{values[0]}»: {self._ids(new)}")
            else:
                self.counts["reads"] += 1
                new = self._in_force(self._read(values, question, as_of), as_of, given)
                asked.append(f"ler {', '.join(values)}: {self._ids(new)}")
            self.counts["added"] += len(new)
            given = given + new
            timed("retrieval", started)
        assert answer is not None  # the last step always answers
        timings = {stage: round(s, 3) for stage, s in seconds.items()}
        update = {
            "timings": timings,
            "requests": asked,
            "tokens": spent(calls),
            "given": read(given),
        }
        return answer.model_copy(update=update)

    def _in_force(
        self, citations: list[Citation], as_of: dt.date, given: list[tuple[Citation, Version]]
    ) -> list[tuple[Citation, Version]]:
        """The citations' versions in force on `as_of`, leaving out those already given."""
        have = {c for c, _ in given}
        out = []
        for citation in dict.fromkeys(citations):
            version = self.articles(citation, as_of)
            if citation not in have and version is not None:
                out.append((citation, version))
        return out

    def _read(self, ids: list[str], question: str, as_of: dt.date) -> list[Citation]:
        """The articles named by id ("CT 251") or number; a bare number is the first diploma's,
        in the order the question suggests (as for references in questions), that has it."""
        out = []
        for entry in ids:
            for ref in cited_articles(entry):
                diplomas = [ref.diploma] if ref.diploma else diplomas_for(question)
                found = (
                    Citation(diploma=d, article=ref.article)
                    for d in diplomas
                    if self.articles(Citation(diploma=d, article=ref.article), as_of) is not None
                )
                if (first := next(found, None)) is not None:
                    out.append(first)
        return out

    @staticmethod
    def _ids(new: list[tuple[Citation, Version]]) -> str:
        return ", ".join(article_id(c) for c, _ in new) or "nada de novo"
