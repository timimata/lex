# 0024. BGE-M3 fine-tuned on synthetic questions about the corpus

Date: 2026-10-10
Status: dropped 2026-10-15: no gain on dev beyond the noise (see Result)

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

## Result (2026-10-15)

`generate` wrote 2,277 questions in 76 requests; `train` ran 143 steps on the CPU, with
gradient checkpointing (the same updates; a batch's activations kept whole outgrew 31 GB of
RAM), to weights `dd3dab6608b7`. On v4's dev, 81 answerable questions, item by item with the
sign test of ADR 0018 ([results/dev/](../../results/dev/)):

| | recall@1 | recall@5 | recall@10 |
|---|---|---|---|
| `dense` (BGE-M3) | 0.59 | 0.72 | 0.75 |
| `dense-ft` | 0.53 | 0.76 | 0.79 |
| `dense+rerank+refs` (the reference system) | 0.74 | 0.86 | 0.93 |
| `dense-ft+rerank+refs` | 0.74 | 0.87 | 0.93 |

Alone, the fine-tuned model puts the right article first less often (better on 4 items, worse
on 11, p = 0.12) and in the top 5 more often (7 against 4, p = 0.55); behind the reranker it
changes almost nothing (top 5: 2 against 1, p = 1.00). No difference is beyond the noise, so
the reference system keeps BGE-M3 as published, and the code stays to repeat the experiment
on a larger benchmark.
