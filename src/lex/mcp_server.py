"""python -m lex.mcp_server: Lex's Código do Trabalho as tools for an MCP client (an agent).

Tools: `artigo` (an article as in force on a date), `versoes` (its timeline), `pesquisar` (the
articles most relevant to a question, on a date) and `responder` (the demo's answer, with
citations). The first two read the local corpus only; the last two use the Gemini API like the
demo (ADR 0014), so they need LLM_API_KEY and spend its free quota. Wiring, like the __main__
modules: it builds concrete parts and hands them to the server.

Run over stdio, e.g. in an MCP client's configuration:
    {"command": "<repo>/.venv/Scripts/python", "args": ["-m", "lex.mcp_server"]}
"""

import datetime as dt
import functools
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from lex.api.app import DISCLAIMER, lisbon_today
from lex.domain import Answer, Citation, Retriever
from lex.store.memory import Corpus
from lex.store.models import ArticleVersion

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "processed" / "ct"
CT = "lei-7-2009"

Search = Callable[[str, dt.date, int], list[Citation]]
Respond = Callable[[str, dt.date], Answer]


def _date(value: str | None) -> dt.date:
    return dt.date.fromisoformat(value) if value else lisbon_today()


def _number(article: str) -> str:
    """'238.º' or 'art. 199.º-A' -> '238', '199-A'."""
    from lex.retrieval.references import normalise_article

    return normalise_article(article.lower().replace("artigo", "").replace("art.", "").strip())


def build_server(
    corpus: Corpus,
    search: Callable[[], Search] | None = None,
    respond: Callable[[], Respond] | None = None,
) -> MCPServer:
    """The server. `search` and `respond` build their parts on first use, so the tools that need
    no model start without a key."""
    server = MCPServer(
        name="lex",
        title="Lex: Código do Trabalho",
        instructions=(
            "O Código do Trabalho português (Lei n.º 7/2009) em todas as versões desde 2009. "
            "Datas em AAAA-MM-DD; sem data, é a lei em vigor hoje em Lisboa. " + DISCLAIMER
        ),
    )
    built: dict[str, Any] = {}

    @server.tool()
    def artigo(numero: str, data: str | None = None) -> dict[str, Any]:
        """Um artigo do Código do Trabalho na versão em vigor numa data (por omissão, hoje)."""
        day, number = _date(data), _number(numero)
        version = corpus.article_at(CT, number, day)
        if version is None:
            return {"erro": f"Nenhuma versão do artigo {number} em vigor a {day.isoformat()}."}
        return {
            "artigo": number,
            "epigrafe": version.heading,
            "texto": version.text,
            "em_vigor_desde": version.valid_from.isoformat(),
            "em_vigor_ate": version.valid_to.isoformat() if version.valid_to else None,
            "introduzido_por": version.introduced_by,
            "fonte": version.source_url,
            "aviso": DISCLAIMER,
        }

    @server.tool()
    def versoes(numero: str) -> list[dict[str, Any]]:
        """Todas as versões de um artigo do Código do Trabalho, da mais antiga à atual."""
        return [
            {
                "em_vigor_desde": v.valid_from.isoformat(),
                "em_vigor_ate": v.valid_to.isoformat() if v.valid_to else None,
                "introduzido_por": v.introduced_by,
            }
            for v in corpus.versions_of(CT, _number(numero))
        ]

    @server.tool()
    def pesquisar(pergunta: str, data: str | None = None, k: int = 5) -> list[dict[str, str]]:
        """Os artigos do Código do Trabalho mais relevantes para uma pergunta, entre os em vigor
        numa data (por omissão, hoje)."""
        if search is None:
            raise ToolError("Pesquisa indisponível neste servidor.")
        if "search" not in built:
            built["search"] = search()
        day = _date(data)
        found = built["search"](pergunta, day, max(1, min(k, 20)))
        out = []
        for c in found:
            version = corpus.article_at(c.diploma, c.article, day)
            out.append({"artigo": c.article, "epigrafe": version.heading if version else ""})
        return out

    @server.tool()
    def responder(pergunta: str, data: str | None = None) -> dict[str, Any]:
        """Resposta do Lex a uma pergunta sobre o Código do Trabalho, com os artigos citados, ou
        a recusa quando os artigos não permitem responder."""
        if respond is None:
            raise ToolError("Respostas indisponíveis neste servidor.")
        if "respond" not in built:
            built["respond"] = respond()
        answer: Answer = built["respond"](pergunta, _date(data))
        return {
            "resposta": answer.text,
            "citacoes": [c.article for c in answer.citations],
            "recusa": answer.refused,
            "aviso": DISCLAIMER,
        }

    return server


def main() -> int:
    load_dotenv(ROOT / ".env")
    corpus = Corpus.load(CORPUS / "versions.jsonl")

    @functools.cache
    def retriever() -> Retriever:
        """The demo's retriever (ADR 0014), built once, on first use."""
        from lex.retrieval.dense import ApiEmbedder
        from lex.retrieval.memory import DenseInMemory, Vectors
        from lex.retrieval.references import WithReferences

        key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("LLM_API_KEY", "")
        vectors = Vectors.load(CORPUS / "vectors-gemini-embedding-2-768.npz")
        dense = DenseInMemory(corpus, ApiEmbedder(api_key=key, waits=()), vectors)
        return WithReferences(dense, corpus.article_at)

    def respond() -> Respond:
        from lex.generation import llm
        from lex.generation.answer import ReferenceSystem

        def article_at(c: Citation, day: dt.date) -> ArticleVersion | None:
            return corpus.article_at(c.diploma, c.article, day)

        return ReferenceSystem(retriever(), article_at, llm.from_env(waits=())).answer

    build_server(corpus, lambda: retriever().search, respond).run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
