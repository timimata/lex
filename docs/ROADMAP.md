# Roadmap

A phase ends when its exit criteria are met. From Phase 2 on, every phase leaves the project in a
state worth showing, so stopping early still leaves something real.

**Unlocks, current** (benchmark v4, `results/test/`, Phase 10's milestone; the phases' own lines
below quote v0): "Built an open benchmark of 201 dated questions on Portuguese labour and tenancy
law, each with the articles a right answer must cite and a private test split, and a system
measured on it: on 76 held-out answerable test questions, answered afresh, its answers cite the
right articles (citation recall 0.92, precision 0.90) and 70% are judged correct by an LLM judge
checked on known-answer cases (81 of 81 right answers accepted, 57 of 57 altered ones caught),
refusing 19 of 20 questions the law it holds does not answer." v3's line quoted 76% on 89
questions; v4's test is v3's less 13 items that joined their groups in dev.

## Phase 0: Foundations (done 2026-09-29)

- Repo layout, rules ([CLAUDE.md](../CLAUDE.md)), ADRs 0001 to 0004.
- Benchmark item schema, split assignment, validator, CI.

**Exit:** CI green on an empty benchmark.

## Phase 1: The Código do Trabalho, with every version (done 2026-09-29)

- ~~Find out how diariodarepublica.pt exposes consolidated legislation and each article's
  history.~~ Done: [ADR 0005](decisions/0005-legislation-source.md).
- ~~Ingest the Código do Trabalho: every article, every version, validity dates, provenance.~~
  Done: `python -m lex.ingest ct` writes `data/processed/ct/versions.jsonl` and `report.json`.
- ~~Date the articles touched by Lei n.º 90/2019 by reading its entry-into-force article.~~
  Done: `READ_FROM_DIPLOMA` in `src/lex/ingest/build.py`, with the source of each date.
- ~~Choose the store.~~ Done: [ADR 0006](decisions/0006-store.md), Postgres 18 with pg_search
  and pgvector (ParadeDB image), `docker compose up -d --wait` then `python -m lex.store load`.
  All 889 versions load under the constraint that no article has two versions in force on the
  same day.

**Ingestion as of 2026-09-29** (first fetch; rebuilds from cache make no requests):
- 601 of 601 articles found on both sources, all with their current text (from the DR) and a
  complete history; 889 article versions stored; 0 problems in the build report.
- 18 version dates resolved by rule, each listed in the report: 10 read from Lei n.º 90/2019's
  art. 9.º (it entered into force on 2019-09-09, 2019-10-04 or 2020-04-01 depending on the
  provision, and the DR gives no date on those 10 articles), 7 rectifications, 1 unanimous
  diploma date.
- The PGDL's current text differs from the DR's on 8 articles, all in punctuation.
- One article carries a Constitutional Court ruling note (368.º, Acórdão n.º 602/2013).

**Exit:**
- ~~one command rebuilds the store from the raw cache~~ (`python -m lex.ingest ct --offline`,
  then `python -m lex.store load`);
- ~~asking for article 238 of `lei-7-2009` on any date returns the text in force that day~~
  (`python -m lex.store show 238 --as-of 2011-06-01`);
- ~~20 randomly chosen article versions checked against the DR, results written down~~:
  [spot check](checks/phase1-spot-check.md), `python -m lex.ingest spot-check 20`. Automated
  rather than by hand: each version is compared with the DR's own history view on its first and
  last day. 38 of 40 checks match in text, and every period the DR states matches the store's
  dates. The two differences are the DR's view, not the data: on 2009-09-14 it already shows
  article 538.º as changed by Lei n.º 105/2009, published that day and in force the next; and
  on 2023-04-30 it shows article 112.º without the Retificação n.º 13/2023, published 2023-05-29,
  which the store applies from 2023-05-01 as Lei n.º 74/98, art. 5.º, n.º 4 requires.

**Phase 1 done 2026-09-29.**

## Phase 2: Benchmark v0 and first baselines (done 2026-09-30)

- ~~100 items on the Código do Trabalho, sourced from ACT's public guidance and similar pages.~~
  Done: 100 items (46 dev, 54 test): 42 `simple`, 17 `composite`, 15 `temporal`, 16
  `explicit_reference`, 10 `unanswerable`. Sources: ACT technical notes and guides, the ACT's
  FAQ ([ADR 0008](decisions/0008-act-faq-as-question-source.md)), Lei n.º 23/2012 and the PGDL's
  pages for earlier article versions. Every item was checked against the law in force on its
  `as_of` and reviewed by the model that drafted it (`reviewed_by`); none is legally validated
  yet (Phase 6).
- ~~Retrieval harness: recall@k per type.~~ Done: `python -m lex.eval retrieval SYSTEM`.
  Citation precision and recall and refusal accuracy score a `System` that answers, so they
  move to Phase 3, where the first one is built.
- ~~Two baselines: BM25 only, dense only. Choose the embedding model (ADR).~~ Done: BM25
  (ADR 0006) and BGE-M3 ([ADR 0007](decisions/0007-embedding-model.md)).

**Test results, 2026-09-30** (`results/test/`, 50 answerable items, commit 9306d9f):

| Retriever | recall@1 | recall@10 | temporal recall@10 | explicit_reference recall@10 |
|---|---|---|---|---|
| BM25 | 0.47 | 0.70 | 0.86 | 0 of 8 |
| Dense (BGE-M3) | 0.58 | 0.79 | 1.00 | 0 of 8 |

On dev (40 answerable): BM25 0.64 and dense 0.74 recall@10, explicit references 0 of 8.

What the numbers say: dense beats BM25 mostly on vocabulary ("morre" where the law says
"falecimento"); the date filter keeps temporal questions from being harder than others at the
retrieval step; and no retriever finds a question that names its article, because article
numbers are not in the article text. That gap, 16 of 100 items, is the first thing Phase 3 fixes
(ADR 0004). Two temporal items turn on effects and transitional provisions the store cannot
represent (bench/README.md, rule 6); their failures will show in answer scoring, not retrieval.

Reviewing the items found 14 places where the ACT's own material is behind or off the law:
outdated definitions and rules from before Leis n.os 83/2021 and 13/2023, paragraphs cited by
their pre-2023 numbers, a wrong article number, a loosened threshold. The items follow the law
and record each difference in their notes.

**Double check, 2026-09-30.** Lint, types, 55 tests, the harness arithmetic (recomputed from
the retrieved lists), determinism (a re-run reproduces every number), all 80 source URLs, every
cited article against the corpus, and the numbers in every answer against the cited articles'
versions all passed. It found one real problem: under the id-based split, some dev items
answered test items. Splits are now grouped by main article
([ADR 0009](decisions/0009-split-by-main-article.md)); the earlier test runs are kept in
`results/test/superseded/` and not reported.

**Exit:** ~~baseline numbers on dev and test in `results/`.~~

