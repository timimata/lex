import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from lex.domain import DIPLOMAS, Citation
from lex.generation.answer import (
    CLAIMS_SYSTEM,
    COVER_SYSTEM,
    ReferenceSystem,
    parse,
    prompt,
)
from lex.generation.llm import (
    DEFAULT_MODEL,
    DEFAULT_PARAMS,
    Cached,
    Completion,
    OpenAiCompatible,
    from_env,
)
from lex.retrieval.references import Reference

TODAY = dt.date(2026, 9, 30)


def cite(article: str) -> Citation:
    return Citation(diploma="lei-7-2009", article=article)


@dataclass(frozen=True)
class Version:
    heading: str
    text: str
    valid_from: dt.date


ARTICLES = {
    "238": Version("Duração do período de férias", "Mínimo de 22 dias úteis.", dt.date(2012, 8, 1)),
    "251": Version("Faltas por falecimento", "Até cinco dias consecutivos.", dt.date(2023, 5, 1)),
    "199-A": Version("Trabalho no domicílio", "Texto.", dt.date(2023, 5, 1)),
}


def articles(citation: Citation, as_of: dt.date) -> Version | None:
    return ARTICLES.get(citation.article) if as_of >= dt.date(2009, 2, 17) else None


class Fixed:
    name = "fixed"

    def __init__(self, ranking: list[str]) -> None:
        self.ranking = [cite(a) for a in ranking]

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        return self.ranking[:k]


class Scripted:
    """A model that replies with the given text and remembers what it was asked."""

    name = "scripted"

    def __init__(self, reply: str) -> None:
        self.params: dict[str, Any] = {}
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, system: str, user: str) -> Completion:
        self.prompts.append(user)
        return Completion(self.reply, prompt_tokens=100, completion_tokens=20)


def reply(answer: str, cited: list[str], refused: bool = False) -> str:
    return json.dumps({"resposta": answer, "citacoes": cited, "recusa": refused})


def test_an_answer_cites_only_articles_it_was_given_and_names_their_versions() -> None:
    model = Scripted(reply("Cinco dias consecutivos.", ["251.º", "999", "238"]))
    system = ReferenceSystem(Fixed(["251", "238"]), articles, model, k=2)

    answer = system.answer("Quantos dias de falta por morte de um filho?", TODAY)

    assert system.name == "fixed+scripted+k2"  # k joins the name when it is not the default
    assert ReferenceSystem(Fixed([]), articles, model).name == "fixed+scripted"
    model.params = {"reasoning_effort": "minimal"}  # so is a reasoning effort other than low
    assert ReferenceSystem(Fixed([]), articles, model).name == "fixed+scripted+effort-minimal"
    model.params = {"reasoning_effort": "low", "seed": 0}  # the default, and other parameters
    assert ReferenceSystem(Fixed([]), articles, model).name == "fixed+scripted"
    assert not answer.refused
    assert answer.citations == [cite("251"), cite("238")]
    assert answer.text.startswith("Cinco dias consecutivos.\n\nFontes (lei em vigor a 30/09/2026):")
    assert "- Código do Trabalho, art. 251.º (versão em vigor desde 01/05/2023)" in answer.text
    assert system.counts == {
        "malformed": 0,
        "uncited": 0,
        "dropped_citations": 1,
        "dropped_sentences": 0,
    }
    assert set(answer.timings) == {"retrieval", "generation"}
    assert all(0 <= t < 1 for t in answer.timings.values())


def test_the_model_reads_the_date_and_the_given_versions_only() -> None:
    model = Scripted(reply("Sim.", ["199-A"]))
    ReferenceSystem(Fixed(["199-A", "238", "251"]), articles, model, k=1).answer("P?", TODAY)

    [sent] = model.prompts
    assert "Data da pergunta: 30/09/2026" in sent
    assert (
        '<artigo id="CT 199-A" diploma="Código do Trabalho" epigrafe="Trabalho no domicílio" '
    ) in sent
    assert "Mínimo de 22 dias úteis." not in sent  # 238 was not among the k retrieved
    assert sent.endswith("Pergunta: P?")


