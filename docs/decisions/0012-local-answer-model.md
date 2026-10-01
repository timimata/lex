# 0012. A local answer model: Gemma 4 E2B, 4-bit, on llama.cpp

Date: 2026-09-30
Status: accepted

## Context

ADR 0011 chose Gemini for answers. On 2026-09-30 the first call returned HTTP 402: the Google
project behind the key has no prepaid credits left. Topping it up is Tiago's decision.

Tiago also wants to try a very small model on a Raspberry Pi with 4 GB of RAM. The quality of a
quantised model does not depend on the machine that runs it, only its speed does, so it can be
measured on this PC now and on the Pi later.

Checked on 2026-09-30 on Hugging Face: `ggml-org/gemma-4-E2B-it-GGUF` (revision
`b4243c156154b6dca9324415f8c7ccc098b4aed1`, Apache-2.0) has `gemma-4-E2B-it-Q4_0.gguf`, 2.84 GB,
sha256 `8e30dff3ac4c8434c49a7036fa15564bdbb6044e42bf04550bf1a096ad7e6a52`. Google made the E2B
for on-device use; the E4B at 4-bit is 4.59 GB and cannot fit in 4 GB. llama.cpp's
`llama-server` (build b11269, Vulkan) serves it through the same OpenAI-compatible interface as
Gemini, on this PC's AMD RX 9070 XT.

## Decision

- The reference system can answer with `gemma-4-E2B-it-Q4_0` on llama.cpp as well as with
  Gemini: `LLM_BASE_URL=http://127.0.0.1:8080/v1`, `LLM_MODEL=gemma-4-E2B-it-Q4_0`,
  `LLM_PARAMS={"seed": 0}` (llama.cpp's sampling defaults otherwise; not tuned on dev).
- The server runs with `-c 8192 -ngl 99 --jinja` and the model file checked against the sha256
  above. Both are outside the repo, in `~/.cache/llama.cpp/`.
- Each model gets its own dev and test results; the choice between them is made on dev.

## Consequences

- Answers cost nothing per question, nothing leaves the machine, and the model is pinned by
  file hash, which an API cannot promise.
- A model this small (2 billion effective parameters) follows the JSON format and the citation rules
  less reliably than a large one; the dev results count what goes wrong (`turned_into_refusals`).
- Whether it runs on the Pi, with what context length and speed, is not measured yet. Retrieval
  (BGE-M3 and the reranker) would not fit beside it in 4 GB (ADR 0011).

## Measured since

- 2026-09-30, Gemma 4 E4B, the next size up, which does not fit a 4 GB Pi:
  `gemma-4-E4B-it-Q4_K_M.gguf` from `lmstudio-community/gemma-4-E4B-it-GGUF` (revision
  `99210a71094c6aa8559f764e0cadedd7d89de94d`, sha256
  `0ffb122c8b6921f13cbc34186e052524d0b5803b17f4867b7197a561400b3770`), served by LM Studio's
  llama.cpp Vulkan runtime 2.47.0, context 8192, `{"seed": 0}`. On dev it matched the E2B's
  citation recall (0.84) with lower precision (0.81 against 0.89), so it is not kept.
- 2026-09-30, Gemini 3.1 Flash-Lite with a free-tier key: better than both on dev (see the
  roadmap), so it is the reference system's model, as ADR 0011 planned; the E2B stays as the
  measured local option.