**Unlocks** (benchmark v0, superseded by later versions' numbers): "Built a 100-question benchmark for Portuguese labour law, with temporal questions
and deliberate out-of-scope traps; dense retrieval recall@10 0.79 vs BM25 0.70 on the held-out
test set."

## Phase 3: Reference system (done 2026-09-30)

Built one step at a time; each step stays only if dev improves:
reference parser, hybrid fusion, reranker, answers with citations, `as_of` filtering, refusal
threshold. Served through a FastAPI API. Choose the LLM and the reranker (ADRs 0010, 0011).
The answer harness scores citation precision and recall and refusals (moved from Phase 2).

**Progress, 2026-09-30** (dev, 40 answerable items; recall@1 / recall@10):

| Step | Result on dev | Kept |
|---|---|---|
| Dense baseline | 0.61 / 0.74 | starting point |
| + reference parser (ADR 0004) | 0.81 / 0.94; explicit references 0 -> 8 of 8 | yes |
| Hybrid BM25 + dense (RRF) | 0.72 / 0.93 | no, below the parser alone |
| + reranker (ADR 0010) | 0.84 / 0.96 | yes, one or two questions |

Retrieval for the reference system is dense + reranker + reference parser.

Answers: a language model reads the top 5 article versions in force on `as_of` and answers
with citations or refuses; citations of articles it was not given are dropped, and an answer
left without any becomes a refusal. `python -m lex.eval answers` scores citation precision and
recall and refusals per type; `python -m lex.api` serves the system. The planned model is
Gemini ([ADR 0011](decisions/0011-answer-llm.md)), but its project had no prepaid credits, so
the model measured is a local Gemma 4 E2B at 4 bits on llama.cpp
([ADR 0012](decisions/0012-local-answer-model.md)), small enough for the Raspberry Pi idea.

| Step (dev, top 5 unless stated) | Citation recall / precision | Refused: answerable, unanswerable | Kept |
|---|---|---|---|
| Gemma 4 E2B, local (ADR 0012) | 0.84 / 0.89 | 2 of 40, 5 of 6 | as the local option |
| Gemma 4 E2B, top 10 | 0.85 / 0.88 | 4 of 40, 4 of 6 | no, no gain; differences are sampling noise |
| Gemma 4 E4B, local in LM Studio | 0.84 / 0.81 | 3 of 40, 5 of 6 | no, below the E2B |
| Gemini 3.1 Flash-Lite (ADR 0011) | 0.91 / 0.95 | 1 of 40, 6 of 6 | yes, the reference system's model |
| Gemini, top 10 | 0.93 / 0.92 | 1 of 40, 6 of 6 | no, recall gained what precision lost, for twice the input |
| Refusal threshold on retrieval scores | not measured | | not built: dev has 6 unanswerable items, too few to fit a threshold to, and Gemini refuses all 6 |

With Gemini, every recall loss on dev is retrieval's: 6 composite questions whose second article
is not in the top 5. Its precision losses are related articles cited beyond the labels (articles
344 to 348 next to 343 on when a contract lapses, for example). The E2B adds its own errors: a
neighbouring article cited twice and an out-of-corpus question answered. Answer correctness is
not measured yet: it needs an LLM judge and hand labels on dev to measure its agreement against.

**Test results, 2026-09-30** (`results/test/`, 50 answerable and 4 unanswerable items):

| Retrieval | recall@1 | recall@10 | composite recall@10 | explicit_reference recall@10 |
|---|---|---|---|---|
| BM25 (Phase 2) | 0.47 | 0.70 | | 0 of 8 |
| Dense (Phase 2) | 0.58 | 0.79 | | 0 of 8 |
| Dense + reranker + reference parser | 0.80 | 0.95 | 0.81 | 8 of 8 |

| Answers (top 5, all answerable) | Citation recall | Citation precision | Wrongly refused | Unanswerable refused |
|---|---|---|---|---|
| Gemini 3.1 Flash-Lite (reference) | 0.90 | 0.93 (48 answers) | 2 of 50 | 3 of 4 |
| Gemma 4 E2B, local | 0.85 | 0.86 (46 answers) | 4 of 50 | 2 of 4 |

| Gemini, per type | Citation recall | Citation precision | Wrongly refused |
|---|---|---|---|
| composite | 0.75 | 0.94 | 0 of 8 |
| explicit_reference | 1.00 | 1.00 | 0 of 8 |
| simple | 0.93 | 0.90 | 1 of 27 |
| temporal | 0.86 | 0.92 | 1 of 7 |

What the numbers say: on test as on dev, the parser and the reranker take retrieval from 0.79 to
0.95 recall@10 and find every question that names its article. Gemini beats the local Gemma 4 E2B
on every measure, on dev and on test; the E2B, small enough for a 4 GB Raspberry Pi, stays within
about 0.05 on citation recall. Composite questions are the weak spot: the second article is
often not retrieved. Refusing out-of-scope questions rests on 10 items in all (dev and test),
too few to say more.

**Exit:** ~~a test run in `results/` with per-type numbers; every step kept has its dev delta in
its commit message.~~

**Unlocks** (benchmark v0, superseded by later versions' numbers): "Built a retrieval-augmented system for Portuguese labour law that answers with
dated article citations: on a held-out test set, recall@10 0.95 (from 0.79 for dense retrieval
alone), every question that names its article found, citation recall 0.90 and precision 0.93
with Gemini 3.1 Flash-Lite, and 0.85 and 0.86 with a local model small enough for a Raspberry Pi
(Gemma 4 E2B, 4-bit)."

## Phase 4: Public demo (done 2026-10-01)

A playground (answer, clickable citations, article version timeline) and a leaderboard built from
`results/`. Rate limit and a budget cap. The disclaimer on every page.

- Live at https://lex-beryl.vercel.app on Vercel's free tier
  ([ADR 0014](decisions/0014-serverless-demo.md); Hugging Face now wants PRO for Docker,
  [ADR 0013](decisions/0013-demo-hosting.md)). Both models are on Gemini's free tier, so the
  demo cannot cost anything: past the day's quota it says so, and says which limit it met.
- The page, in Portuguese or English: answers with a dated citation after every sentence, each
  opening its article; the time each stage took; shareable links to an answer or to an article on
  a date; an Articles tab that needs no model (by number or word, any date); each article's
  timeline and what changed from its previous version, marked as a reviser would; the test
  leaderboard; a dark "night edition". `web/e2e.py` checks it in a browser, in both colour schemes.
- Around it: an MCP server over the code (`python -m lex.mcp_server`); a weekly check that the
  code has not been amended since the corpus (`python -m lex.ingest check-updates`); the page's
  examples answered at deploy.

**The demo's system on dev** (40 answerable and 6 unanswerable items): Gemini Embedding 2 over
the corpus in memory, the reference parser, Gemini 3.1 Flash-Lite reading the top 5. Retrieval
alone: recall@5 0.95 (BGE-M3 with the parser 0.90, with the reranker 0.93).

| Variant (dev) | Citation recall / precision | Refused: answerable, unanswerable | Kept |
|---|---|---|---|
| Answer, then its sources | 0.93 / 0.97 | 1 of 40, 5 of 6 | starting point |
| + cross-references (`+xrefs`) | 0.91 / 0.94 | 2 of 40, 5 of 6 | no |
| `reasoning_effort` minimal instead of low | 0.90 / 0.97 | 2 of 40, 5 of 6 | no |
| A citation per sentence (`--format claims`) | 0.93 / 0.95 | 1 of 40, 6 of 6 | yes ([ADR 0014](decisions/0014-serverless-demo.md), amended) |
| Question decomposition (`+decomp`) | composite recall@5 0.72, from 0.78 | | no, dropped at retrieval |

The per-sentence format refuses the out-of-scope question the other answered, and makes as many
citations outside the labels (4 of 47); ADR 0014 has the item-by-item reading.

**Test results, 2026-10-01** (`results/test/`, commit c0d4d37; 50 answerable and 4
unanswerable items):

| The demo's system | Result |
|---|---|
| Retrieval recall@1 / recall@10 | 0.78 / 1.00 (reference system 0.80 / 0.95) |
| Citation recall / precision | 0.94 / 0.94 (reference system 0.90 / 0.93) |
| Wrongly refused, unanswerable refused | 2 of 50, 3 of 4 (the same as the reference system) |
| Composite questions: citation recall | 0.75 (the same) |

**Latency** (`python -m lex.eval latency`: 15 dev questions asked one at a time from Portugal,
`results/dev/`). The first timing failed 3 of 15: Gemini answered at once that it was
overloaded (HTTP 503), the demo gave up and the page blamed the daily limit. The demo now asks
an overloaded model twice more within 3 s and tells the visitor which failure it met. Timed
again: 0 of 15 failed, though no overload happened that time, so the retry is checked by tests
only; over the 14 answers after the first (which may meet a cold start, 3.83 s), total p50
3.93 s and p95 6.12 s, retrieval p50 0.23 s, generation p50 3.48 s and p95 5.65 s.

What the numbers say: with no reranker and no server, the demo's system scores above the
reference system on test, and its retrieval puts the right article in the top 10 for every test
question. The two differ in two ways (the embeddings and the per-sentence format), so this says
which is better, not why. Composite questions stay the weak spot, and neither cross-references
nor decomposition helped them on dev.

**Exit:** ~~a public URL, linked from the README, with the demo's own test numbers on its
leaderboard.~~ Linking it from the CV is Tiago's.

**Unlocks** (benchmark v0, superseded by later versions' numbers): "Deployed a public demo that answers questions on Portuguese labour law with a
dated citation per sentence, at no cost (Vercel and Gemini free tiers): citation recall 0.94 and
precision 0.94 on the held-out test set, answers in 3.93 s at the median."

## Phase 5: Answer correctness (done 2026-10-01)

Citation recall and precision say whether an answer rests on the right articles, not whether it
is right; a demo answer about 2011 added a true sentence from an article it did not cite, which
they cannot see. Built: an LLM judge against each item's reference answer
([ADR 0015](decisions/0015-answer-judge.md)) and a terminal tool for hand labels.

- ~~Tiago labels about 40 dev answers (`python -m lex.eval label SYSTEM`).~~ Tiago chose not to
  (2026-10-01). Instead the judge must pass known-answer checks on dev first: the reference
  answers as they are, and with a quantity changed or a yes or no turned over
  (`python -m lex.eval judge-check`, [ADR 0015](decisions/0015-answer-judge.md) amended). A
  weaker measure than hand labels, reported as such; `label` and `judge` still work.
- ~~Report correctness per type on test, next to how the judge was measured
  (`answers --judge`).~~
- If a claim-level measure is needed (sentences the cited articles do not support), it gets its
  own hand labels first.

**The judge** ([ADR 0015](decisions/0015-answer-judge.md), amended): Gemma 4 26B A4B, because
Gemini 3.8 Flash's free tier allows 20 requests a day. On the known-answer checks it accepted 40
of 40 dev reference answers and caught 28 of 28 altered ones (16 with a quantity changed, 15 of
them judged wrong and 1 partial; 12 with the yes or no turned over, all wrong), against a bar of
90% each set before it ran (`results/dev/judge-check.json`).

**The demo's system, judged** (a refusal of an answerable question counts as wrong):

| Split | Correct | Partial | Wrong | Composite correct |
|---|---|---|---|---|
| dev, 40 answerable | 0.75 | 0.20 | 0.05 | 0.56 |
| test, 50 answerable (2026-10-01, commit 089db08) | 0.82 | 0.10 | 0.08 | 0.75 |

On test, per type: explicit references 1.00 correct, temporal 0.86, simple 0.78, composite 0.75.

What the numbers say: on dev, the judge's partial verdicts name conditions an answer left out
(the six-month limit for challenging a collective dismissal, the right to a temporary post's
better conditions), and its one wrong verdict on a real answer is a real error: the answer took a
holiday removed in 2012 as gone that year, when its removal only took effect in 2013. The checks
show the judge catches clear errors; how it treats ambiguous answers needs hand labels, which
stay the stronger measure (`label`, then `judge`).

**Exit:** ~~correctness on test in `results/`, with how the judge was measured.~~

**Unlocks** (benchmark v0, superseded by later versions' numbers): "Measured answer correctness with an LLM judge checked on known-answer cases (40 of
40 right answers accepted, 28 of 28 altered ones caught): 82% of the demo's answers on the
held-out test set judged correct."

## Phase 6: Wider corpus, benchmarks v1 and v2, publication (done 2026-10-06 but the legal review)

Phases 3 to 5 report their test numbers on benchmark v0 (54 test items). From 2026-10-01 the
README and the leaderboard report v1; v0's test runs are kept in `results/test/v0/`.

- ~~Grow the benchmark to 150 to 200 items, first where it is thinnest: `unanswerable` (10) and
  `composite` (17, the weakest type).~~ Done 2026-10-01: **benchmark v1, 158 items**, from two
  batches drawn from the ACT's FAQ (07 and 08, 58 items). `unanswerable` 10 -> 29 (out-of-corpus
  regimes a question could be mistaken for: domestic service, work accidents, health and safety
  services, road transport, asbestos, disability quotas, retirement, social-security benefits,
  the meal allowance), `composite` 17 -> 33, `temporal` 15 -> 22 (among them absences for a death
  in 2022, when a spouse's gave five days and a child's twenty), and recent law such as the 2025
  absence for endometriosis. A new `validate` check refuses a second item from an FAQ entry about
  the present; it caught four drafts that repeated entries already in the benchmark. Dev 70
  items, test 88. Every run now records which version of its split it used; runs on the
  intermediate 132-item state are kept in `results/test/v1-132/`.

  **Test results on v1, 2026-10-01** (`results/test/`, commit e8f11ed; 75 answerable and 13
  unanswerable items):

  | Retrieval | recall@1 | recall@10 | explicit references | composite recall@10 |
  |---|---|---|---|---|
  | BM25 | 0.48 | 0.75 | 0 of 8 | 0.75 |
  | Dense (BGE-M3) | 0.59 | 0.83 | 0 of 8 | 0.85 |
  | BGE-M3 + reranker + parser (reference) | 0.76 | 0.96 | 8 of 8 | 0.88 |
  | Gemini Embedding 2 + parser (the demo) | 0.71 | 0.99 | 8 of 8 | 0.97 |

  | Answers (Gemini 3.1 Flash-Lite, top 5) | Correct | Citation recall / precision | Refused: answerable, unanswerable | Composite: recall, correct |
  |---|---|---|---|---|
  | The demo (a citation per sentence) | 0.76 | 0.92 / 0.94 | 2 of 75, 11 of 13 | 0.71, 0.50 |
  | Reference (BGE-M3 + reranker) | 0.67 | 0.89 / 0.91 | 2 of 75, 11 of 13 | 0.71, 0.50 |
  | BGE-M3 without reranker | not judged | 0.87 / 0.91 | 2 of 75, 12 of 13 | 0.64, not judged |

  On dev (70 items) the demo: 0.70 judged correct, citation recall 0.85 and precision 0.93, 3 of
  54 answerable questions wrongly refused, all 16 unanswerable ones refused. The judge passed its
  known-answer checks on v1's dev (54 of 54 references, 41 of 41 altered
  answers). What the numbers say: with nearly three times as many out-of-scope
  questions, refusing what the Code does not cover holds up (11 or 12 of 13 on test, 16 of 16 on
  dev). Composite questions remain the weak spot, half of them judged correct; their misses on
  dev are a second article left out (art. 199.º-A next to 169.º-B on telework, 101.º-G next to
  101.º-C and 101.º-D for carers) or a refusal. The demo leads the reference system on
  correctness (0.76 against 0.67), mostly through fewer partial answers; the two differ in
  embeddings and in answer format, so this does not say which change helps.
- ~~Add tenancy (Código Civil and NRAU)~~; the Código do IRS waits ([ADR 0017](decisions/0017-tenancy.md)).
  Tenancy's corpus is in, 2026-10-01: the Código Civil's articles 1022.º to 1113.º (94
  articles, 147 versions) and the NRAU (86 articles, 177 versions), every version dated from the
  DR, with the PGDL's labels corrected where they credit a republication, three of the DR's own
  dates corrected, and 48 spot checks against the DR's history (all agree but two, where the
  DR is the one wrong). Retrieval, answers, the MCP server and the page work across the three
  diplomas: articles are cited by id ("CT 238", "NRAU 9"), a bare article number goes to the
  diploma the question speaks of, and the page has a diploma list and `dip=` links.

  **Benchmark v2, 181 items** (2026-10-02): 23 tenancy items (`ar-`), 14 in dev and 9 in test,
  from the DGAJ's pages on the eviction procedure (tribunais.org.pt) and the Diário da
  República's Lexionário; gov.pt and the Portal da Habitação, whose terms allow only
  non-commercial reuse, are not used. Dev 84 items, test 97. v1's test runs are in
  `results/test/v1/`.

  On dev, the demo's retrieval was weakest on tenancy (recall@5 0.63 on 12 items against 0.89 on
  labour): the eviction procedure's 22 articles read alike. Embedding questions in Gemini
  Embedding 2's documented query format (ADR 0014, amended) took dev recall@5 from 0.84 to 0.90,
  tenancy to 0.92; on test the demo's recall@1 went from 0.71 to 0.79.

  **Test results on v2** (`results/test/`; 80 answerable and 17 unanswerable items):

  | Retrieval | recall@1 | recall@5 | recall@10 | composite recall@10 |
  |---|---|---|---|---|
  | BM25 | 0.48 | 0.69 | 0.74 | 0.71 |
  | Dense (BGE-M3) | 0.59 | 0.79 | 0.82 | 0.83 |
  | BGE-M3 + reranker + parser (reference) | 0.76 | 0.91 | 0.95 | 0.85 |
  | Gemini Embedding 2 + parser (the demo) | 0.79 | 0.96 | 0.99 | 0.97 |

  | Answers (Flash-Lite, top 5) | Correct | Citation recall / precision | Refused: answerable, unanswerable | Composite: recall, correct |
  |---|---|---|---|---|
  | The demo (a citation per sentence) | 0.71 | 0.92 / 0.92 | 0 of 80, 15 of 17 | 0.67, 0.41 |
  | Reference (BGE-M3 + reranker) | 0.72 | 0.90 / 0.89 | 1 of 80, 14 of 17 | 0.70, 0.53 |

  On dev (84 items) the demo: 0.68 judged correct (labour 37 of 54, tenancy 8 of 12), citation
  recall 0.83 and precision 0.90, 4 of 66 answerable questions refused, all 18 unanswerable ones
  refused. The judge passed its known-answer checks on dev v2: 66 of 66 references, 48 of 48
  altered answers. What the numbers say: correctness on test fell from v1's 0.76 to 0.71, almost
  all of it into partial answers (0.26), not wrong ones (0.03); composite questions remain the
  weak spot, and their articles are mostly retrieved, so what is left out is the answer's. The
  reference system, behind the demo on v1 (0.67 against 0.76), is level with it on v2 (0.72
  against 0.71) and ahead on composite questions (0.53 against 0.41).
  A fault found on the way: the reference system's BGE-M3 embeddings were never committed to
  the store, so each run embedded tenancy again (results unaffected; fixed).

  **Benchmark v3, 201 items** (2026-10-06): twenty more tenancy items from the Lexionário (batch
  12): 11 answerable, four of them temporal (rules changed between 2018 and 2023), and 9
  unanswerable, rules outside the corpus a tenancy question can be mistaken for. Dev 92, test 109;
  43 tenancy items. v2's test runs are in `results/test/v2/`. On test v3 (89 answerable, 20
  unanswerable): retrieval recall@1 / @10 BM25 0.49 / 0.74, BGE-M3 0.58 / 0.81, reference
  0.76 / 0.94, the demo 0.81 / 0.99; answers judged correct: the agent 0.76, the per-sentence
  prompt 0.73, the reference 0.73 (citation recall 0.94, 0.93, 0.89). `python -m lex.eval
  check-results`, now in CI, keeps every number in `results/` adding up and the leaderboard on one
  test split.
