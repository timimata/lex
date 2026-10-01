# Roadmap

A phase ends when its exit criteria are met. From Phase 2 on, every phase leaves the project in a
state worth showing, so stopping early still leaves something real.

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

**Unlocks:** "Built a 100-question benchmark for Portuguese labour law, with temporal questions
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

**Unlocks:** "Built a retrieval-augmented system for Portuguese labour law that answers with
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

**Unlocks:** "Deployed a public demo that answers questions on Portuguese labour law with a
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

**Unlocks:** "Measured answer correctness with an LLM judge checked on known-answer cases (40 of
40 right answers accepted, 28 of 28 altered ones caught): 82% of the demo's answers on the
held-out test set judged correct."

## Phase 6: Wider corpus, benchmark v1, publication (current)

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
- Add tenancy (Código Civil and NRAU) and the Código do IRS.
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

## Phase 7: Optional

Chosen by what the numbers and job ads say:
- fine-tuned embeddings (was Phase 5): Gemini Embedding 2 already finds the right article in the
  top 5 for 0.95 of dev questions, and 40 dev items cannot tell a small gain from noise, so it
  waits for benchmark v1; it also needs a GPU this machine cannot give PyTorch;
- an agent (LangGraph) for `composite` questions: decomposition and cross-references did not
  help them on dev (Phase 4), so an agent is next, kept only if it beats them on that subset;
- tracing (Langfuse), model routing, cost per question;
- a local model for the answers on a Raspberry Pi (ADR 0012 has the quality; speed not measured);
- a hand-scored comparison with Lia and TogaAI on a small dev subset, after checking their terms.

## Open decisions

Each becomes an ADR when its phase starts.

| Decision | Phase |
|---|---|
| Store and BM25 implementation | 1 |
| Embedding model | 2 |
| ~~LLM for answers~~ (ADR 0011); ~~LLM for judging~~ (ADR 0015) | 3, 5 |
| ~~Reranker~~ (ADR 0010) | 3 |
| ~~Demo hosting~~ (ADRs 0013, 0014) | 4 |
| ~~Code and dataset licences; whether test stays hidden~~ (ADR 0016) | before the repo goes public |
