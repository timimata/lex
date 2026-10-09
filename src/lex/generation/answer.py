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

from lex import domain
from lex.domain import DIPLOMAS, Answer, Citation, Retriever
from lex.generation.llm import DEFAULT_PARAMS, Completion, Llm, spent
from lex.retrieval.references import Reference, find_references, normalise_article

K = 5  # article versions given to the model; a usual size, not tuned on dev

SYSTEM = """\
Respondes a perguntas sobre a lei portuguesa, apenas com base nos artigos que te são dados, na \
versão em vigor na data da pergunta. Os artigos são do Código do Trabalho (CT) e, sobre o \
arrendamento, do Código Civil (CC) e do Novo Regime do Arrendamento Urbano (NRAU).

Regras:
1. Usa só os artigos dados. Não acrescentes nada que não esteja neles, nem o que sabes de outras \
versões da lei ou de outras leis.
2. Cada afirmação apoia-se num artigo dado. Em "citacoes" põe o id de cada artigo em que te \
apoiaste (por exemplo "CT 238"), e só esses.
3. Se os artigos dados não permitem responder, recusa: "recusa": true, e explica numa frase, em \
"resposta", o que falta. Recusa também quando a pergunta não é sobre o que a lei diz.
4. Se os artigos só respondem a parte da pergunta, responde a essa parte e diz o que fica por \
responder.
5. Escreve em português europeu, de forma curta e direta (no máximo cinco frases), com os \
números, prazos e condições que os artigos dão.
6. Responde apenas com um objeto JSON, sem mais nada:
{"resposta": "...", "citacoes": ["CT 238"], "recusa": false}"""

# The same task with a citation per sentence: a sentence no given article supports is dropped,
# so "no citation, no claim" holds sentence by sentence, not only for the answer as a whole.
CLAIMS_SYSTEM = """\
Respondes a perguntas sobre a lei portuguesa, apenas com base nos artigos que te são dados, na \
versão em vigor na data da pergunta. Os artigos são do Código do Trabalho (CT) e, sobre o \
arrendamento, do Código Civil (CC) e do Novo Regime do Arrendamento Urbano (NRAU).

Regras:
1. Usa só os artigos dados. Não acrescentes nada que não esteja neles, nem o que sabes de outras \
versões da lei ou de outras leis.
2. Responde só ao que é perguntado, em frases curtas. Cada frase diz em "artigos" o id de cada \
artigo dado em que se apoia (por exemplo "CT 238"); uma frase sem artigo não é aceite.
3. Se os artigos dados não permitem responder, recusa: "recusa": true, e explica numa frase, em \
"motivo", o que falta. Recusa também quando a pergunta não é sobre o que a lei diz.
4. Se os artigos só respondem a parte da pergunta, responde a essa parte e diz em "motivo" o que \
fica por responder.
5. Escreve em português europeu, no máximo cinco frases, com os números, prazos e condições \
que os artigos dão.
6. Responde apenas com um objeto JSON, sem mais nada:
{"frases": [{"texto": "...", "artigos": ["CT 238"]}], "recusa": false, "motivo": ""}"""

# The per-sentence task with the one instruction of the agent's prompt that is not about
# requests (ADR 0018): what the agent's gain on dev came from, if not from the requests' text.
COVER_SYSTEM = CLAIMS_SYSTEM.replace(
    "\n\nRegras:\n",
    "\n\nAntes de responder, vê se os artigos dados cobrem todas as partes da pergunta.\n\n"
    "Regras:\n",
)

FORMATS = ("answer", "claims", "claims-cover")


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


def _number(citation: Citation) -> str:
    """'199.º-A'."""
    number, _, suffix = citation.article.partition("-")
    return f"{number}.º" + (f"-{suffix}" if suffix else "")


def label(citation: Citation) -> str:
    """'Código do Trabalho, art. 199.º-A'."""
    return f"{DIPLOMAS[citation.diploma].name}, art. {_number(citation)}"