- Legal review by a law student or lecturer (Faculdade de Direito, Universidade Lusófona).
- ~~Licences for the code and the data, with a decision on whether test stays hidden.~~ Done
  ([ADR 0016](decisions/0016-licences-and-hidden-test.md)): MIT for the code, CC BY 4.0 for the
  benchmark, and the test split private. A search of every tracked file found test items quoted
  in two ADRs and a parser fixture, now removed. `python -m lex.bench snapshot` writes the public
  mirror and refuses it while any file holds test content or a key.
- ~~Then the repo public, as that mirror~~: https://github.com/timimata/lex, from 2026-10-01 (its
  CI passes without the test split). ~~The benchmark's dev split on Hugging Face Datasets~~:
  https://huggingface.co/datasets/timimata/lex, with its card (`bench/DATASET_CARD.md`).
- Keep the corpus current: the weekly amendment check is in place; rebuilding after an
  amendment stays a person's call, since dating new versions needs checking.

## Phase 7: Optional (done 2026-10-07, the agent; the rest stays optional)

Chosen by what the numbers and job ads say:
- fine-tuned embeddings (was Phase 5): Gemini Embedding 2 already finds the right article in the
  top 5 for 0.95 of dev questions, and 40 dev items cannot tell a small gain from noise, so it
  waits for benchmark v1; it also needs a GPU this machine cannot give PyTorch;
- ~~an agent for `composite` questions~~: built without a framework (`--format agent`) and not
  kept ([ADR 0018](decisions/0018-agent.md)). On dev v2 the model never asked for more (0
  searches and 0 reads in 168 answers), yet its prompt scored 0.74 correct in both of two runs
  against the per-sentence format's 0.68 and 0.70, and refused none of the 66 answerable
  questions against 4 (all 18 unanswerable refused either way). The gain is the prompt's, and
  two runs of the same system differ by about one item (`--repeat`). The coverage instruction
  alone (`--format claims-cover`) scored 0.65, no gain; the rest of the agent's prompt, that the
  model may ask and should answer when the articles suffice, is what helped (ADR 0018, amended).
  On v3 the agent leads again on dev (0.74 against 0.68) and on test (0.76 against 0.73), still
  with 0 requests, and since 2026-10-07 it is the demo's system, with a 9 s budget on any request
  (ADR 0018, amended). The documents' own format for Gemini Embedding 2 changed nothing in the
  top 5 the model reads (ADR 0014, amended 2026-10-07);
- tracing (Langfuse), model routing, cost per question;
- a local model for the answers on a Raspberry Pi (ADR 0012 has the quality; speed not measured);
- a hand-scored comparison with Lia and TogaAI on a small dev subset, after checking their terms.

## Phase 8: Operating the demo (done 2026-10-07)

The demo is public and the benchmark measured; what is missing is knowing, without looking, that
it still works, what it costs, and that a change to a prompt has been measured before it ships.
Every check here runs without spending the model's quota unless it says so.

