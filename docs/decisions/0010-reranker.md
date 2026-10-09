# 0010. BGE-reranker-v2-m3 over the dense retriever's top 20

Date: 2026-09-30
Status: accepted for the reference system; amended 2026-10-08 (not in the demo)

## Context

Dense retrieval with the reference parser finds the right article in the top 10 for 94% of dev
questions but ranks it first for 81%. A cross-encoder reads the question and each candidate
together, which usually orders a short list better than comparing two separately made vectors.
Candidates must be read whole: article versions reach about 1,500 tokens (ADR 0007).

BAAI/bge-reranker-v2-m3 is built on the same multilingual model as the embeddings, is open, and
runs on this machine's CPU. A check on one benchmark question followed here; that item is now in
the test split, which no other file may quote (CLAUDE.md), so the check was removed on 2026-10-01.

## Decision

- Rerank the dense retriever's top 20 candidates (a usual depth, not tuned on dev) with
  bge-reranker-v2-m3 at the pinned revision, each candidate as its heading and text at `as_of`.
- The reference parser still goes first: an article the question names is not reranked away.

## Consequences

- On dev, recall@1 0.81 -> 0.84, recall@3 0.90 -> 0.93, recall@10 0.94 -> 0.96. Each 0.025 is
  one of 40 questions, so this is a gain of one or two questions; it is kept because the rule is
  to keep what improves dev, and revisited if it does not hold on test.
- `max_length` 1,024 truncates the longest versions for the reranker only; the retriever and the
  answer still see them whole.
- About 20 cross-encoder passes per question on CPU: seconds per question, acceptable for the
  benchmark and the demo, to be watched for the API.

## Amendment, 2026-10-08: the demo has no reranker

This ADR found the reranker's cost acceptable "for the benchmark and the demo". The demo never ran
it: a Hugging Face Space could not hold it beside the other models ([ADR 0013](0013-demo-hosting.md))
and the serverless demo has no model server ([ADR 0014](0014-serverless-demo.md)). It reranks in
the reference system only; on test v3 that system's retrieval (recall@1 0.76, recall@10 0.94)
trails the demo's, which has none (0.81, 0.99).
