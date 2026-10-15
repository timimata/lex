# 0024. BGE-M3 fine-tuned on synthetic questions about the corpus

Date: 2026-10-10
Status: proposed (accepted or dropped by its dev run; not run when the project closed,
2026-10-15)

## Context

Phase 7 of the roadmap left fine-tuned embeddings waiting for a larger benchmark and a GPU. On
v4's dev the reference system's dense stage, BGE-M3, puts the right article first for 0.59 of the
81 answerable questions, against 0.75 for Gemini Embedding 2 (`results/dev/`); the reranker lifts
BGE-M3's ranking to 0.74. This machine gives PyTorch its CPU only (8 threads), enough for one epoch
over a few thousand pairs. There are no labelled pairs outside the benchmark, and benchmark items
cannot be used: dev is where the model is measured, and test is never read.

## Decision

- **Training data are synthetic, from the corpus alone:** Gemini 3.1 Flash-Lite writes 3
  questions a citizen could ask of each article in force with text (781 versions in force, the
  revoked left out), ten articles a request, through the eval's LLM cache
  (`python -m lex.finetune generate`, to `data/synthetic/questions.jsonl`). The questions live
  outside `bench/` and never enter it (CLAUDE.md); no benchmark item is read.
- **Training is fixed before the dev run, not tuned on dev:** BGE-M3 at its pinned revision,
  in-batch negatives (`MultipleNegativesRankingLoss`), one epoch, batch 16, learning rate 1e-5
  with a tenth of the steps of warmup, 384 tokens, seed 0, on the CPU
  (`python -m lex.finetune train`, to `data/models/bge-m3-lex/`; a plain torch loop, as
  sentence-transformers' trainer needs two more libraries).
- **Its vectors are its own:** the embedder's name holds a hash of the weights
  (`lex/bge-m3-ft@<sha>`), so they never mix with BGE-M3's, and the ranking cache follows it.
- **Measured on dev as two retrievers**, `dense-ft` and `dense-ft+rerank+refs`, against
  `dense` and `dense+rerank+refs`, item by item. Kept if it gains beyond the noise; otherwise
  dropped, and this ADR says so with the numbers.

## Consequences

- The model and the questions are rebuilt by the two commands; neither is committed (`data/`).
- The synthetic questions are written by the same model family that answers, about the same
  articles: a gain could partly be the model learning that family's phrasing. Only dev, written
  by people at public bodies, says whether it carries to real questions.
- A test run of a fine-tuned system waits for the next milestone.
