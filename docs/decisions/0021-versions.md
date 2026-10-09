# 0021. Versions for the benchmark and the code

Date: 2026-10-08
Status: accepted

## Context

Benchmark versions existed only in prose (v0 to v3 in the roadmap and the README), the code was
at 0.0.1 since its first commit, and nothing told someone citing Lex which questions or which
code they meant (ROADMAP 12.4). A run already records the version of the split it read: the hash
of what it scores (`bench.scored`, ROADMAP 9.6), which a validation sign-off or a source date
leaves unchanged.

## Decision

- **The benchmark** is `vN`. N moves when what a run scores changes in either split: an item
  added, removed or moved, a question, date, type or citation changed; in short, when a split's
  `scored` hash changes. Metadata (a reviewer's sign-off, `source.modified`) does not move it.
  Each version is tagged `bench-vN` on the public mirror's snapshot commit and on the Hugging Face
  dataset's revision, and `lex.eval.report.VERSIONS` maps the test split's hash to its name.
- **The code** is `0.N.P`: N is the benchmark version its published numbers are on, P a release
  without a new benchmark. It moves in `pyproject.toml` and `CITATION.cff` together (a test holds
  them equal), and a release is tagged `vX.Y.Z` on the mirror beside its `bench-vN`. 1.0 waits
  for the legal review of the test split (ROADMAP, Open).
- `CITATION.cff` names the code; the dataset card's BibTeX names the benchmark.

## Consequences

- One number says which benchmark a release's numbers are on: 0.3.0 reports v3's runs, and the
  release after Phase 10's milestone will be 0.4.0 with `bench-v4`.
- The tags live on the mirror and the dataset, which are published by hand (CLAUDE.md,
  Commands), so they are made when a snapshot is pushed, not by CI.
- Revisit if the code is released on its own schedule, apart from the benchmark: then the two
  numbers part.
