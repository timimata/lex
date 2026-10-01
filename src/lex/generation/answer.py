"""The reference system: retrieve, read the article versions in force on the date asked about,
and answer from them with citations, or refuse (ADR 0011).

The model sees only the retrieved versions. Its citations are kept only if they name one of
them, and an answer left without any becomes a refusal: no citation, no claim (CLAUDE.md).
"""

import datetime as dt
import json
import re
import time
from collections.abc import Callable
from typing import Protocol

from lex.domain import Answer, Citation, Retriever
from lex.generation.llm import DEFAULT_PARAMS, Llm
from lex.retrieval.references import find_references

K = 5  # article versions given to the model; a usual size, not tuned on dev
DIPLOMAS = {"lei-7-2009": "Código do Trabalho"}

SYSTEM = """\
Respondes a perguntas sobre o Código do Trabalho português, apenas com base nos artigos que te \
são dados, na versão em vigor na data da pergunta.

Regras:
1. Usa só os artigos dados. Não acrescentes nada que não esteja neles, nem o que sabes de outras \
versões da lei ou de outras leis.
2. Cada afirmação apoia-se num artigo dado. Em "citacoes" põe o número de cada artigo em que te \
apoiaste, e só esses.
3. Se os artigos dados não permitem responder, recusa: "recusa": true, e explica numa frase, em \
"resposta", o que falta. Recusa também quando a pergunta não é sobre o que a lei diz.
4. Se os artigos só respondem a parte da pergunta, responde a essa parte e diz o que fica por \
responder.
5. Escreve em português europeu, de forma curta e direta (no máximo cinco frases), com os \
números, prazos e condições que os artigos dão.
6. Responde apenas com um objeto JSON, sem mais nada:
{"resposta": "...", "citacoes": ["238"], "recusa": false}"""

# The same task with a citation per sentence: a sentence no given article supports is dropped,
# so "no citation, no claim" holds sentence by sentence, not only for the answer as a whole.
CLAIMS_SYSTEM = """\
Respondes a perguntas sobre o Código do Trabalho português, apenas com base nos artigos que te \
são dados, na versão em vigor na data da pergunta.

Regras:
1. Usa só os artigos dados. Não acrescentes nada que não esteja neles, nem o que sabes de outras \
versões da lei ou de outras leis.
2. Responde só ao que é perguntado, em frases curtas. Cada frase diz em "artigos" o número de \
cada artigo dado em que se apoia; uma frase sem artigo não é aceite.
3. Se os artigos dados não permitem responder, recusa: "recusa": true, e explica numa frase, em \
"motivo", o que falta. Recusa também quando a pergunta não é sobre o que a lei diz.
4. Se os artigos só respondem a parte da pergunta, responde a essa parte e diz em "motivo" o que \
fica por responder.
5. Escreve em português europeu, no máximo cinco frases, com os números, prazos e condições \
que os artigos dão.
6. Responde apenas com um objeto JSON, sem mais nada:
{"frases": [{"texto": "...", "artigos": ["238"]}], "recusa": false, "motivo": ""}"""

FORMATS = ("answer", "claims")


class Version(Protocol):
    """What the model reads of an article version (lex.store's ArticleVersion fits)."""

    @property
    def heading(self) -> str: ...
    @property
    def text(self) -> str: ...
    @property
    def valid_from(self) -> dt.date: ...


# The version of a cited article in force on a date, or None if there was none.
Articles = Callable[[Citation, dt.date], Version | None]


def day(date: dt.date) -> str:
    return f"{date:%d/%m/%Y}"


def label(citation: Citation) -> str:
    """'Código do Trabalho, art. 199.º-A'."""
    number, _, suffix = citation.article.partition("-")
    article = f"art. {number}.º" + (f"-{suffix}" if suffix else "")
    return f"{DIPLOMAS.get(citation.diploma, citation.diploma)}, {article}"