@pytest.mark.parametrize(
    ("model_reply", "count"),
    [
        (reply("A lei não trata disso.", [], refused=True), None),
        (reply("Uma resposta sem apoio.", []), "uncited"),
        (reply("Uma resposta com citação inventada.", ["999"]), "uncited"),
        ("Não sei responder em JSON.", "malformed"),
    ],
)
def test_refusals_and_answers_without_support_are_refusals(
    model_reply: str, count: str | None
) -> None:
    system = ReferenceSystem(Fixed(["251"]), articles, Scripted(model_reply))

    answer = system.answer("Pergunta?", TODAY)

    assert answer.refused
    assert answer.citations == []
    assert "em vigor a 30/09/2026" in answer.text
    if count:
        assert system.counts[count] == 1


def test_no_article_in_force_means_a_refusal_without_calling_the_model() -> None:
    model = Scripted(reply("Não devia ser chamado.", ["251"]))
    answer = ReferenceSystem(Fixed(["251"]), articles, model).answer("P?", dt.date(2008, 1, 1))

    assert answer.refused
    assert model.prompts == []


def test_parse_tolerates_a_code_fence_and_article_labels() -> None:
    fenced = (
        '```json\n{"resposta": "Sim.", "citacoes": ["art. 199.º-A", 238], "recusa": false}\n```'
    )
    assert parse(fenced) == ("Sim.", [bare("199-A"), bare("238")], False)
    assert parse('{"resposta": "Sim.", "citacoes": "238", "recusa": false}') is None
    assert parse('{"resposta": "Sim.", "citacoes": ["238"]}') == ("Sim.", [bare("238")], False)
    assert parse('{"resposta": "Sim.", "citacoes": [], "recusa": "não"}') is None
    assert parse('{"citacoes": ["238"]}') is None


def bare(article: str) -> Reference:
    return Reference(article, None)


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        # A note after the object, with braces of its own, used to make the whole reply malformed.
        ('{"resposta": "Sim.", "citacoes": ["238"], "recusa": false}\nNota: {n.º 2}', ["238"]),
        ('Texto {não JSON} antes. {"resposta": "Sim.", "citacoes": ["238"]}', ["238"]),
        # A diploma the corpus does not hold.
        ('{"resposta": "Sim.", "citacoes": ["artigo 10.º da Lei n.º 23/2012"]}', []),
        # Several articles in one entry, and a range.
        (
            '{"resposta": "Sim.", "citacoes": ["238.º e 239.º", "344.º a 346.º"]}',
            ["238", "239", "344", "345", "346"],
        ),
        ('{"resposta": "Sim.", "citacoes": ["n.º 2 do artigo 131.º", 238, "238"]}', ["131", "238"]),
        # Ids as the prompt gives them, and a diploma named after the number.
        (
            '{"resposta": "Sim.", "citacoes": ["CT 238", "NRAU 15-A", '
            '"art. 1083.º do Código Civil"]}',
            ["CT:238", "NRAU:15-A", "CC:1083"],
        ),
    ],
)
def test_parse_reads_citations_as_the_reference_parser_reads_questions(
    reply: str, expected: list[str]
) -> None:
    parsed = parse(reply)
    assert parsed is not None
    short = {d.short: diploma for diploma, d in DIPLOMAS.items()}
    assert parsed[1] == [
        Reference(t.rpartition(":")[2], short.get(t.rpartition(":")[0])) for t in expected
    ]


def test_a_bare_number_two_given_articles_share_names_neither() -> None:
    nrau_9 = Citation(diploma="lei-6-2006", article="9")
    given = {
        cite("9"): Version("Forma (CT)", "Texto do CT.", dt.date(2009, 2, 17)),
        nrau_9: Version("Forma da comunicação", "Texto do NRAU.", dt.date(2017, 6, 15)),
    }

    class Both:
        name = "both"

        def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
            return list(given)

    def read(citation: Citation, as_of: dt.date) -> Version | None:
        return given.get(citation)

    ambiguous = ReferenceSystem(Both(), read, Scripted(reply("Sim.", ["9"])))
    assert ambiguous.answer("P?", TODAY).refused
    named = ReferenceSystem(Both(), read, Scripted(reply("Sim.", ["NRAU 9"])))
    answer = named.answer("P?", TODAY)
    assert answer.citations == [nrau_9]
    assert "- NRAU, art. 9.º (versão em vigor desde 15/06/2017)" in answer.text


def test_the_prompt_lists_each_article_with_its_version_date() -> None:
    text = prompt("P?", TODAY, [(cite("238"), ARTICLES["238"])])
    assert 'em_vigor_desde="01/08/2012">\nMínimo de 22 dias úteis.\n</artigo>' in text


