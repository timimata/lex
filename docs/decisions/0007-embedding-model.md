# 0007. BGE-M3 for the first dense baseline

Date: 2026-09-29
Status: accepted

## Context

The dense baseline needs an embedding model. The benchmark has 6 answerable dev items, far too
few to choose between models on their numbers, so the first choice rests on properties:

- **Length.** Article versions have a median of 889 characters, a 99th percentile of 3,515 and a
  maximum of 5,885 (about 1,500 tokens). About 10% are longer than roughly 512 tokens, where
  many multilingual encoders (e.g. multilingual-e5) stop reading.
- **Portuguese.** The texts and questions are European Portuguese.
- **Local and open.** Runs on this machine's CPU (no CUDA GPU; an AMD card), costs nothing per
  query, and is reproducible from a pinned revision.
- **Phase 5.** The model will be fine-tuned on (question, article) pairs with
  sentence-transformers.

BAAI/bge-m3 reads up to 8,192 tokens, is multilingual, open, and loads in sentence-transformers.
Checked on 2026-09-29 at revision `5617a9f61b028005a4858fdac845db406aefb181`: 1,024 dimensions; on
CPU it encoded 3 short texts in 0.43 s. A check on one benchmark question followed here; that item
is now in the test split, which no other file may quote (CLAUDE.md), so the check was removed on
2026-10-01.

## Decision

- The dense baseline embeds each article version as its heading and text, with BGE-M3 at the
  pinned revision, normalised, and ranks by cosine distance in pgvector, among the versions in
  force on the date asked about.
- Embeddings live in their own table, keyed by article version and model, with a hash of the
  embedded text, so reloading the store does not recompute them unless a text changed.
- sentence-transformers and PyTorch are an optional `dense` extra; CI tests the dense code with
  a toy embedder instead of the model.

## Consequences

- No chunking: every version fits whole, so a hit is always a whole article.
- Loading the model takes about two minutes the first time (a ~2 GB download) and seconds after.
- Revisit when dev has at least 50 answerable items: compare BGE-M3 with a Portuguese-specific
  encoder, and with the model fine-tuned in Phase 5.
