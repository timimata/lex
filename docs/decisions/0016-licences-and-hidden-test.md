# 0016. Licences, and a test split that stays private

Date: 2026-10-01
Status: accepted

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
- A Hugging Face dataset, when made, holds dev only, with the datasheet and the licence.

## Consequences

- Readers of the public repository get the code, dev, the datasheet, every decision and every
  number, but not the test items or the development history.
- Each public release is a snapshot commit that names the private commit it was made from.
- Scoring someone else's system on test goes through the maintainer, as with other benchmarks
  that keep their test set hidden.
