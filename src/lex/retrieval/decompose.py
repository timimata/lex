"""Question decomposition, for composite questions: a model splits the question into the parts
that need different articles, each part is searched for, and the rankings are interleaved, the
whole question's first.

"Se o pai de um trabalhador morrer durante as férias, as férias suspendem-se?" needs the article
on suspending holidays and the one on bereavement leave; one embedding of the whole question
tends to find only the first. A question the model keeps whole is searched exactly as before, so
simple questions lose nothing but the model call. Measured on dev before it is kept anywhere.
"""

import datetime as dt
import json
import re
from typing import Protocol

from lex.domain import Citation, Retriever

MOST = 3  # parts searched besides the whole question; set, not tuned

SYSTEM = """\
Divides perguntas sobre a lei portuguesa (o Código do Trabalho e o arrendamento) nas partes que \
precisam de artigos diferentes.

Regras:
1. Se a pergunta trata de um só assunto, devolve-a como única parte.
2. Senão, devolve de 2 a 3 perguntas curtas, uma por assunto, com as palavras que a lei usaria.
3. Não respondas à pergunta.
Responde apenas com um objeto JSON: {"partes": ["..."]}"""


class Reply(Protocol):
    @property
    def text(self) -> str: ...


class Model(Protocol):
    name: str

    def complete(self, system: str, user: str) -> Reply: ...


def parts(reply: str) -> list[str]:
    """The parts in a model's reply; none if it gave no readable list."""
    decoder = json.JSONDecoder()
    for start in (m.start() for m in re.finditer(r"\{", reply)):
        try:
            data, _ = decoder.raw_decode(reply, start)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("partes"), list):
            found = [p.strip() for p in data["partes"] if isinstance(p, str) and p.strip()]
            return list(dict.fromkeys(found))
    return []


class Decomposed:
    def __init__(self, base: Retriever, model: Model, most: int = MOST) -> None:
        self.base = base
        self.model = model
        self.most = most
        self.name = f"{base.name}+decomp"

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        found = parts(self.model.complete(SYSTEM, question).text)
        if len(found) < 2:  # one subject: search the question as it is
            return self.base.search(question, as_of, k)
        rankings = [self.base.search(q, as_of, k) for q in [question, *found[: self.most]]]
        out: list[Citation] = []
        for rank in range(k):
            for ranking in rankings:
                if rank < len(ranking) and ranking[rank] not in out:
                    out.append(ranking[rank])
        return out[:k]