def test_the_cache_answers_a_repeated_prompt_from_disk(tmp_path: Path) -> None:
    model = Scripted("resposta")
    cached = Cached(model, tmp_path)

    first = cached.complete("sistema", "pergunta")
    second = cached.complete("sistema", "pergunta")
    cached.complete("sistema", "outra pergunta")

    assert first == second
    assert len(model.prompts) == 2  # the repeat never reached the model
    assert cached.usage() == {
        "calls": 3,
        "cached": 1,
        "prompt_tokens": 300,
        "completion_tokens": 60,
    }
    # A new process reads the same file.
    assert Cached(Scripted("outra"), tmp_path).complete("sistema", "pergunta") == first


def test_the_cache_key_changes_with_model_and_params(tmp_path: Path) -> None:
    a = Cached(Scripted(""), tmp_path)
    b = Cached(Scripted(""), tmp_path)
    b.name = "another-model"
    c = Cached(Scripted(""), tmp_path)
    c.params = {"reasoning_effort": "high"}
    assert len({x.key("s", "u") for x in (a, b, c)}) == 3


def test_a_repeat_asks_again_and_keeps_the_first_answers(tmp_path: Path) -> None:
    first = Cached(Scripted("primeira"), tmp_path)
    first.complete("s", "u")
    model = Scripted("segunda")
    again = Cached(model, tmp_path, repeat=1)

    assert again.complete("s", "u").text == "segunda" and len(model.prompts) == 1
    assert Cached(Scripted("outra"), tmp_path).complete("s", "u").text == "primeira"
    assert again.key("s", "u") != first.key("s", "u")


# A chat completion as the OpenAI-compatible endpoint returns it.
REPLY = {
    "id": "1",
    "object": "chat.completion",
    "created": 0,
    "model": "gemini-3.1-flash-lite",
    "choices": [
        {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "{}"}}
    ],
    "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
}


def test_the_client_sends_the_model_prompt_and_params_and_reads_usage() -> None:
    httpx = pytest.importorskip("httpx")
    pytest.importorskip("openai")
    sent: list[dict[str, Any]] = []

    def endpoint(request: Any) -> Any:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=REPLY)

    llm = OpenAiCompatible(api_key="test")
    llm.client = llm.client.with_options(
        http_client=httpx.Client(transport=httpx.MockTransport(endpoint))
    )

    assert llm.complete("sistema", "pergunta") == Completion("{}", 12, 3)
    assert sent == [
        {
            "model": "gemini-3.1-flash-lite",
            "messages": [
                {"role": "system", "content": "sistema"},
                {"role": "user", "content": "pergunta"},
            ],
            "reasoning_effort": "low",
        }
    ]
    # A model served without system instructions reads them first in the user's message.
    gemma = OpenAiCompatible(model="gemma-4-26b-a4b-it", params={}, system_as_user=True)
    gemma.client = llm.client
    gemma.complete("sistema", "pergunta")
    assert sent[1] == {
        "model": "gemma-4-26b-a4b-it",
        "messages": [{"role": "user", "content": "sistema\n\npergunta"}],
    }


def test_an_overloaded_model_is_asked_again_and_a_rate_limit_is_not() -> None:
    httpx = pytest.importorskip("httpx")
    openai = pytest.importorskip("openai")
    replies: list[Any] = []

    def endpoint(request: Any) -> Any:
        return replies.pop(0)()

    def model(
        overload_waits: tuple[float, ...] = (), quick: float | None = None
    ) -> OpenAiCompatible:
        llm = OpenAiCompatible(
            api_key="test",
            waits=(),
            max_retries=0,
            overload_waits=overload_waits,
            quick_failure=quick,
        )
        llm.client = llm.client.with_options(
            http_client=httpx.Client(transport=httpx.MockTransport(endpoint))
        )
        return llm

    def busy() -> Any:
        return httpx.Response(503, json={"error": {"code": 503, "message": "high demand"}})

    def limited() -> Any:
        return httpx.Response(429, json={"error": {"code": 429, "message": "quota"}})

    def answered() -> Any:
        return httpx.Response(200, json=REPLY)

    replies[:] = [busy, answered]
    assert model(overload_waits=(0,)).complete("s", "p") == Completion("{}", 12, 3)
    replies[:] = [busy, busy]
    with pytest.raises(openai.InternalServerError):  # asked once more, then it gives up
        model(overload_waits=(0,)).complete("s", "p")
    replies[:] = [busy]
    with pytest.raises(openai.InternalServerError):  # the default: no second try of its own
        model().complete("s", "p")
    replies[:] = [limited]
    with pytest.raises(openai.RateLimitError):  # a rate limit is not an overload
        model(overload_waits=(0,)).complete("s", "p")
    replies[:] = [busy]
    with pytest.raises(openai.InternalServerError):  # under a time budget, a slow refusal is final
        model(overload_waits=(0,), quick=-1).complete("s", "p")
    assert replies == []


