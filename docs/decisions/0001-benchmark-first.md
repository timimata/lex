# 0001. The benchmark is the product

Date: 2026-09-29
Status: accepted

## Context

The first idea was an assistant that answers questions about Portuguese law with exact article
citations. Before starting, we looked at what already exists (September 2026):

- **Lia**, on diariodarepublica.pt, built by Xpand IT with Microsoft for INCM and live since
  February 2025. Generative AI with hybrid search over about 3,600 consolidated laws in force.
  Free, requires registration. ([INCM](https://incm.pt/site/lia-a-assistente-de-pesquisa-inteligente-do-diario-da-republica-ja-esta-disponivel/))
- **Guia Prático da Justiça**, from the Ministry of Justice, on Azure OpenAI, limited to specific
  topics. ([PÚBLICO](https://www.publico.pt/2023/02/17/tecnologia/noticia/ministerio-justica-vai-usar-tecnologia-chatgpt-responder-cidadaos-2039270))
- **Actia**, the virtual assistant on the ACT's portal (portal.act.gov.pt), for labour law
  questions. Found while looking for question sources on 2026-09-29.
- **TogaAI** and **LeiGPT**, commercial: legislation and case law with cited sources, contract
  analysis. LeiGPT has temporal filters. ([TogaAI](https://www.togai.pt/), [LeiGPT](https://leigpt.pt/))
- MCP servers for Portuguese law already exist
  ([portuguese-law-mcp](https://github.com/Ansvar-Systems/portuguese-law-mcp),
  [IAJUS](https://github.com/rafaelob/iajus-plugin-public-pt)).
- Open-source RAG over legislation with article-level chunking, hybrid BM25 + embeddings and
  mandatory citations, mostly Brazilian (e.g. [docs-rag](https://github.com/danieldevbel/docs-rag)).

Another assistant would be a worse copy of free tools with more coverage. None of them publishes
an evaluation anyone can check, and we found no open question-answering benchmark for European
Portuguese legislation.

## Decision

Lex is an open benchmark plus a reference system. The benchmark (questions, dates, and the
articles a correct answer must cite) is the main deliverable. The reference system exists to be
measured on it, and every design choice in it is kept or dropped on its dev-set numbers.

## Consequences

- Dataset quality is the core risk. Items come from public sources and get legal review before
  v1 ([bench/README.md](../../bench/README.md)).
- The public demo leads with the leaderboard, not a chat box.
- Features that don't move a benchmark number (MCP, agents, tracing) are optional and come last.
- External tools can be compared by hand on a small subset, after checking their terms of use.