1. **No prompt ships unmeasured.** Every answers run records a fingerprint of the prompts it
   used (the answer prompts, the query format, the judge's prompt). CI, which has no key, fails
   when the demo's prompts differ from those of its last dev run in `results/`: change a prompt
   and the dev run comes with it. `python -m lex.eval regress` (spends dev's quota) runs the
   demo's system on dev again and fails if it answers correctly fewer questions than the
   committed run by more than the noise measured (ADR 0018), or wrongly refuses more.
   *Exit:* CI fails on a changed prompt with no new dev run (tested); `regress` passes on main.
   **Done 2026-10-07:** answers runs record `prompts`; `check-results` (CI) holds the demo's dev
   run to the prompts and query format of today's code; `regress` on main: 50 -> 50 correct, 0 ->
   0 answerable refused (from the cache, no quota).
2. **Usage, quota and latency, from the demo itself.** Each answer writes one JSON line to the
   platform's log (outcome, seconds, calls, tokens, cost at paid prices); `/api/usage` gives the
   counts of the instance answering since it started: answers made and served from the cache,
   visitors turned away by the limits, quota and overload failures, latency p50 and p95, tokens
   and cost. Vercel runs several instances and keeps no state, so the endpoint says it is one
   instance's view. *Exit:* tested on a scripted system, served on the live demo.
   **Done 2026-10-07, live:** `/api/usage` and a JSON line per answer, with
   outcomes `answered`, `cached`, `limited` and `failed_<kind>` (quota per day or minute,
   overloaded, timeout, other); tested with a scripted model reporting tokens.
3. **An outside probe that alerts.** A scheduled GitHub workflow runs `python -m lex.probe URL`
   every six hours: health, an article on a date, a word search and a cached example answer
   (no quota), each timed, plus the instance's usage. It fails on an error or a request slower
   than its bar, and a failed workflow is GitHub's email to the owner. *Exit:* the workflow green
   against the live demo, and red against a wrong URL.
   **Done 2026-10-07:** `src/lex/probe.py` (standard library only) and `.github/workflows/probe.yml`;
   against the live demo before this deploy, 5 of 6 checks pass (`/api/usage` is not deployed yet:
   the probe is right to fail it); after the deploy, 6 of 6, and the workflow's first run on
   GitHub is green; against a wrong URL, 5 of 6 fail. Bars: 20 s for the first
   request, which may wake a cold function, 5 s for the rest.
4. **Cost per day.** At the agent's measured cost on test v3 ($0.00106 a question at paid
   prices), the gate's daily cap bounds what the demo would cost; `/api/usage` gives an
   instance's actual figure. *Exit:* the bound in the README, computed from `results/`.
   **Done 2026-10-07:** $0.001058 a question (`results/test/2026-10-07T1749-…+agent.json`, every
   call's thinking recorded) times the 400 a day of `LEX_ANSWERS_PER_DAY`: at most $0.4232 a day
   at paid prices.
5. **What changed between two dates.** A page and `/api/changes`: choose a diploma and two
   dates, and get every article whose text changed in between, grouped by the amending law, each
   opening its comparison. No model, no quota. *Exit:* checked in `web/e2e.py` on Lei n.º
   13/2019's changes to the Código Civil.
   **Done 2026-10-07:** `/alteracoes` and `/api/changes` (`Corpus.changes`): each version that
   came into force in the period, marked changed, added, revoked or original, grouped by the law
   and the day; an article opens on its changes from the previous version. In 2019 the Código
   Civil has one group, Lei n.º 13/2019 from 13/02/2019, 15 articles (13 changed, 2 added); art.
   1041.º opens with "50%" struck and "20 %" added. Checked in `web/e2e.py`, axe included.

## Phase 9: What a score rests on (done 2026-10-08 but the legal review itself)

A review after Phase 8 (2026-10-07) found places where a number can mean less than it says:
reference answers sent to a free-tier API, splits that can share a question's source, corpus
checks that never run in CI, verdicts and the articles behind an answer that are not kept. This
phase closes them for the benchmark and the judge. It runs no test split: the next test run is
Phase 10's milestone, once the split, the judge and what a run records have settled, so the
leaderboard moves once.

1. **Correct what is false today.** The README gives the demo's dev v2 recall@5 (0.90) among v3
   numbers; on dev v3 it is 0.89, and the reference system's 0.85 (`results/dev/`). The README
   and the dataset card report the judge's known-answer checks (66 of 66, 48 of 48) without
   saying they ran on dev v2 (`results/dev/judge-check.json`, 84 items). CLAUDE.md says "Seeds
   are fixed", but no seed is sent (ADR 0011). *Exit:* each of these says which version it
   stands on, or is gone; CLAUDE.md says what makes a run reproducible (the cache) and how its
   noise is measured (`--repeat`).
   **Done 2026-10-07:** the README gives dev v3's recall@5 (0.89 against 0.85), the README and
   the card say the judge's checks ran on v2's dev, and CLAUDE.md says no seed is sent.
2. **Say what leaves the machine.** ADR 0011 says the reference answers are never sent. The judge
   sends them: `judge.prompt` puts each item's question and reference answer, with the system's
   answer, in a request to Gemma on Gemini's free tier, whose prompts Google may use to improve
   its products; on test, these are test items. Amend ADR 0016 with every flow (what each command
   sends, to whom, on what terms: answers, the judge, embeddings, `latency`, the demo's visitors,
   and `HttpSystem` once 12.5 builds it), and decide, for test runs, between a paid key and a
   judge run locally (the same Gemma 4 26B A4B weights on llama.cpp: a new model id, so measured
   again by 9.11). No test run until then. *Exit:* ADR 0016 amended and ADR 0011 corrected; each
   run records the endpoint of every model it called and the key's tier (a setting); the page
   says where a visitor's question goes.
   **Done 2026-10-08:** Tiago chose a paid key. ADR 0016's amendment lists every flow with
   Google's terms as read that day; runs record `endpoints` (URL and tier per model);
   `ensure_private` refuses a test run that would reach a free tier (tested), so none starts
   until `LLM_KEY_TIER=paid`; the page's note under the question field waits for the next deploy.
   **Reversed 2026-10-09:** Tiago accepts the free tier for test runs (ADR 0016, amended);
   `FREE_TIER_ON_TEST` lets them start, runs still record each endpoint's tier, and the card's
   contamination note says what is sent.
3. **Close the leaks between splits.** `group_of` (`src/lex/bench/splits.py`) groups items by
   their first `must_cite` alone, so two items from the same source page, or sharing a secondary
   article, can sit in different splits, and an ACT FAQ entry can give a present-day item to one
   split and a temporal item to the other. Dev alone has 7 source URLs shared by two to five
   items each. `validate` lists, by id only, every pair across splits that shares a source URL or
   a `must_cite` article; `assign` refuses an incoming item whose source or articles are already
   in the other split. With the count known, amend ADR 0009: move the test side of each pair to
   dev, never the reverse (dev is public on Hugging Face, so a dev item can never become a test
   item), as benchmark v4; or keep the pairs and report their count. A re-split is applied at
   Phase 10's milestone, with the test runs it forces. *Exit:* `validate` lists the pairs;
   `assign` refuses a constructed leaking item (tested); ADR 0009 amended.
   **Done 2026-10-08:** 45 pairs on v3, none sharing a FAQ entry; 14 share one item's main
   article, putting 13 test items in a group with dev items. ADR 0009, amended: a group takes
   in every item linked by a main article or a FAQ entry, and a group spanning the splits goes
   to dev. `assign` places an incoming item in its group's split and refuses one linking both
   (tested); `python -m lex.bench resplit` moves the 13 at the milestone (test 96, dev 105).
4. **A leak scan that catches paraphrase.** `find_leaks` (`src/lex/bench/snapshot.py`) finds a
   test question only verbatim and an answer only by its first 120 characters; a reworded
   question, or a sheet that pairs a test id with its article, passes into the public mirror.
   Add word-shingle overlap with each test question and answer, and refuse a file where a test id
   appears near one of that item's `must_cite` articles. Messages still name the file only.
   *Exit:* a reworded question, a reworded answer and an id beside its article are each refused
   (tested); the current tree passes.
   **Done 2026-10-08:** a file is refused when it holds half or more of the six-word runs of a
   test question or answer that neither the law nor dev holds, or a test id within 200
   characters of one of its articles. It found one real leak: ADR 0009 named test items beside
   their articles since Phase 2 (public in the mirror since 2026-10-01); its lines no longer do.
   Chance overlaps in the tree (legal phrasing in dev answers and sheets) hold a third at most.
5. **The corpus checks in CI, from an index.** `data/` is not committed, so in CI `validate`
   prints "no corpus" and checks no citation or date against the law. Commit an index of the
   corpus without its text: per version, its diploma, article, `valid_from`, `valid_to`,
   `introduced_by` and the sha256 of its heading and text, written by the ingestion and checked
   against `data/processed/` wherever that exists. `validate` reads the periods from the index
   when there is no corpus. *Exit:* CI checks every citation and `as_of` against the index; an
   item citing an article not in force on its date fails CI (tested).
   **Done 2026-10-08:** `corpus/index.jsonl`, 1,213 versions, written by `python -m lex.bench
   index`; without the corpus `validate` checks every citation and date against it (tested),
   and with the corpus it fails if the index is out of date.
6. **A legal review that leaves a record.** `status` and `validated_by` are in the schema, but
   nothing sets them: the 92 dev items are all `draft`, reviewed by `claude-opus-5.5` and
   validated by no one. First, `bench_version` hashes only what a run reads (id, question,
   `as_of`, type, citations, answer), so validating an item does not make every test run stale;
   the current runs get that hash once. Then `python -m lex.bench review ID --by NAME` records a
   person's validation (`validated_by` and a new `validated_on`) or a correction, which changes
   the hash, as it should. `validate`'s summary and the dataset card count validated items by
   split, and results can be reported on them apart (bench/README.md, rule 1). The reviewer
   reviews test items alone: the command shows them in the terminal only, and no model runs it.
   *Exit:* the command tested on dev; the card's count produced by script; the review itself
   (Phase 6) under way.
   **Done 2026-10-08, but the review itself:** runs carry `bench.scored`, a hash of what a run
   reads, and are compared by it (the 14 runs on today's splits were given it); `review` shows
   the item, asks, and records `validated_by` and `validated_on` (tested: the file's hash moves,
   `scored` does not); `python -m lex.bench card` writes the card's counts, validated items
   among them, and `validate` fails when they are out of date. 0 items validated: the review
   waits for a reviewer at the Faculdade de Direito.
7. **Keep each verdict and its reason.** `judge.parse` keeps the verdict and drops the judge's
   `razao`, and `answer_run` keeps only the shares, so `check-results` cannot recompute a
   correctness number, the README's headline among them. Dev runs keep each item's verdict and
   reason; test runs keep each item's id, verdict, refusal and citation scores, with no text and
   no citations, which amends ADR 0016 ("summaries carry no items") and the check in
   `vercel/assemble.py`. *Exit:* `check-results` recomputes `correctness` wherever a run reports
   it; an edited verdict fails CI (tested).
   **Done 2026-10-08:** answers runs keep `verdict` and `reason` per item (test runs the verdict
   and the scores by id, ADR 0016 amended); `check-results` recomputes correctness from them for
   every run from 2026-10-08 on, test runs included, and fails one that reports correctness
   without them (tested). Older runs keep shares only, until rerun.
8. **Record what the model was given.** A run records what an answer cites, not what the model
   read: an article retrieval missed and one the model left out look the same, and an answer made
   with no `must_cite` article in hand cannot be counted. `Answer` gains the articles given, with
   their versions, from both `ReferenceSystem` and `AgentSystem`; the harness splits citation
   recall's losses into retrieval and generation, and counts answers made without support.
   *Exit:* a dev run of the demo's system reports both losses and the unsupported answers, per
   type.
   **Done 2026-10-08 in code:** `Answer.given` holds each article version the model read, from
   both systems; runs report `given_recall` (recall's loss down to it is retrieval's, the rest
   the answer's) and `unsupported` answers, per type (tested). The dev run that reports them
   closes the phase. Reported by the demo's dev run of commit e08cd35: given recall 0.89 against
   citation recall 0.86 (composite 0.71 and 0.61), 0 answers without support.
9. **Score the version, not only the article.** A temporal item is scored by article id. The
   answer names the version in its sources, but nothing records or checks it, though answering
   for a date is the benchmark's distinctive claim. Record each cited article's version, check it
   is the one in force on `as_of` against the index (9.5), and report version accuracy on temporal
   items. The reference system is right by construction; the check is there for a regression and
   for systems scored from outside (12.5). After 9.5 and 9.8. *Exit:* a scripted system citing
   today's version on a temporal item scores 0 on it (tested); dev runs report it.
   **Done 2026-10-08 in code:** `version_right` per item and per type, from `Answer.given` and
   the index (tested on a temporal item answered with the 2011 text and with today's); answers
   runs read the index. The dev run at the phase's exit reports it: 1.00 on every type
   (commit e08cd35), as the reference system's construction gives.
10. **Keep the cache's dates in sight.** The LLM cache is keyed on model, parameters and prompt,
    with no date, so a model changed by its provider under the same name goes unseen: test v3's
    per-sentence run took 108 of its 109 answers from the cache. Each run records the oldest and
    newest `made_at` among the responses it used; at milestones the answers are asked afresh (a
    new sample, as `--repeat` asks) and compared with the cached run (10.2). *Exit:* every
    answers run records its cache's dates; Phase 10's milestone runs answer from no cache.
    **Done 2026-10-08 in code:** answers runs record `cache` (calls, cached, the oldest and
    newest `made_at`) for the model and the judge; `answers --fresh` asks both again, a sample
    named for the day that a re-run that day reuses, without renaming the system (tested).
11. **The judge measured on today's dev, and for leniency.** `results/dev/judge-check.json` ran on
    dev v2, and `measured_judge` compares the judge's model and prompt but never the split, so a
    check made on an older dev still counts. Its cases test that the judge catches a changed
    number or a turned-over yes or no, not whether it is too lenient with an answer wrong in other
    ways. Record the dev version in the check and require it; add cases built by code: a reference
    answer with a contradicting sentence appended, and another item's reference answer. Their bar
    is set and committed before they first run, as ADR 0015's was. *Exit:* `judge-check` passes
    on the current dev with the new cases; `measured_judge` refuses a check made on another dev
    version (tested); ADR 0015 amended.

**Exit:** CI checks the splits and the corpus index; ADR 0016 says what leaves the machine; the
demo's system has a dev run that keeps each verdict with its reason, the articles given and their
versions, and its cache's dates; the judge passes on the current dev, leniency cases included.

**Phase 9 done 2026-10-08, but the legal review, which waits for a reviewer.** The judge passed
on v3's dev: 68 of 68 references, 48 of 48 altered answers, 110 of 110 lenient cases. The demo's
system on dev, all 92 answers and 68 verdicts from the cache (made 2026-10-05 to 2026-10-07):
0.74 correct, 0.22 partial, 0.04 wrong, as before; its model was given 0.89 of the must-cite
articles and cited 0.86, so retrieval accounts for most of what recall loses (composite: 0.71
given, 0.61 cited); 1 answer made with no must-cite article given (ar-0002); every cited version
the one in force on the date. Found on the way: Gemma 4 has no paid tier, so the judge needs
another home before a judged test run (ADR 0016, amended).

## Phase 10: Numbers anyone can recompute (done 2026-10-09)

Phase 9 makes a run keep what it rests on; this phase makes every number comparable,
recomputable from `results/` and reproducible from a commit, and ends with the one test run of
Phases 9 and 10.

1. **Cache writes that cannot half-happen.** The caches (`llm.Cached`, the ranking and embedding
   caches, `Vectors.save`, the fetcher's metadata) write in place: an interrupted run can leave an
   entry that no longer parses, and an entry in the test cache cannot be opened to repair it.
   Write to a temporary file and `os.replace` it; read a broken entry as a miss, set it aside and
   count it, never print it. It comes first so that the milestone's fresh runs stand on it.
   *Exit:* a write interrupted in a test leaves no broken entry; a broken entry is asked again
   and counted.
   **Done 2026-10-08:** `lex.atomic` writes beside the target and `os.replace`s it; the LLM,
   ranking and embedding caches, `Vectors.save` and the fetcher use it, and read a broken entry
   as a miss, set aside as `<name>.broken` and counted (`broken` in a run's `cache`), never shown
   (tested: an interrupted write leaves the old entry and no temporary file).
2. **Compare runs item by item.** `regress` fails when the demo answers more than two fewer dev
   questions correctly than its committed run (`REGRESSION_MARGIN`), a margin taken from two
   runs; totals hide which questions changed. `python -m lex.eval compare A B` pairs two runs by
   item (after 9.7), lists the items where they disagree, and gives an exact sign test on them;
   `regress` uses it instead of the margin. *Exit:* `compare` tested on constructed runs;
   `regress` passes on main; ADR 0018's noise restated as the items its two runs disagree on.
   **Done 2026-10-08 in code:** `lex.eval.compare` pairs runs by id, lists the items they
   disagree on, and gives an exact two-sided sign test; `regress` fails only on a loss of right
   answers, or a gain of refusals, that a one-sided test puts under 0.05 (tested: two lost and
   one gained is noise, five lost and none gained is not). `REGRESSION_MARGIN` is gone. The agent run
   and repeated on v3's dev: 50 of 68 correct both times, but 8 items change verdict, 4 each way;
   ADR 0018 and the README now say so. `regress` passes on main (2026-10-08, after the judge
   moved to temperature 0): 0 items changed, p = 1.00.
3. **More than one sample from the judge, and its failures named.** The judge answers once per
   answer, and a reply it cannot parse becomes `errada` with only a count (`Judge.unparsed`).
   `--judge-samples N` asks N cached samples, takes the majority, and records how often the
   samples disagree, the judge's own noise; an unparsed reply is asked once more and its id
   recorded; a test run with an unparsed verdict left fails. *Exit:* a dev run with three samples
   reports the judge's self-agreement; unparsed ids are in the run (tested).
   **Done 2026-10-08 in code:** `answers --judge-samples N` asks N draws of the judge and keeps
   their median (with three, the majority's; all three different, `parcial`) and each sample's
   verdict; runs record `disagreed`, `retried_ids` and `unparsed_ids`; a reply with no verdict is
   asked once more, and a test run with one left writes nothing (tested). `check-results` holds
   each verdict to its samples' median.
   **Measured 2026-10-08:** the demo's dev answers judged with three samples
   (`results/dev/archive/...+agent+judge-3-provider.json`, answers from the cache, the judge at
   the provider's temperature; item 5 then set it to 0): the samples disagree on 8 of
   the 67 answers judged, each time by one step (correct and partial 7 times, partial and wrong
   once), none unparsed, none asked again. The median changes 2 verdicts from the single-sample
   run, one each way, so 49 of 68 correct either way. The judge's own noise is of the size of
   the 8 verdicts two runs of the model change (10.2), which a repeat measures with the judge's
   noise in it.
4. **Say what "correct" hides.** The README and the leaderboard show the share judged correct,
   never the share wrong, and the rule behind it is not in `bench/README.md`. Write it there: the
   three verdicts as the judge's prompt defines them, a refused answerable question counted wrong
   without the judge, unanswerable items not judged, and what becomes of a reply the judge cannot
   parse (10.3). Show correct, partial and wrong in the README's tables and on the Results page.
   *Exit:* both show all three for every judged run; `web/e2e.py` checks the columns.
   **Done 2026-10-08:** `bench/README.md` gives the rule; the README's table and the Results page
   show correct, partial and wrong (the demo on test v3: 0.76, 0.20, 0.03), with the rule under
   the page's table; `web/e2e.py` checks the three columns and the rule (passes, axe clean). The
   page waits for the next deploy.
5. **Decide the temperature.** ADR 0011 sends no temperature and no seed, so the answer model and
   the judge sample at the provider's default. Measure on dev with `--repeat` at the default and
   at a lower setting, the judge first, after reading Google's guidance on temperature for
   Gemini 3 models; amend ADR 0011 with the choice and the noise measured at each (10.2).
   *Exit:* ADR 0011 amended; every run records the temperature it used.
   **Done 2026-10-08:** read both guides (Google: keep Gemini 3 at 1.0; the Gemma 4 card: 1.0
   for all uses), then measured the judge on the demo's cached dev answers: at temperature 0 its
   three samples agree on all 67 answers, against 8 of 67 at the default, with 49 of 68 correct
   at both and every known-answer case as expected at both. The judge now sends temperature 0
   (`gates.JUDGE_PARAMS`, `JUDGE_PARAMS` to override; other parameters need their own check);
   the answer model keeps the provider's 1.0, not measured lower (Google advises against it).
   Runs record `llm_params` and `judge.params`. [ADR 0011](decisions/0011-answer-llm.md),
   amended. The dev runs at the default are in `results/dev/archive/`.
6. **Every run names its corpus.** No run records the corpus it ran on, and the two fingerprints
   differ: `Corpus.fingerprint` (in memory) leaves the heading out, `db.fingerprint` (Postgres)
   puts it in. The ranking cache is keyed on them, so a heading changed in the demo's corpus
   reuses rankings made before. One fingerprint, heading included, for both stores and the index
   (9.5); each run records it with its count of versions per diploma, and `check-results` holds
   the leaderboard to one corpus as it does to one split. *Exit:* both stores and the index agree
   on the same versions (tested); a changed heading misses the ranking cache (tested).
   **Done 2026-10-08:** `lex.domain.corpus_fingerprint` over each version's identity, dates and
   `text_sha` (heading and text); the corpus in memory and the index agree on today's corpus and
   in a test, Postgres in a test that needs the store; every retrieval and answers run records
   `corpus` (fingerprint, versions per diploma), and `check-results` refuses test runs on two
   corpora, or on one that is not the index's.
7. **A test run names the dev run behind it.** Nothing ties a test run to a dev run, and test v3's
   answer runs record no prompt fingerprint. A test run looks up the system's dev run and refuses
   unless its prompts, configuration and dev version are the current code's; it records that
   run's file, commit and fingerprint. *Exit:* a test run without a matching dev run is refused
   (tested); every new test run names its dev run.
   **Done 2026-10-08:** retrieval and answers test runs look up the system's dev run and refuse
   without one on today's dev made with the same configuration (for answers, the model, its
   parameters, k, the format and the prompts' fingerprint); the run records `justified_by`
   (tested).
8. **check-results checks every run.** It accepts 12 dev runs with no `bench` key (from before
   splits were versioned) and 4 on dev v2, and five were written with uncommitted changes, the
   demo's own among them. A dev run comes before the commit that reports it, so uncommitted
   changes are normal; what must hold is that the run is committed with the code that made it.
   Each run records a hash of the source, and `check-results` compares it with the source at the
   commit that last changed the run's file (CI fetches the history). Runs from before versioning,
   or on an earlier dev, move to `results/dev/archive/`, kept and not reported. *Exit:*
   `check-results` fails on a run with no `bench` or with code other than its commit's (tested);
   the demo's dev run passes.
   **Done 2026-10-08:** runs record `source`, a hash of `src/lex` and `pyproject.toml`;
   `check-results` refuses a run with no split version, a dev run on another dev, a run from
   today on that records no source, and one whose source is not the commit's that last changed
   its file (the working tree's while uncommitted; skipped where the history lacks the run's
   commit, as in the public mirror); CI fetches the whole history (tested on a scratch
   repository). 15 runs from before versioning or on v2's dev moved to `results/dev/archive/`.
9. **The whole cost of a question.** `cost()` counts the answer model's tokens alone: the
   question's embedding (a call per question on the demo) and the judge are left out, and so is
   the README's bound of $0.4232 a day. Count the embedder's and the judge's usage, price each
   where Google publishes a price, and say "not priced" where it does not. *Exit:* runs record
   their cost by part; the README's bound includes the embedding.
   **Done 2026-10-08 in code:** answers runs record `costs`: the answers', the embeddings' (the
   texts the run embedded, tokens counted by Google's countTokens, since the OpenAI-compatible
   endpoint reports none for embeddings, at $0.20 per million) and the judge's tokens, not
   priced (Gemma 4 has no paid tier), with `usd_per_question` for answer and embedding together
   (tested). The README's bound follows the milestone's run: $0.00103781 a question on test v4
   ($0.001033 the answer, $0.00000481 the embedding), $0.415124 a day at 400.
10. **A lockfile, and the environment in each run.** Direct dependencies are pinned and theirs are
    not; CI tests Python 3.14 while the demo runs whatever Python Vercel picks. Lock every
    dependency (the tool chosen in a short ADR), install CI from the lock, export
    `vercel/requirements.txt` from it, pin one Python for CI, the venv and Vercel, and record
    Python's version and the lock's hash in each run. *Exit:* CI installs from the lock and fails
    when `vercel/requirements.txt` drifts from it; runs record both.
    **Done 2026-10-08:** [ADR 0019](decisions/0019-lockfile.md): uv locks 107 packages in
    `uv.lock`; `.python-version` says 3.14 for CI, the venv and Vercel (which ran 3.12 until
    now); CI installs from `uv export --locked` and fails when `vercel/requirements.txt` is not
    the lock's export; runs record `environment` (Python, lock hash).

**Exit (milestone):** under ADR 0016's terms (9.2), and on benchmark v4 if ADR 0009 chose the
re-split (9.3), every system on the leaderboard runs on test once, fresh, judged with several
samples, each run naming its dev run, corpus, environment and cost by part, and keeping its
verdicts by item; `check-results` recomputes every number the README and the leaderboard show.

**Milestone met 2026-10-09.** ADR 0016 as amended that day (Tiago accepts the free tier for test
runs; every run records each endpoint's tier). `python -m lex.bench resplit` made benchmark v4:
13 test items joined their groups in dev (dev 105, test 96), and a test item in a group with
dev items is now a fault. On v4's dev the judge, at temperature 0, accepted 81 of 81 reference
answers, caught 57 of 57 altered ones and judged none of 132 lenient cases correct (129 as
expected); each leaderboard system ran on dev, then once on test from a clean tree: the four
retrievers (recall@1 0.52, 0.56, 0.75, 0.81) and the three answer systems, answered from no
cache and judged three times (samples agreed on every answer): the demo's agent 0.70 correct,
per sentence 0.71, the reference system 0.75; item by item none differs beyond the noise
(p = 1.00 and 0.42). Each run names its dev run, corpus, environment, endpoints and costs, and
keeps its verdicts; `check-results` recomputes them, and the README's tables are generated from
them (12.1). The code is 0.4.0 (ADR 0021). v3's runs are in `results/test/v3/` and
`results/dev/archive/v3/`.

## Phase 11: The corpus and the demo (done; deployed 2026-10-09)

The corpus parses more than it keeps, the demo can cache what it should not, and several paths
have no test. The items are independent. One that changes answers (1, 5, 7) comes with a dev run,
and the phase ends with a test run only if `compare` (10.2) finds that dev moved beyond the noise.

1. **Keep effects, suspensions and rulings with the versions.** `dr.py` parses what other
   diplomas say about an article's effects (deferred, suspended, starting with other legislation)
   and the Constitutional Court's rulings; `build.py` copies them into `report.json`, and nothing
   reads them. Attach each to the versions it concerns, as notes on `ArticleVersion` in both
   stores and the index, put them in the model's prompt and on the article's page, and amend ADRs
   0002 and 0005 (which keeps ruled-on articles out of temporal items). *Exit:* article 368.º
   carries Acórdão n.º 602/2013 on the page and in the prompt; a dev run measures the prompt's
   change.
   **Done 2026-10-08:** `ArticleVersion.notes` holds each of the DR's notes on effects with the
   version it concerns (17 versions, the store's column and the index's hash included); the
   model reads them as `<nota>` inside the article, the page shows them above the text (the e2e
   checks art. 368.º in 2013), the MCP server returns them; ADRs 0002 and 0005 amended. The dev
   run that measures it follows, with the parser's change (11.5).
2. **Spot-check the hand-dated versions, and log disagreements.** `spot_check.run` draws versions
   uniformly, so it rarely draws one dated by rule (a correction, a date read from the diploma, a
   rectification's, the unanimous date), the riskiest kind. And when a date read by hand
   (`read_from_diploma`) and the DR's note both exist, `_start_of` takes the note and says
   nothing. Spot-check every rule-dated version, plus a random sample of the rest; make a
   disagreement between a hand date and a note a build problem until a correction explains it.
   *Exit:* the spot-check reports list every rule-dated version; the build report has no
   unexplained disagreement.
   **Done 2026-10-08:** the spot check checks every rule-dated version (18 in the Código do
   Trabalho, 1 in the Código Civil, 17 in the NRAU) besides its random draw; `_start_of` makes a
   hand date the DR's note contradicts a build problem (none today: the offline rebuild left the
   corpus as it was). Of 65 labour checks, 56 agree; 8 are versions made by Retificações n.º
   13/2023 and 28/2017, which the store applies from the rectified text's date (Lei n.º 74/98,
   art. 5.º, n.º 4) while the DR's history shows them once published, listed apart; 1 is new and
   open: art. 127.º as Lei n.º 120/2015 left it numbers its last paragraphs one way on the PGDL
   and another on the DR. Tenancy: the two dates codes.py corrects on the DR's are labelled so,
   and NRAU 35's known difference remains.
3. **The store in memory keeps the store's rules.** The demo's only store is `Corpus`, which
   enforces none of Postgres's constraints: no two versions of an article in force on one day,
   `valid_to` after `valid_from`. Add `Corpus.check()`, called by `Corpus.load` and by
   `vercel/assemble.py`. *Exit:* an overlapping corpus fails to load (tested); a deploy assembles
   only a checked corpus.
   **Done 2026-10-08:** `Corpus.check()` refuses a version that ends before it starts and two
   versions of an article in force on one day; `Corpus.load` (the demo's start) and
   `vercel/assemble.py` call it (tested; today's corpus passes).
4. **The weekly check, on the DR too and for any act.** `check-updates` reads only the PGDL, and
   its pattern knows laws, decree-laws, portarias and rectifications: an amendment of another
   kind, such as a Constitutional Court ruling with general binding force or a regional decree,
   goes unseen. Count the rows the page lists against those parsed and fail on any it cannot read;
   compare with the DR's own list of changes, the reference (ADR 0005), rendered as the build
   renders it. *Exit:* a fixture with an act of an unknown kind fails the check (tested); the DR
   is checked weekly, or ADR 0005 says why it cannot be.
   **Done 2026-10-08:** the check reads every act the PGDL lists and fails on one of a kind it
   cannot read (tested); reading them found two numberless declarations on the Código Civil's
   page (1980, 1986) the check had never seen, now in its known list. `check-updates --dr`
   renders the DR's page too and compares its own list of amending acts (28, 101 and 13, with
   the rulings and the regional decree the PGDL omits) with the one the corpus was built from;
   the weekly workflow runs both. Run today: no new amendment on either source.
5. **Read citations that name the approving law.** The reference parser takes "artigo 238.º da
   Lei n.º 7/2009" and "artigo 1069.º do DL n.º 47344/66" for other diplomas and drops them, so a
   model citing that way turns its answer into a refusal. Read them as the Código do Trabalho and
   the Código Civil, except where the number can be one of the approving law's own articles
   (Lei n.º 7/2009 has its own, on transition and revocation, before the Code it approves).
   *Exit:* `tests/fixtures/references.tsv` holds both forms and the exception; a dev run reports
   `dropped_citations` before and after.
   **Done 2026-10-08:** `references.py` reads Lei n.º 7/2009 as the Código do Trabalho but for
   its own articles 1.º to 14.º, and DL n.º 47344/66 as the Código Civil; four fixture lines hold
   both forms and the exception. The demo's dev run (commit e08cd35, with item 1's notes) reports
   0 dropped citations, as the run before it did: on dev, no model cited that way.
6. **Over budget is a failure, not an answer.** When the agent's 9 s budget runs out,
   `AgentSystem` returns a refusal ("demoraria demasiado"), which `/api/answer` caches and counts
   as answered. Raise instead: the endpoint answers 503, gives the admission back and caches
   nothing. *Exit:* a scripted slow model gets a 503 and its admission back, and a retry is
   answered afresh (tested).
   **Done 2026-10-08:** `AgentSystem` raises `BudgetTimeout`; `/api/answer` answers 503 with its
   "took too long" message, refunds the admission and keeps nothing, counted `failed_timeout`
   (tested). Waits for the next deploy.
7. **A refusal's reason is a claim too.** `refusal(as_of, reason)` appends the model's `motivo`
   to a refusal: free text with no citation, shown to the visitor and cached, against "no
   citation, no claim". Show the fixed refusal sentence alone, and keep the reason in the run.
   *Exit:* no refusal carries model text (tested); dev runs keep each refusal's reason.
   **Done 2026-10-08:** a refusal shows the fixed sentence only; the model's reason lives in
   `Answer.reason`, which the API empties before it caches or answers (tested) and runs keep as
   `refusal_reason`.
8. **Examples that stay warm, and a live check.** Three of the page's four examples
   (`web/src/examples.json`) have no date: they are answered at deploy for that day and miss the
   cache from the next midnight in Lisbon. The probe asks only the dated one, so it sees neither
   that nor a revoked key. Give every example a fixed `asOf`; the probe checks that each is served
   from the cache, and a daily `--live` run spends one answer on a question that is not. *Exit:*
   the probe fails when an example is not cached (tested); the daily live check is green on the
   demo, and red with a revoked key (scripted).
   **Done 2026-10-08 in code:** every example has a date (`web/src/examples.json`), and the
   assembly answers each for its own; the probe asks every example and fails on one not cached;
   `--live` asks a question about the day, from no cache, and fails on anything but an answer
   (tested on a 503, as a revoked key gives); the workflow adds it to the run of 06:41 UTC. Green
   on the demo once it is deployed. **Deployed 2026-10-09:** the first deploy found the examples
   uncached (`assemble.py --warm` failed writing dates; fixed, tested); after it, the probe passes
   with all four examples from the cache and `--live` answers in 4.15 s.
9. **The demo says what it runs, and the probe keeps what it measures.** `/api/health` gives the
   system's name and the day, not the commit or the corpus; the probe prints its timings and keeps
   none; the cold start on Vercel is still "not measured yet". `vercel/assemble.py` writes the
   commit, whether the tree was clean, the corpus fingerprint and the date into the deployment,
   and `/api/health` returns them with the instance's start time. The probe keeps each run's
   timings (a workflow artifact, gathered into `results/`), and a request that met a new instance
   counts as a cold start. *Exit:* `/api/health` names the commit and the corpus; the README's
   cold start is measured, from those runs.
   **Done 2026-10-08 in code:** `vercel/assemble.py` writes `data/build.json` (commit, clean
   tree, corpus fingerprint and versions, time); `/api/health` returns it with the instance's
   `started_at`; `--record` appends each run's timings and whether it met a cold start, which
   the workflow keeps as an artifact for 90 days (tested). The measured cold start follows the
   deploy and a week of runs.
10. **Test the untested paths.** No test exercises the `Fetcher` (its cache, offline mode,
    interval and backoff), `ApiEmbedder`'s rate-limit loop, the `Gate`'s change of day, or the
    integrity gates of `src/lex/eval/__main__.py` (756 lines; none of its seven `SystemExit`s,
    four of them in `measured_judge`, is tested). Split that module into wiring and commands so
    its gates can be tested without the CLI, and test each path with injected clocks and
    clients. *Exit:* a test for each path; Phase 10's new gates came with theirs.
    **Done 2026-10-08:** `tests/test_untested_paths.py` covers the fetcher, the embedder's
    waits, the gate's change of day and the eval's gates; the gates moved to
    `src/lex/eval/gates.py` (the CLI keeps the wiring the import rules give it, 852 lines).
11. **The page, by keyboard and in CI.** On a change of route, focus stays where it was;
    `web/e2e.py` clicks but never tabs; the e2e, axe and the contrast check run only by hand. Move
    focus to the new view's heading on every change of route, back included, add a keyboard-only
    pass to the e2e, and run the e2e (scripted answers, no quota), axe and `web/contrast.py` in
    CI's web job. *Exit:* CI runs all three; a colour below its bar fails CI.
    **Done 2026-10-08:** on every route change, back included, focus moves to the visible view's
    heading; `web/e2e.py` adds a keyboard-only pass (tab to a view, open it, focus on its heading;
    back; tab to the question and ask) and runs under the CSP; CI's web job builds the page and
    runs the e2e and `web/contrast.py` (which exits 1 under a bar) on `corpus/versions.jsonl.gz`,
    the corpus's text now committed beside its index by `lex.bench index` (235 KB, checked
    against the index in CI). Passes locally with `data/` moved aside.
12. **Small fixes,** each its own commit:
    - security headers on the page and the API (a content security policy, `nosniff`, a referrer
      policy, no framing), set in `vercel.json`;
    - `visitor()` trusts `x-real-ip` wherever the API runs: trust it only behind Vercel (a
      setting), and the connection's address elsewhere;
    - errors reach the English page in Portuguese: the API returns a code with each, and the page
      words it (`i18n.ts`);
    - the gate's day is Lisbon's, the free quota's is the Pacific's (it renews at 08:00 in
      Lisbon): count the gate's day as the quota does, keep Lisbon's "today" for `as_of`, and
      compute the hour the limit message gives;
    - the `mcp` extra needs FastAPI, because `mcp_server.py` imports `DISCLAIMER` and
      `lisbon_today` from `lex.api.app`: move them to `lex.domain`, and test the MCP server with
      its extra alone;
    - `space/` no longer starts, and ADR 0013 is superseded: remove the folder and its mentions.

    *Exit:* each done, with a test where it has behaviour.
    **Done 2026-10-08:** `SECURITY_HEADERS` (a strict CSP, `nosniff`, a referrer policy, no
    framing) on every API response and, through `vercel/assemble.py`, in `vercel.json` for the
    CDN's files; `web/e2e.py` passes with the CSP in force. `visitor()` trusts the proxy's headers
    only where Vercel sets `VERCEL=1`. Errors carry a code (`X-Lex-Error`) that the page words in
    its own language. The gate counts the quota's Pacific day and says when it renews in Lisbon
    (08:00, or 07:00 in the week the clocks disagree). The MCP server imports no FastAPI (tested
    with FastAPI blocked). `space/` is gone. All tested; the page and headers wait for a deploy.

**Exit, 2026-10-08:** every item done. The answer changes (1, 5, 7) were measured in one dev run
of the demo's system (commit e08cd35): 49 of 68 judged correct against 50, one item changed
(`ar-0002`), sign test p = 1.00. Dev did not move beyond the noise, so the phase makes no test
run; its changes reach test with Phase 10's milestone. What waits: a deploy, which publishes the
security headers, the error codes, the build in `/api/health`, and lets the probe's live check
and cold start be measured (items 8, 9, 12).

## Phase 12: Documentation, community and publication

What the project says about itself should come from what it measured, carry a version, and say
how others can take part. The phase ends with a technical report.

1. **One benchmark version in the README.** The README mixed dev v2 and v3 (9.1 corrected the
   lines found). Generate its tables, and the dataset card's numbers, from `results/` between
   markers (`python -m lex.eval report --write`), and fail CI when they are out of date. *Exit:*
   every number in those tables comes from a run of the current benchmark version, checked in CI.
   **Done 2026-10-08:** `lex.eval.report` writes the README's two results tables, and the
   sentence above them with the benchmark version and its counts, from each system's latest run
   in `results/test/` (`python -m lex.eval report --write`); `check-results`, which CI runs, fails
   when the block differs. Generated, the tables came out as they had been typed, number for
   number. The card's counts are generated by `python -m lex.bench card` (12.6) and checked by
   `validate`. The prose around the tables is still written by hand.
2. **"Unlocks" with their version.** The Unlocks lines of Phases 2 to 5 quote v0's test numbers,
   and none has a successor. Label each with its benchmark version, and write a current one from
   Phase 10's milestone. *Exit:* every Unlocks names its version, and one quotes the current
   benchmark.
   **Done 2026-10-08:** the phases' lines say they quote v0, and a current line at the top quotes
   v3's test runs; the milestone replaces it with v4's.
3. **ADRs that say what is true, and the budgets in one.** By a reading on 2026-10-07, six ADRs
   were overtaken without an amendment: 0003 (the Código do Trabalho alone; ADR 0017 added
   tenancy), 0005 (the consolidated text from the PGDL; the current text now comes from the DR),
   0006 (the store; the demo runs without it, ADR 0014), 0007 (BGE-M3, to be revisited at 50
   answerable dev items; dev has 68), 0010 (the reranker in the demo, which has none) and 0011
   (its status line, "no LLM judge yet", the answer's format). Amend each with what overtook it;
   add an "Open" section to this roadmap for what waits on no phase (the legal review, Phase 7's
   options); and write ADR 0020 with the budgets that live in code: 20 answers per visitor an hour
   and 400 a day (`Limits` defaults to 500, `lex.api.__main__` to 400: one value), the agent's
   9 s, the model's 18 s and the embedder's 8 s timeouts, Vercel's 30 s, the probe's 20 s and
   5 s bars, the judge's 90% bar and the regression rule (10.2). *Exit:* each ADR amended or
   confirmed; ADR 0020 names each budget, its constant and why.
   **Done 2026-10-08:** ADRs 0003, 0005, 0006, 0007, 0010 and 0011 amended with what overtook
   them; an "Open" section above the decisions table; [ADR 0020](decisions/0020-budgets.md) lists
   17 budgets with their constants and reasons. `Limits.per_day` follows it to 400 with the next
   code change.
4. **Versions outside prose.** Benchmark versions exist only in prose: no git tags, no
   `CITATION.cff`, `pyproject.toml` at 0.0.1, the card's counts typed by hand. Tag each benchmark
   version on the mirror's snapshot commit (`bench-v3`, then `bench-v4`) and on the Hugging Face
   dataset's revision, give the code a version that moves with its releases, add `CITATION.cff`,
   and generate the card's counts (12.1). *Exit:* the tags exist on the mirror and the dataset;
   `CITATION.cff` validates; the counts are generated.
   **Done 2026-10-08, but the tags:** [ADR 0021](decisions/0021-versions.md) sets the scheme:
   the benchmark moves to `vN` when a split's `scored` hash changes, and the code is `0.N.P`, N
   the benchmark its published numbers are on. The code is 0.3.0 (`pyproject.toml` and
   `CITATION.cff`, which cffconvert validates against schema 1.2.0; a test holds the two equal
   and N to the leaderboard's benchmark). The counts are generated (12.1, 12.6). `bench-v3` and
   `v0.3.0` are made with the next snapshot pushed to the mirror and the dataset, which waits on
   publishing.
5. **A way in for contributors and other systems.** There is no CONTRIBUTING.md and no issue
   template, and the dataset card says to open an issue to have a system scored on test, with
   nothing saying how. Write CONTRIBUTING.md (proposing items under the writing rules, reporting
   an error in one, the checks to run), issue templates (an item's error; a system to score), and
   in the harness `answers --from answers.jsonl` (answers by item id, with citations and their
   versions, scored and judged as any system) and an `HttpSystem` that calls an endpoint with
   `/api/answer`'s contract. On test, an `HttpSystem` sends test questions to whoever runs the
   endpoint, so ADR 0016's table (9.2) says on what terms. *Exit:* a system scored on dev from a
   file, by the documented steps; an HTTP system scored in a test; the guide and the templates on
   the mirror.
   **Done 2026-10-08, but publishing the mirror:** CONTRIBUTING.md and two issue templates;
   `lex.eval.outside` scores a file (`answers --from`) or an endpoint (`answers --http`) as any
   system, versions included (`Answer.cited_versions`), judged if asked; an endpoint on test
   needs `--operator-agrees`. The demo's dev answers written to a file and scored by the
   documented steps give back its numbers (citation recall 0.86, precision 0.90); tested.
6. **A dataset card that says what can be measured.** The card does not say that 63 of the 92 dev
   items come from the ACT's portal, nor that 34 of the 56 drawn from its FAQ keep the ACT's
   question word for word (measured 2026-10-07 against `act_faq.jsonl`): models may have read
   those questions and the ACT's answers, which calls for a contamination note. It has no
   sections on intended and out-of-scope uses, personal data, biases and limits (one source
   dominates; one model drafted and reviewed every item), or contact. ADR 0008 has each FAQ item
   record its entry's last-modified date; 2 of the 56 do, in their notes. Add `source.modified`
   to the schema, filled from `act_faq.jsonl` and required for FAQ items by `validate` (metadata,
   so 9.6's hash ignores it), and compute the card's numbers by script. *Exit:* the card has the
   sections and the computed numbers; every FAQ item carries its modified date.
   **Done 2026-10-08:** the card has sections on uses, contamination, personal data, biases and
   limits, maintenance and contact, and its block now computes 63 of 92 dev items from the ACT's
   portal and 34 of the 56 from its FAQ in its words (that line left out of CI's comparison,
   which has no FAQ); `source.modified` is in the schema, `python -m lex.bench stamp` wrote it
   into 126 items (56 dev, 70 test) from `act_faq.jsonl`, and `validate` requires it of any FAQ
   item. The leaderboard's runs stayed current: nothing a run reads changed (9.6).
7. **Hygiene.** Dependabot for pip, npm and the actions (an update that can change a number still
   comes with a dev run); `SECURITY.md`; actions pinned by commit SHA; and `amendments.yml`
   limited to the private repository, as `probe.yml` is, so the mirror does not run it too.
   *Exit:* all four in place; the mirror runs no amendment check.
   **Done 2026-10-08:** `.github/dependabot.yml` (uv, npm, actions; weekly, grouped), `SECURITY.md`
   (private reports through GitHub, which the repository's settings must enable), every action
   pinned by commit with its version beside it, and `amendments.yml` limited to `timimata/lex-pt`.
   **2026-10-10:** the first published snapshot carried `dependabot.yml`, and Dependabot opened
   six pull requests on the mirror; the snapshot now leaves it out (tested), and they were closed.
8. **A technical report, with related work.** Nothing in the repository cites another benchmark.
   Write the related work first: LegalBench and LexGLUE; BSARD and LLeQA, the closest designs
   (citizens' questions answered with statutory articles); COLIEE's statute law retrieval;
   Magesh et al. (2024), who measured how often commercial legal research tools are wrong;
   temporal question answering (SituatedQA); and a survey of legal datasets in Portuguese,
   European and Brazilian. Then the report: the corpus and its dates, the items and splits, the
   judge and how it was measured, results with paired tests, and the limits (contamination,
   model-drafted items, the legal review's state). *Exit:* a draft in `docs/` whose every number
   links to its file in `results/`.
   **Related work done 2026-10-08** ([docs/report.md](report.md)), each work checked at its source:
   LexGLUE, LegalBench, LegalBench.PT (Portuguese law, exam questions turned into closed formats,
   2025: the closest in jurisdiction), BSARD and LLeQA (the closest in design), COLIEE,
   SituatedQA, Magesh et al. The report's other sections follow the milestone.
   **Done 2026-10-09:** the report's other sections, from the milestone's runs: the corpus and
   its dating, the items and splits, the metrics and the judge, the systems, results on test
   v4 with the paired comparisons and the noise, and the limits; each number links to its run in
   `results/`, or to the index, the checks or the card it comes from.

**Exit:** the mirror and the dataset published as a tagged version, with the README and the card
generated from `results/`; the report drafted.

## Open

What waits on no phase, or on someone other than the code:

- **The legal review** (Phase 6): a law student or lecturer of the Faculdade de Direito,
  Universidade Lusófona, signing items off with `python -m lex.bench review`. 0 of 201 validated.
- ~~Where the judge runs on test, and a billed key~~: decided 2026-10-09, Tiago accepts the
  free tier for test runs; the judge stays Gemma 4 on Google's API, at temperature 0 (ADR 0016,
  amended 2026-10-09).
- **Phase 7's options:** fine-tuned embeddings, tracing, a local answer model on a Raspberry Pi
  (its speed not measured), and a hand-scored comparison with Lia and TogaAI on a small dev subset.
- **Art. 127.º, 2015 to 2017:** the spot check of 2026-10-08 found its paragraphs 5 to 7
  numbered one way by the PGDL and another by the DR; a person reads Lei n.º 120/2015 to say
  which holds, and a correction follows (ADR 0005: the DR wins).
- **More law:** the Código do IRS waits ([ADR 0017](decisions/0017-tenancy.md)).

## Open decisions

Each becomes an ADR when its phase starts.

| Decision | Phase |
|---|---|
| ~~Store and BM25 implementation~~ (ADR 0006) | 1 |
| ~~Embedding model~~ (ADR 0007) | 2 |
| ~~LLM for answers~~ (ADR 0011); ~~LLM for judging~~ (ADR 0015) | 3, 5 |
| ~~Reranker~~ (ADR 0010) | 3 |
| ~~Demo hosting~~ (ADRs 0013, 0014) | 4 |
| ~~Code and dataset licences; whether test stays hidden~~ (ADR 0016) | before the repo goes public |
| ~~What leaves the machine: a paid key or a local judge for test runs~~ (ADR 0016, amended 2026-10-09: the free tier) | 9 |
| Pairs across splits: re-split as benchmark v4, or keep and report (ADR 0009, amended) | 9 |
| Temperature for answers and the judge (ADR 0011, amended) | 10 |
| ~~The lockfile's tool~~ (ADR 0019) | 10 |
| Effects, suspensions and rulings as notes on versions (ADRs 0002 and 0005, amended) | 11 |
| ~~The demo's budgets in one place~~ (ADR 0020) | 12 |