def prompt(question: str, as_of: dt.date, given: list[tuple[Citation, Version]]) -> str:
    articles = "\n\n".join(
        f'<artigo numero="{c.article}" epigrafe="{v.heading}" '
        f'em_vigor_desde="{day(v.valid_from)}">\n{v.text}\n</artigo>'
        for c, v in given
    )
    return (
        f"Data da pergunta: {day(as_of)}\n\n"
        f"Artigos do Código do Trabalho em vigor nessa data:\n\n{articles}\n\n"
        f"Pergunta: {question}"
    )


def _first_object(reply: str, key: str = "resposta") -> dict[str, object] | None:
    """The first JSON object in the reply that has `key`, wherever it starts and whatever
    follows it (a code fence, a note with braces of its own)."""
    decoder = json.JSONDecoder()
    for start in (m.start() for m in re.finditer(r"\{", reply)):
        try:
            data, _ = decoder.raw_decode(reply, start)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and key in data:
            return data
    return None


def cited_articles(cited: object) -> list[str]:
    """Article numbers from one entry of "citacoes": 238, "238.º", "art. 199.º-A", "238.º e
    239.º", "344.º a 346.º". Read as the reference parser reads a question, so an entry naming
    another diploma ("artigo 10.º da Lei n.º 23/2012") yields nothing."""
    text = str(cited).strip()
    if not re.match(r"(?i)art", text):
        text = f"artigo {text}"
    return find_references(text)


def parse(reply: str) -> tuple[str, list[str], bool] | None:
    """The answer, the article numbers cited and whether the model refused, or None if the reply
    is not the JSON asked for. Tolerates a code fence or text around the object, and a missing
    "recusa" (an answer)."""
    data = _first_object(reply)
    if data is None:
        return None
    text, cited, refused = data.get("resposta"), data.get("citacoes", []), data.get("recusa", False)
    if not isinstance(text, str) or not isinstance(cited, list) or not isinstance(refused, bool):
        return None
    numbers = [n for c in cited for n in cited_articles(c)]
    return text.strip(), list(dict.fromkeys(numbers)), refused


def parse_claims(reply: str) -> tuple[list[tuple[str, list[str]]], bool, str] | None:
    """The sentences with the article numbers each cites, whether the model refused, and its
    reason, or None if the reply is not the JSON asked for."""
    data = _first_object(reply, "frases")
    if data is None:
        return None
    sentences, refused, reason = data["frases"], data.get("recusa", False), data.get("motivo", "")
    if not isinstance(sentences, list) or not isinstance(refused, bool):
        return None
    claims = []
    for sentence in sentences:
        if not isinstance(sentence, dict) or not isinstance(sentence.get("texto"), str):
            return None
        cited = sentence.get("artigos", [])
        numbers = [n for c in cited for n in cited_articles(c)] if isinstance(cited, list) else []
        claims.append((sentence["texto"].strip(), list(dict.fromkeys(numbers))))
    return claims, refused, reason.strip() if isinstance(reason, str) else ""


def marker(citations: list[Citation]) -> str:
    """'(art. 238.º)', '(arts. 238.º e 239.º)'."""
    numbers = [label(c).split(", ", 1)[1].removeprefix("art. ") for c in citations]
    if len(numbers) == 1:
        return f"(art. {numbers[0]})"
    return f"(arts. {', '.join(numbers[:-1])} e {numbers[-1]})"


def refusal(as_of: dt.date, reason: str = "") -> Answer:
    text = (
        f"Não encontrei, nos artigos do Código do Trabalho em vigor a {day(as_of)}, base para "
        "responder a esta pergunta."
    )
    return Answer(text=f"{text} {reason}" if reason else text, refused=True)


def sources(as_of: dt.date, used: list[tuple[Citation, Version]]) -> str:
    lines = [f"- {label(c)} (versão em vigor desde {day(v.valid_from)})" for c, v in used]
    return f"Fontes (lei em vigor a {day(as_of)}):\n" + "\n".join(lines)


