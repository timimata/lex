# 0014. The public demo on Vercel: Gemini Embedding 2 over the corpus in memory

Date: 2026-09-30
Status: accepted; supersedes the hosting and the demo's system in ADR 0013; amended
2026-10-01 (answers a citation per sentence)

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
- `space/` stays as the container image for any host that runs Docker.
