# 0011. Gemini 3.1 Flash-Lite through an OpenAI-compatible endpoint, for answers

Date: 2026-09-30
Status: accepted; amended 2026-10-08 (the key, the judge, the format, the terms). On 2026-09-30
the key's project had no prepaid credits (HTTP 402); a local model was measured meanwhile
([ADR 0012](0012-local-answer-model.md)).

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
  the DR); the reference answers are not sent by the answers themselves, but the judge (ADR
  0015) sends them, test included: ADR 0016, amended 2026-10-08, lists what leaves the machine
  and requires a paid key for test runs. A paid key avoids this, and is worth it before
  the benchmark is published (Phase 6).
- A different model changes the cache key and gets its own dev run. A model changed by its
  provider under an unchanged name would not, so each cached response keeps the date it was made.

## Amendment, 2026-10-08: what changed since

- The model has answered through a free-tier key since 2026-09-30 ([ADR 0012](0012-local-answer-model.md),
  "Measured since"); the 402 no longer applies.
- "No LLM judge yet": an LLM judge has scored correctness since 2026-10-01
  ([ADR 0015](0015-answer-judge.md)), measured on known-answer cases.
- The reply is no longer one answer with a list of citations: the demo answers a citation per
  sentence ([ADR 0014](0014-serverless-demo.md), amended) with the agent's prompt
  ([ADR 0018](0018-agent.md)); the format here is the reference system's default.
- The paid key this ADR thought worth having before publication was not used: the benchmark was
  published with test runs made on the free tier. Since 2026-10-08 test runs reach outside models
  on a paid key only ([ADR 0016](0016-licences-and-hidden-test.md), amended), and the judge, which
  Google serves on the free tier alone, needs another home before a judged test run.
- Temperature is still the provider's default; whether to set it is measured and decided in
  Phase 10 of the roadmap (decided below).

## Amendment, 2026-10-08: temperature

Read on 2026-10-08: Google's guide to Gemini 3 "strongly recommend[s] keeping the temperature
parameter at its default value of 1.0", and warns that a lower one "may lead to unexpected
behavior, such as looping or degraded performance"
([ai.google.dev](https://ai.google.dev/gemini-api/docs/gemini-3)); Gemma 4's model card
recommends temperature 1.0, top_p 0.95 and top_k 64 "across all use cases"
([Hugging Face](https://huggingface.co/google/gemma-4-26b-a4b-it)).

Measured on the demo's dev answers, the answers from the cache so that only the judge varies
(ROADMAP 10.3 and 10.5):

| Judge | Samples that disagree | Judged correct | Known-answer checks (references, altered, lenient) |
|---|---|---|---|
| Provider's default (`results/dev/archive/...+judge-3-provider.json`, `judge-check-provider.json`) | 8 of 67 | 49 of 68 | 68 of 68, 48 of 48, 110 of 110 |
| Temperature 0 (`results/dev/...+judge-3.json`, `judge-check.json`) | 0 of 67 | 49 of 68 | 68 of 68, 48 of 48, 110 of 110 |

At temperature 0, three verdicts differ from the default's median, each by one step.

- **The judge sends temperature 0** (`lex.eval.gates.JUDGE_PARAMS`; `JUDGE_PARAMS` in `.env`
  overrides it, `{}` for the provider's default). Measured, it removes the judge's own noise and
  keeps every known-answer case, against the model card's general advice: a judge is asked for a
  verdict, not prose. A judge with other parameters is another judge, with its own known-answer
  check (`judge-check-<params>.json`). A local server's default temperature is its own, so a
  judge moved there (ADR 0016) still sends 0 explicitly.
- **The answer model keeps the provider's default**, 1.0 for Gemini 3, sent as nothing: Google
  advises against lower values for these models, and not measured lower here, as the dev runs
  that would test it are spent against the free tier's 500 requests a day. The run-to-run noise
  measured with `--repeat` (8 of 68 verdicts, ADR 0018) is the model's with the judge's in it;
  with the judge at 0, a repeat now measures the model's alone.
- Every run records what it sent: `llm_params` for the answer model (no temperature: the
  provider's default) and `judge.params` for the judge. The test runs of v3 were judged at the
  provider's default; the milestone's are judged at 0.