class ReferenceSystem:
    def __init__(
        self,
        retriever: Retriever,
        articles: Articles,
        llm: Llm,
        k: int = K,
        format: str = "answer",  # or "claims": a citation per sentence
    ) -> None:
        if format not in FORMATS:
            raise ValueError(f"unknown format {format!r}")
        self.retriever = retriever
        self.articles = articles
        self.llm = llm
        self.k = k
        self.format = format
        # A setting that is not the default joins the name, so its results never overwrite the
        # default's (results/dev/ files are named after the system).
        effort = llm.params.get("reasoning_effort")
        self.name = (
            f"{retriever.name}+{llm.name}"
            + (f"+k{k}" if k != K else "")
            + ("+claims" if format == "claims" else "")
            + (
                f"+effort-{effort}"
                if effort not in (None, DEFAULT_PARAMS["reasoning_effort"])
                else ""
            )
        )
        # Why answers turned into refusals, and what was dropped, over this system's life.
        self.counts = {
            "malformed": 0,
            "uncited": 0,
            "dropped_citations": 0,
            "dropped_sentences": 0,
        }

    def answer(self, question: str, as_of: dt.date) -> Answer:
        """The answer, with the seconds spent retrieving and generating it."""
        started = time.perf_counter()
        given = []
        for citation in self.retriever.search(question, as_of, self.k):
            version = self.articles(citation, as_of)
            if version is not None:
                given.append((citation, version))
        retrieved = time.perf_counter()
        answer = self._from_model(question, as_of, given) if given else refusal(as_of)
        timings = {
            "retrieval": round(retrieved - started, 3),
            "generation": round(time.perf_counter() - retrieved, 3),
        }
        return answer.model_copy(update={"timings": timings})

    def _from_model(
        self, question: str, as_of: dt.date, given: list[tuple[Citation, Version]]
    ) -> Answer:
        if self.format == "claims":
            return self._from_claims(question, as_of, given)
        parsed = parse(self.llm.complete(SYSTEM, prompt(question, as_of, given)).text)
        if parsed is None:
            self.counts["malformed"] += 1
            return refusal(as_of)
        text, numbers, refused = parsed
        if refused:
            return refusal(as_of, text)

        by_article = {c.article: (c, v) for c, v in given}
        unknown = [n for n in numbers if n not in by_article]
        self.counts["dropped_citations"] += len(unknown)
        used = [by_article[n] for n in dict.fromkeys(numbers) if n in by_article]
        if not used:
            self.counts["uncited"] += 1
            return refusal(as_of)
        return Answer(
            text=f"{text}\n\n{sources(as_of, used)}",
            citations=[c for c, _ in used],
        )

    def _from_claims(
        self, question: str, as_of: dt.date, given: list[tuple[Citation, Version]]
    ) -> Answer:
        parsed = parse_claims(self.llm.complete(CLAIMS_SYSTEM, prompt(question, as_of, given)).text)
        if parsed is None:
            self.counts["malformed"] += 1
            return refusal(as_of)
        claims, refused, reason = parsed
        if refused:
            return refusal(as_of, reason)
        by_article = {c.article: (c, v) for c, v in given}
        kept, used = [], []
        for text, numbers in claims:
            self.counts["dropped_citations"] += sum(n not in by_article for n in numbers)
            support = [by_article[n] for n in numbers if n in by_article]
            if not text or not support:
                self.counts["dropped_sentences"] += 1
                continue
            kept.append(f"{text} {marker([c for c, _ in support])}")
            used += [s for s in support if s not in used]
        if not kept:
            self.counts["uncited"] += 1
            return refusal(as_of)
        return Answer(
            text=f"{' '.join(kept)}\n\n{sources(as_of, used)}",
            citations=[c for c, _ in used],
        )
