# 0014. The public demo on Vercel: Gemini Embedding 2 over the corpus in memory

Date: 2026-09-30
Status: accepted; supersedes the hosting and the demo's system in ADR 0013; amended
2026-10-01 (answers a citation per sentence), 2026-10-02 (questions in the model's query
format) and 2026-10-07 (documents stay as they are)

## Context

On 2026-09-30 Hugging Face refused to create the Docker Space of ADR 0013: Docker and Gradio
Spaces now need a PRO subscription ($9 a month). Tiago wants the demo to cost nothing and cannot
use a card: Oracle Cloud's Always Free rejected his card's address, and Modal asks for one.

Vercel's Hobby plan is free, needs only a GitHub login, serves static pages and runs Python
functions (up to 500 MB unpacked). A function cannot hold BGE-M3 and torch, nor a Postgres.

The article corpus is small: 889 versions, 1.4 MB of text. Gemini Embedding 2 is free on the
Gemini API's free tier, which embeds 1000 texts a day per account (every text of a batch counts;
checked 2026-09-30 from the API's own quota error). Measured on dev (commit f4f23e3), at 768
dimensions over the corpus in memory, with the reference parser: recall@5 0.95, against 0.90 for
BGE-M3 with the parser and 0.93 with the reranker; recall@1 0.78 against 0.81 and 0.84.

## Decision

- The demo is a Vercel project: one FastAPI function (`vercel/index.py`) that serves the
  web page's static files and `/api/*`.
- Its system is Gemini Embedding 2 (768 dimensions) over the corpus in memory
  (`lex.store.memory`, `lex.retrieval.memory`), the reference parser, and Gemini 3.1 Flash-Lite
  reading the top 5. `python -m lex.eval answers --retriever dense-gemini+refs` scores these same
  code paths; its dev and test numbers go on the leaderboard as the demo's.
- The corpus and its vectors ship with the function; questions are embedded through the API.
- The key is a Vercel environment variable. Both models are on the free tier, so the demo cannot
  cost anything: past the daily quota it answers "try later" (HTTP 503) at once, without waiting
  on retries. `LEX_ANSWERS_PER_DAY` (400 by default) keeps it under the embedding quota, which
  the eval runs of the same account share.
- The benchmark's reference system is unchanged: BGE-M3, the reranker and Postgres (ADRs 0006,
  0007, 0010).

## Consequences

- The demo costs nothing, needs no card, and holds no model: a cold function starts in about a
  second (0.91 s to import on this PC; on Vercel not measured yet).
- The per-visitor limit lives in each function instance, so it is weak; the free quota is the
  real cap.
- Answers from the demo are measured with the same code (`--retriever dense-gemini+refs`); see
  the amendment below.

## Amendment, 2026-10-01: a citation per sentence

Measured on dev (40 answerable and 6 unanswerable items), all with Gemini 3.1 Flash-Lite reading
the top 5 (`results/dev/`):

| Demo's system, variant | Citation recall / precision | Refused: answerable, unanswerable |
|---|---|---|
| answer, then its sources (as deployed until now) | 0.93 / 0.97 | 1 of 40, 5 of 6 |
| + cross-references (`+xrefs`) | 0.91 / 0.94 | 2 of 40, 5 of 6 |
| `reasoning_effort` minimal instead of low | 0.90 / 0.97 | 2 of 40, 5 of 6 |
| a citation per sentence (`--format claims`) | 0.93 / 0.95 | 1 of 40, 6 of 6 |

Question decomposition (`+decomp`) was dropped at retrieval: composite recall@5 0.72 against
0.78 without it (recall@10 0.89 against 0.83, beyond what the model reads).

The demo now answers a citation per sentence. Item by item it differs from the answer format in
four places: it refuses the out-of-scope question the answer format answered (the minimum wage for
2026, which the Code leaves to a yearly decree; the other cited art. 273.º), drops two of three
neighbouring articles cited on when a contract lapses, and adds a related article to two simple
answers; both formats make 4 citations outside the labels out of 47. Answering what the Code does
not cover is the worse error, and a citation on every sentence is what the project's rule asks of
an answer ("no citation, no claim"). `LEX_ANSWER_FORMAT=answer` brings the old format back.
- `space/` stays as the container image for any host that runs Docker. (Removed 2026-10-08: it
  still loaded Postgres for a demo that no longer reads it, and no longer started.)

## Amendment, 2026-10-02: questions in the model's own query format

Gemini Embedding 2 takes no task parameter. Google's embeddings guide puts the task in the text
instead: a question as `task: question answering | query: {question}`, a document as
`title: {title} | text: {text}`. The demo embedded both as they are. Questions now carry the
guide's prefix for question answering, the row of its table that fits, chosen before measuring;
no other prefix was tried. On dev v2 (66 answerable items, with the reference parser;
`results/dev/dense-gemini-embedding-2+refs.json`):

| Questions embedded | recall@1 | recall@3 | recall@5 | recall@10 |
|---|---|---|---|---|
| as they are | 0.65 | 0.81 | 0.84 | 0.92 |
| `task: question answering \| query: ...` | 0.75 | 0.88 | 0.90 | 0.95 |
| of which labour (54 items), before and after | 0.69, 0.75 | 0.85, 0.87 | 0.89, 0.89 | 0.93, 0.94 |
| of which tenancy (12 items), before and after | 0.50, 0.75 | 0.58, 0.92 | 0.63, 0.92 | 0.92, 1.00 |

Tenancy gains most where it was weakest: the eviction procedure, 22 articles (15.º to 15.º-S of
the NRAU) whose texts all speak of the same requerimento, now has the asked article in the top 5
for 4 of its 5 dev questions, from 0. One labour question lost ground at 5 (a composite one, 2
of 3 articles to 1 of 3).

Documents stay embedded as they were: their format means embedding all 1,213 versions again,
more than the 1,000 texts a day the free tier allows, and the demo's visitors spend from the same
quota. The query format lives with the embedder (`ApiEmbedder.query_format`), so the eval, the
demo and the MCP server embed questions the same way, and the eval's ranking cache keys on it.

## Amendment, 2026-10-07: documents stay as they are

The guide's document format, `title: {heading} | text: {text}`, was measured once the corpus
was embedded in it over two days of free quota (`dense-gemini-titled+refs`, vectors of their own).
On dev v3 (68 answerable items), against the plain heading and text, both with questions in the
query format:

| Documents embedded | recall@1 | recall@3 | recall@5 | recall@10 |
|---|---|---|---|---|
| heading and text (deployed) | 0.73 | 0.87 | 0.89 | 0.94 |
| `title: ... \| text: ...` | 0.78 | 0.87 | 0.89 | 0.95 |

The model reads the top 5, where nothing changes (0.890 against 0.887: one composite question
loses one of its three articles), so the deployed vectors stay; the gain at 1 would show only in
the order of what the model already reads. `results/dev/dense-gemini-embedding-2-titled+refs.json`
keeps the run.
