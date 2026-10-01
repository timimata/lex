# 0011. Gemini 3.1 Flash-Lite through an OpenAI-compatible endpoint, for answers

Date: 2026-09-30
Status: accepted. On 2026-09-30 the key's project had no prepaid credits (HTTP 402); a local
model is measured meanwhile ([ADR 0012](0012-local-answer-model.md)).

## Context

The reference system needs a language model to turn the retrieved article versions into a
short answer with citations, or a refusal. The benchmark, not the model, is the product: what
matters is that the model can be swapped and every swap measured on the same items.

Tiago already runs Google's Gemini through its OpenAI-compatible endpoint
(`https://generativelanguage.googleapis.com/v1beta/openai/`) with `gemini-3.1-flash-lite` in
another project, so a key and a working setup exist. Checked on 2026-09-30 on
[ai.google.dev](https://ai.google.dev/gemini-api/docs/models): `gemini-3.1-flash-lite` is a
stable model, the cheapest of the current Flash models on the paid tier ($0.25 per million input
tokens, $1.50 per million output), with a free tier. On the free tier, Google uses prompts and
responses to improve its products; on the paid tier it does not.
[The compatibility layer](https://ai.google.dev/gemini-api/docs/openai) documents
`reasoning_effort` (thinking cannot be turned off on Gemini 3 models) and documents no `seed`.

The same interface is served by llama.cpp's server, Ollama and LM Studio. Tiago wants, later, to
try a very small model on a Raspberry Pi with 4 GB of RAM; through this interface that is a
change of URL and model name.

## Decision

- Answers come from `gemini-3.1-flash-lite` through the OpenAI-compatible endpoint, with the
  `openai` client. `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` in `.env` point it elsewhere.
- `reasoning_effort` is `low`, a default that keeps latency and cost down, not tuned on dev. No
  `temperature` or `seed` is sent: the endpoint documents no seed, and every eval call goes
  through a disk cache keyed on model, parameters and prompt (CLAUDE.md), which is what makes a
  run reproducible. Each result records the model id and the tokens its answers used.
- The model reads only the article versions the retriever returned for the question's date, and
  replies with JSON: the answer, the article numbers it relied on, and whether it refuses. The
  system keeps only citations of articles it was given, and an answer left with none becomes a
  refusal (CLAUDE.md: no citation, no claim).
- No LLM judge yet. Answer correctness is "not measured yet" until there are hand labels on dev
  to measure a judge's agreement against (CLAUDE.md); citation precision and recall and the
  refusal rates are computed without one.

## Consequences

- Swapping the model is a configuration change followed by a dev run, and each model's numbers
  sit side by side in `results/`. The Raspberry Pi is an experiment for later: a 4 GB board can
  hold a 1 to 3 billion parameter model quantised to 4 bits, but not also BGE-M3 and the
  reranker (about 2.2 GB each at full precision), so retrieval would stay on another machine or
  be quantised too. Its speed and quality are not measured yet.
- On the free tier, benchmark questions and the retrieved articles reach Google and may be used
  for training. Both are public already (the questions come from public pages, the articles from
  the DR); the reference answers are never sent. A paid key avoids this, and is worth it before
  the benchmark is published (Phase 6).
- A different model changes the cache key and gets its own dev run. A model changed by its
  provider under an unchanged name would not, so each cached response keeps the date it was made.