def article_id(citation: Citation) -> str:
    """'CT 199-A': how the prompt names an article, and how the model cites it."""
    return f"{DIPLOMAS[citation.diploma].short} {citation.article}"


def _notes(version: Version) -> str:
    """The DR's notes on a version's effects (a deferral, a suspension, a Constitutional Court
    ruling), each in its own element inside the article: the law as it applied, not only as
    written (ROADMAP, Phase 11)."""
    return "".join(f"\n<nota>{note}</nota>" for note in getattr(version, "notes", ()))


def prompt(question: str, as_of: dt.date, given: list[tuple[Citation, Version]]) -> str:
    articles = "\n\n".join(
        f'<artigo id="{article_id(c)}" diploma="{DIPLOMAS[c.diploma].name}" '
        f'epigrafe="{v.heading}" em_vigor_desde="{day(v.valid_from)}">\n{v.text}'
        f"{_notes(v)}\n</artigo>"
        for c, v in given
    )
    return (
        f"Data da pergunta: {day(as_of)}\n\n"
        f"Artigos em vigor nessa data:\n\n{articles}\n\n"
        f"Pergunta: {question}"
    )


def first_object(reply: str, key: str = "resposta") -> dict[str, object] | None:
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


_SHORT = {d.short: diploma for diploma, d in DIPLOMAS.items()}
_ID = re.compile(
    rf"^(?P<short>{'|'.join(_SHORT)})\s+(?P<number>\d+(?:\.º|º)?(?:\s*-\s*[A-Z]{{1,2}})?)$",
    re.IGNORECASE,
)


def cited_articles(cited: object) -> list[Reference]:
    """The articles one entry of "citacoes" names: an id as the prompt gives them ("CT 238",
    "NRAU 15-A"), or what the reference parser reads in it as in a question ("238.º", "art.
    1083.º do Código Civil", "238.º e 239.º", "344.º a 346.º"). An entry naming a diploma the
    corpus does not hold ("artigo 10.º da Lei n.º 23/2012") yields nothing."""
    text = str(cited).strip()
    if match := _ID.match(text):
        diploma = _SHORT[match.group("short").upper()]
        return [Reference(normalise_article(match.group("number")), diploma)]
    if not re.match(r"(?i)art", text):
        text = f"artigo {text}"
    return find_references(text)


def given_cited(
    references: list[Reference], given: list[tuple[Citation, Version]]
) -> tuple[list[tuple[Citation, Version]], int]:
    """The given articles the references name, in order, once each, and how many references
    name none of them. A bare number names the given article with that number, if only one has
    it."""
    found: list[tuple[Citation, Version]] = []
    unknown = 0
    for ref in references:
        matches = [
            (c, v)
            for c, v in given
            if c.article == ref.article and ref.diploma in (None, c.diploma)
        ]
        if len(matches) != 1:
            unknown += 1
        elif matches[0] not in found:
            found.append(matches[0])
    return found, unknown


def parse(reply: str) -> tuple[str, list[Reference], bool] | None:
    """The answer, the articles cited and whether the model refused, or None if the reply is
    not the JSON asked for. Tolerates a code fence or text around the object, and a missing
    "recusa" (an answer)."""
    data = first_object(reply)
    if data is None:
        return None
    text, cited, refused = data.get("resposta"), data.get("citacoes", []), data.get("recusa", False)
    if not isinstance(text, str) or not isinstance(cited, list) or not isinstance(refused, bool):
        return None
    references = [r for c in cited for r in cited_articles(c)]
    return text.strip(), list(dict.fromkeys(references)), refused


def parse_claims(reply: str) -> tuple[list[tuple[str, list[Reference]]], bool, str] | None:
    """The sentences with the articles each cites, whether the model refused, and its reason, or
    None if the reply is not the JSON asked for."""
    data = first_object(reply, "frases")
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
        refs = [r for c in cited for r in cited_articles(c)] if isinstance(cited, list) else []
        claims.append((sentence["texto"].strip(), list(dict.fromkeys(refs))))
    return claims, refused, reason.strip() if isinstance(reason, str) else ""


