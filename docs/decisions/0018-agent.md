# 0018. The agent: what helped was its prompt, and it answers on the demo

Date: 2026-10-06
Status: accepted; amended 2026-10-06 (the coverage instruction alone) and 2026-10-07 (the agent
becomes the demo's system)

## Context

Composite questions are the benchmark's weak spot (on test v2 the demo gets 0.41 of them
correct). Deciding the parts before retrieval and following cross-references did not help them
on dev (ROADMAP, Phase 4), so Phase 7 tried an agent (`lex.generation.agent`): the demo's
per-sentence answer, after the model may ask, up to three times, for a search on a subject or
for articles by id. Its system prompt is the per-sentence one plus a paragraph: "before
answering, check whether the given articles cover every part of the question; if an article is
missing you may ask for more", and the two request formats.

Measured on dev v2 (84 items, 66 answerable; `results/dev/`, each run twice with `--repeat 1`,
a fresh sample of the same prompts, since Gemini's endpoint takes no seed):

| Dev v2 | Correct (run 1, run 2) | Answerable refused | Unanswerable refused | Citation recall | Composite correct |
|---|---|---|---|---|---|
| Per-sentence (the demo) | 0.68, 0.70 | 4, 4 of 66 | 18, 18 of 18 | 0.83, 0.83 | 0.47, 0.47 |
| Agent | 0.74, 0.74 | 0, 0 of 66 | 18, 18 of 18 | 0.87, 0.87 | 0.58, 0.53 |

In both agent runs the model made **no request**: 0 searches and 0 reads in 168 answers. Every
difference therefore comes from the system prompt, not from the loop. The two runs of each
system differ by one item in correct answers, so the gap between them (3 to 4 items, and the
four refusals of answerable questions gone) is larger than the noise measured, though on 66
items.

## Decision

- The agent loop is not kept: it adds code and, when used, calls and latency, and the model does
  not use it. `--format agent` stays runnable, as the record of this result.
- The demo keeps the per-sentence format for now. Its test numbers on v2 were measured with it,
  and the agent prompt mixes two things: the instruction to check that every part of the
  question is covered, and the description of requests the model could make. Which of them
  stops the refusals is not known.
- Next: measure the per-sentence prompt with the coverage instruction alone, twice on dev; if it
  holds, it becomes the demo's prompt, with a test run at that milestone.

## Consequences

- Every comparison on dev now has a measured noise floor to stand on: about one item in 66
  between two runs of the same system and prompt (two pairs of runs; more would narrow it).
  Earlier decisions taken on differences of one or two items (ROADMAP, Phases 3 and 4) may have
  been within it.
- Revisit an agent if the questions grow beyond what five retrieved articles can hold (the
  model never found anything missing here, with the demo's retrieval at dev recall@5 0.90).

## Amendment, 2026-10-06: the coverage instruction alone does not do it

`--format claims-cover` is the per-sentence prompt with the agent's one sentence that is not
about requests ("Antes de responder, vê se os artigos dados cobrem todas as partes da
pergunta."), word for word. One run on dev v2: 0.65 correct (43 of 66), 0.27 partial, 0.08
wrong; citation recall 0.85, precision 0.90; 2 of 66 answerable refused, 18 of 18 unanswerable
refused; composite 0.37 correct. That is no better than the per-sentence prompt (0.68 and
0.70), so the agent prompt's gain does not come from that sentence. What is left is the rest of
its text: that the model may ask for more articles, and should answer "when the articles
suffice, or if no request would help". A model told it could ask, and that what it holds may
be enough, refused no answerable question in two runs.

Next: the agent itself as the demo's system, since it is the measured configuration (0.74 twice)
and costs one call per question while the model asks for nothing. Before that, a time budget for
the demo (a request adds a search and a call, within Vercel's 30 s) and a test run at that
milestone. Not done today: the day's free quota is spent.

## Amendment, 2026-10-07: the agent becomes the demo's system

On benchmark v3 (dev 92 items, 68 answerable; test 109, 89 answerable), the agent against the
per-sentence prompt, with the same retrieval and model (`results/`):

| | Correct | Citation recall / precision | Answerable refused | Unanswerable refused | Composite correct |
|---|---|---|---|---|---|
| dev, per-sentence | 0.68 | 0.83 / 0.90 | 4 of 68 | 23 of 24 | 0.45 |
| dev, agent | 0.74 | 0.86 / 0.89 | 0 of 68 | 23 of 24 | 0.55 |
| test, per-sentence | 0.73 | 0.93 / 0.92 | 0 of 89 | 18 of 20 | 0.41 |
| test, agent | 0.76 | 0.94 / 0.92 | 0 of 89 | 18 of 20 | 0.47 |

The decision rests on dev, where the agent led in all three of its runs (0.74, 0.74, 0.74 against
0.68, 0.70, 0.68); the test run, taken after, agrees. The model still asks for nothing (0
requests in 109 test answers), so on the demo it costs one call per question, $0.00106 at paid
prices with its thinking (23,823 thinking tokens over the 109 calls). It is now the demo's
default (`LEX_ANSWER_FORMAT`, `claims` for the per-sentence answer), with the 9 s budget of
2026-10-06 bounding a request should the model make one. The loop is kept for that case; that
it helps by being offered rather than used is what the numbers say, not why.
