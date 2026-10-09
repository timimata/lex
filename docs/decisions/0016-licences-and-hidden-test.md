# 0016. Licences, and a test split that stays private

Date: 2026-10-01
Status: accepted; amended 2026-10-08 (what leaves the machine; a paid key for test runs) and 2026-10-09 (the free tier accepted for test runs)

## Context

Phase 6 makes the code public and the benchmark a dataset. Three things set the terms:

- The corpus is official text, and it is not committed: `data/` is rebuilt from the sources by
  script (ADR 0005). What is published is code, the benchmark and results.
- Most benchmark questions are drawn from the ACT's FAQ and guidance (ADR 0008). Public bodies'
  documents may be reused under Lei n.º 26/2016 with their source named, and every item names its
  page and the date it was read.
- A benchmark whose test answers are public ends up in training data and gets tuned against, and
  its scores stop meaning what they say.

The private repository's history holds the test split, and also test items in older files: dev
items that ADR 0009's regrouping moved to test, the draft batches before they were cut to ids,
and, until 2026-10-01, two ADRs and a parser fixture, which were cleaned that day.

## Decision

- Code, everything outside `bench/`: the MIT licence (`LICENSE`).
- The benchmark, `bench/`: CC BY 4.0 (`bench/LICENSE.md`), attributed to Lex and, item by item,
  to its source.
- The test split stays private. The public repository is a mirror of the current tree without
  `bench/data/test.jsonl`, published as snapshots, without the private history.
  `python -m lex.bench snapshot DIR` writes a snapshot and refuses it if any file holds a test
  item's question or answer, or a string shaped like an API key.
- Test results stay public: their summaries (`results/test/`) carry no items, and the README and
  the leaderboard report them. Another system can be scored on test by asking; the private
  repository runs it and publishes the numbers.
- The Hugging Face dataset holds dev only, with its card and the licence:
  https://huggingface.co/datasets/timimata/lex.

## Consequences

- Readers of the public repository get the code, dev, the datasheet, every decision and every
  number, but not the test items or the development history.
- Each public release is a snapshot commit that names the private commit it was made from. The
  mirror is https://github.com/timimata/lex, first published on 2026-10-01 from commit df50041;
  its commits use the account's GitHub no-reply address.
- Scoring someone else's system on test goes through the maintainer, as with other benchmarks
  that keep their test set hidden.

## Amendment, 2026-10-08: what leaves the machine

ADR 0011 says the reference answers are never sent. Since ADR 0015 they are: the judge's prompt
(`lex.eval.judge.prompt`) holds each item's question, date and reference answer with the system's
answer, and goes to Gemma on Google's Gemini API. Every test run judged so far (2026-10-01 to
2026-10-07) sent test items that way, on the free tier. Google's terms for the Gemini API, read
on 2026-10-08 (last modified 2026-04-28): on unpaid services Google "uses the content you submit
to the Services and any generated responses to provide, improve, and develop Google products and
services", and human reviewers may read it; on paid services it "doesn't use your prompts [...]
or responses to improve our products", and logs them "for a limited period of time, solely for
detecting and preventing violations of the Prohibited Use Policy" and legal disclosures.

What each part of Lex sends, and where:

| What runs | What it sends | To |
|---|---|---|
| `eval answers` (dev, test) | the question, its date, the retrieved article versions | the answer model, Gemini 3.1 Flash-Lite, on Google's API |
| `--judge`, `judge`, `judge-check` | the question, its date, the reference answer, the system's answer | the judge, Gemma 4 26B A4B, on Google's API |
| a `dense-gemini` retriever | the question (and, once, every article version) | Gemini Embedding 2, on Google's API |
| `+decomp` (dropped, ADR 0014) | the question | the answer model |
| `eval latency URL` | dev questions | the deployed demo, and through it Google |
| the demo | a visitor's question, its date, the retrieved articles | Google's API, on the free tier |
| `bench snapshot`, then a push; `hf upload` | every tracked file but test and Dependabot's settings; the card, dev, the licence | GitHub and Hugging Face, publicly |
| BM25, BGE-M3, the reranker, a model on llama.cpp | nothing | this machine |

### Decision

- Test runs that call a model outside this machine do so with a paid key (Tiago, 2026-10-08).
  `LLM_KEY_TIER=paid` in `.env` says the key's project is billed; every run records, for each
  model it calls, the endpoint and that tier (`lex.generation.llm.endpoint`), and a test run
  refuses to start if one of them would go to a free tier (`lex.eval.results.ensure_private`).
  A model on this machine needs no key and passes.
- Dev runs may use either tier: dev is public already.
- Test results keep each item's scores by id (refused, citation precision and recall, the
  judge's verdict) and nothing an item says or cites, nor the judge's reason, which may quote
  the reference answer: enough for `check-results` to recompute every reported number, nothing
  that tells a test question or its answer. The demo's copy of `results/test/` drops them.
- The demo stays on the free tier (ADR 0014): a visitor's question reaches Google on those terms.
  The page says so under the question field, and asks for no personal data.
- What the free tier received before this amendment cannot be called back. The dataset card's
  contamination note (ROADMAP, Phase 12) says that test questions and their reference answers
  were sent to Google's free tier during the runs of 2026-10-01 to 2026-10-07.
- A system scored on test through an endpoint of its own (`HttpSystem`, Phase 12) receives the
  test questions: it is run only for an operator who agrees, in the issue asking for it, not to
  keep or train on what it receives, and the run records who.

- Google serves Gemma 4, the judge (ADR 0015), on the free tier only: its pricing page, read
  on 2026-10-08, lists its paid tier as "Not available". A paid key therefore leaves the judge's
  requests, reference answers included, on unpaid terms, and `lex.generation.llm.endpoint`
  says so whatever the key; a judged test run is refused until the judge runs elsewhere. The
  way open without changing the judge's model is to serve the same weights on this machine
  (`JUDGE_BASE_URL`, `JUDGE_MODEL`), measured on dev again under its new id; or the judge
  becomes a model with a paid tier, measured again too. Tiago's choice, pending on 2026-10-08.

### Consequences

- A test run costs money: the agent's answers on test v3 cost $0.115361 at paid prices
  (`results/test/2026-10-07T1749-…+agent.json`), before the judge and the embeddings, which runs
  do not price yet (ROADMAP, Phase 10).
- Until the key's project is billed and `.env` says so, no test run starts.

## Amendment, 2026-10-09: the free tier accepted for test runs

Gemma 4, the judge, has no paid tier on Google's API, so the rule of 2026-10-08 left a judged
test run waiting for a local judge or a new one, measured again. Tiago weighed it on 2026-10-09
and accepts that a provider may train on what test runs send it.

- Test runs may call models on a free tier (`lex.eval.results.FREE_TIER_ON_TEST`). The judge
  stays Gemma 4 26B A4B on Google's API, at temperature 0, as measured on dev (ADR 0011,
  amended); the answer model may run on the free key.
- Every run still records each model's endpoint and tier, so a reader knows which test
  questions and reference answers reached which provider, on which terms. The dataset card's
  contamination note says it.
- What this costs the benchmark: test questions and their reference answers may enter a
  provider's training data, and a model trained on them could score higher on test than its
  ability warrants. The test split stays out of the public mirror and the dataset (above), so it
  is not published; it is no longer kept from the providers the runs call.
- `FREE_TIER_ON_TEST = False` restores the rule of 2026-10-08 for the runs that follow; it cannot
  call back what was sent.