def marker(citations: list[Citation]) -> str:
    """'(art. 238.º do CT)', '(arts. 238.º e 239.º do CT)', '(art. 1083.º do CC; art. 9.º do
    NRAU)'."""
    by_diploma: dict[str, list[str]] = {}
    for c in citations:
        by_diploma.setdefault(c.diploma, []).append(_number(c))
    parts = []
    for diploma, numbers in by_diploma.items():
        short = DIPLOMAS[diploma].short
        if len(numbers) == 1:
            parts.append(f"art. {numbers[0]} do {short}")
        else:
            parts.append(f"arts. {', '.join(numbers[:-1])} e {numbers[-1]} do {short}")
    return f"({'; '.join(parts)})"


def read(given: list[tuple[Citation, Version]]) -> list[domain.Version]:
    """What the model was given, as the answer records it."""
    return [
        domain.Version(diploma=c.diploma, article=c.article, valid_from=v.valid_from)
        for c, v in given
    ]


def refusal(as_of: dt.date, reason: str = "") -> Answer:
    text = (
        f"Não encontrei, no Código do Trabalho nem na lei do arrendamento em vigor a "
        f"{day(as_of)}, base para responder a esta pergunta."
    )
    # The model's own reason cites nothing: kept for reading runs, never part of the answer a
    # visitor is shown (no citation, no claim; ROADMAP, Phase 11).
    return Answer(text=text, refused=True, reason=reason)


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
        format: str = "answer",  # "claims": a citation per sentence; "claims-cover", ADR 0018
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
            + (f"+{format}" if format != "answer" else "")
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

    def _complete(self, system: str, user: str) -> str:
        completion = self.llm.complete(system, user)
        self._calls.append(completion)
        return completion.text

    def answer(self, question: str, as_of: dt.date) -> Answer:
        """The answer, with the seconds spent retrieving and generating it, and its tokens."""
        self._calls: list[Completion] = []
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
        update = {"timings": timings, "tokens": spent(self._calls), "given": read(given)}
        return answer.model_copy(update=update)

    def _from_model(
        self, question: str, as_of: dt.date, given: list[tuple[Citation, Version]]
    ) -> Answer:
        if self.format != "answer":
            return self._from_claims(question, as_of, given)
        parsed = parse(self._complete(SYSTEM, prompt(question, as_of, given)))
        if parsed is None:
            self.counts["malformed"] += 1
            return refusal(as_of)
        text, references, refused = parsed
        if refused:
            return refusal(as_of, text)

        used, unknown = given_cited(references, given)
        self.counts["dropped_citations"] += unknown
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
        system = COVER_SYSTEM if self.format == "claims-cover" else CLAIMS_SYSTEM
        reply = self._complete(system, prompt(question, as_of, given))
        return claims_answer(reply, as_of, given, self.counts)


def claims_answer(
    reply: str, as_of: dt.date, given: list[tuple[Citation, Version]], counts: dict[str, int]
) -> Answer:
    """The answer a per-sentence reply makes: each sentence kept with the given articles it
    cites, one that cites none dropped, a reply left with none a refusal. `counts` keeps why."""
    parsed = parse_claims(reply)
    if parsed is None:
        counts["malformed"] += 1
        return refusal(as_of)
    claims, refused, reason = parsed
    if refused:
        return refusal(as_of, reason)
    kept: list[str] = []
    used: list[tuple[Citation, Version]] = []
    for text, references in claims:
        support, unknown = given_cited(references, given)
        counts["dropped_citations"] += unknown
        if not text or not support:
            counts["dropped_sentences"] += 1
            continue
        kept.append(f"{text} {marker([c for c, _ in support])}")
        used += [s for s in support if s not in used]
    if not kept:
        counts["uncited"] += 1
        return refusal(as_of)
    return Answer(
        text=f"{' '.join(kept)}\n\n{sources(as_of, used)}",
        citations=[c for c, _ in used],
    )