def test_the_environment_chooses_the_model_endpoint_and_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("openai")
    monkeypatch.setenv("LLM_MODEL", "gemma-4-E2B-it-Q4_0")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
    monkeypatch.setenv("LLM_PARAMS", '{"seed": 0}')
    model = from_env()
    assert (model.name, model.params) == ("gemma-4-E2B-it-Q4_0", {"seed": 0})
    assert str(model.client.base_url) == "http://127.0.0.1:8080/v1/"

    monkeypatch.delenv("LLM_MODEL")
    monkeypatch.delenv("LLM_PARAMS")
    assert (from_env().name, from_env().params) == (DEFAULT_MODEL, DEFAULT_PARAMS)


def claims(*sentences: tuple[str, list[str]], refused: bool = False, reason: str = "") -> str:
    return json.dumps(
        {
            "frases": [{"texto": t, "artigos": a} for t, a in sentences],
            "recusa": refused,
            "motivo": reason,
        }
    )


def test_the_cover_format_is_the_claims_task_with_the_coverage_instruction() -> None:
    class Asked(Scripted):
        def complete(self, system: str, user: str) -> Completion:
            self.system = system
            return super().complete(system, user)

    model = Asked(claims(("São cinco dias consecutivos.", ["251"])))
    system = ReferenceSystem(Fixed(["251"]), articles, model, format="claims-cover")
    answer = system.answer("Pergunta?", TODAY)

    assert system.name == "fixed+scripted+claims-cover"
    assert model.system == COVER_SYSTEM != CLAIMS_SYSTEM
    assert "cobrem todas as partes da pergunta" in COVER_SYSTEM
    assert answer.citations == [cite("251")]


def test_claims_keep_each_sentence_with_its_articles_and_drop_the_unsupported() -> None:
    reply = claims(
        ("São cinco dias consecutivos.", ["251"]),
        ("O trabalhador-estudante tem regras próprias.", []),  # no article: dropped
        ("As férias têm 22 dias úteis.", ["238.º", "999"]),  # 999 was not given
    )
    system = ReferenceSystem(Fixed(["251", "238"]), articles, Scripted(reply), format="claims")
    answer = system.answer("Pergunta?", TODAY)

    assert system.name == "fixed+scripted+claims"
    assert answer.text.startswith(
        "São cinco dias consecutivos. (art. 251.º do CT) "
        "As férias têm 22 dias úteis. (art. 238.º do CT)"
    )
    assert "estudante" not in answer.text
    assert answer.citations == [cite("251"), cite("238")]
    assert system.counts["dropped_sentences"] == 1
    assert system.counts["dropped_citations"] == 1


def test_claims_with_no_support_or_a_refusal_are_refusals() -> None:
    unsupported = ReferenceSystem(
        Fixed(["251"]), articles, Scripted(claims(("Sem apoio.", []))), format="claims"
    )
    assert unsupported.answer("P?", TODAY).refused
    assert unsupported.counts["uncited"] == 1

    reply = claims(refused=True, reason="A lei não trata disso.")
    refused = ReferenceSystem(Fixed(["251"]), articles, Scripted(reply), format="claims")
    answer = refused.answer("P?", TODAY)
    assert answer.refused and answer.text.endswith("A lei não trata disso.")
    with pytest.raises(ValueError):
        ReferenceSystem(Fixed(["251"]), articles, Scripted(reply), format="prose")


def test_a_sentence_may_rest_on_several_articles() -> None:
    reply = claims(("Ambos se aplicam.", ["238", "251"]))
    answer = ReferenceSystem(
        Fixed(["251", "238"]), articles, Scripted(reply), format="claims"
    ).answer("P?", TODAY)
    assert answer.text.startswith("Ambos se aplicam. (arts. 238.º e 251.º do CT)")
