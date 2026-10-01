import asyncio
import datetime as dt
from typing import Any

import pytest

from lex.domain import Answer, Citation
from lex.store.memory import Corpus
from lex.store.models import ArticleVersion

pytest.importorskip("mcp")
from mcp.client.client import Client

from lex.mcp_server import build_server


def cite(article: str) -> Citation:
    return Citation(diploma="lei-7-2009", article=article)


def version(text: str, start: dt.date, end: dt.date | None) -> ArticleVersion:
    return ArticleVersion(
        diploma="lei-7-2009",
        article="238",
        heading="Duração do período de férias",
        path=[],
        text=text,
        valid_from=start,
        valid_to=end,
        introduced_by="lei-7-2009" if end else "lei-23-2012",
        source_url="https://example.org",
        fetched=dt.date(2026, 9, 30),
    )


CORPUS = Corpus(
    [
        version("com majoração", dt.date(2009, 2, 17), dt.date(2012, 8, 1)),
        version("sem majoração", dt.date(2012, 8, 1), None),
    ]
)


def call(tool: str, arguments: dict[str, Any], **parts: Any) -> Any:
    """A tool's structured result through a real MCP client, in memory."""

    async def go() -> Any:
        async with Client(build_server(CORPUS, **parts)) as client:
            result = await client.call_tool(tool, arguments)
            if result.is_error:
                return {"error": result.content[0].text}  # type: ignore[union-attr]
            return result.structured_content

    return asyncio.run(go())


def test_the_server_offers_four_tools() -> None:
    async def names() -> set[str]:
        async with Client(build_server(CORPUS)) as client:
            return {t.name for t in (await client.list_tools()).tools}

    assert asyncio.run(names()) == {"artigo", "versoes", "pesquisar", "responder"}


def test_an_article_on_a_date_and_its_timeline() -> None:
    old = call("artigo", {"numero": "art. 238.º", "data": "2011-06-01"})
    assert (old["texto"], old["em_vigor_ate"]) == ("com majoração", "2012-08-01")
    assert "valor legal" in old["aviso"]
    assert "Nenhuma versão" in call("artigo", {"numero": "238", "data": "2008-01-01"})["erro"]
    timeline = call("versoes", {"numero": "238.º"})["result"]
    assert [v["em_vigor_desde"] for v in timeline] == ["2009-02-17", "2012-08-01"]


def test_search_and_answers_use_the_parts_they_are_given() -> None:
    asked: list[tuple[str, dt.date, int]] = []

    def search() -> Any:
        def run(q: str, day: dt.date, k: int) -> list[Citation]:
            asked.append((q, day, k))
            return [cite("238")]

        return run

    def respond() -> Any:
        return lambda q, day: Answer(text=f"Resposta a {day:%d/%m/%Y}.", citations=[cite("238")])

    found = call("pesquisar", {"pergunta": "férias", "data": "2011-06-01", "k": 99}, search=search)
    assert found["result"] == [{"artigo": "238", "epigrafe": "Duração do período de férias"}]
    assert asked == [("férias", dt.date(2011, 6, 1), 20)]  # k capped at 20
    answer = call("responder", {"pergunta": "Férias?", "data": "2011-06-01"}, respond=respond)
    assert (answer["resposta"], answer["citacoes"]) == ("Resposta a 01/06/2011.", ["238"])
    assert "indisponíveis" in call("responder", {"pergunta": "Férias?"})["error"]
