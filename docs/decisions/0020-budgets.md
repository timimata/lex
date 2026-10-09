# 0020. The budgets that live in code, in one place

Date: 2026-10-08
Status: accepted

## Context

The demo, the eval runs and the checks rest on numbers set in code, each with a reason given at
the time in a commit or a comment, none gathered. Two disagreed: `Limits` defaulted to 500
answers a day while the demo, through `LEX_ANSWERS_PER_DAY`, allowed itself 400.

## Decision

These are the budgets, each with its constant and its reason. A change to one is a change to this
ADR.

| Budget | Value | Where | Why |
|---|---|---|---|
| Answers per visitor | 20 an hour | `Limits.per_visitor_per_hour`, `LEX_ANSWERS_PER_VISITOR_PER_HOUR` | one visitor cannot spend the day's quota |
| Answers a day, all visitors | 400 | `Limits.per_day`, `LEX_ANSWERS_PER_DAY` | under Gemini Embedding 2's 1000 a day on the free tier, with room for the agent's searches; the gate's day is the quota's (Pacific) day |
| Answers kept in an instance's cache | 1000 | `Limits.cached_answers` | memory of a serverless function |
| The agent's budget before a request | 9 s | `demo_system(budget=9.0)` | one more call (18 s at most) still fits in Vercel's 30 s; past it, a 503 (ROADMAP, Phase 11) |
| A model call on the demo | 18 s, no client retries | `demo_system`, `llm.from_env(timeout=18, max_retries=0)` | fits twice in 30 s with retrieval |
| An overloaded model, on the demo | asked again after 1 s and 2 s, only if it refused within 5 s | `overload_waits=(1, 2)`, `QUICK_FAILURE` | an overload passes in seconds; a slow failure would not fit |
| An embedding call on the demo | 8 s, no retries | `ApiEmbedder(timeout=8, max_retries=0)` | a question is one short text |
| A function's run on Vercel | 30 s | `vercel/vercel.json`, `maxDuration` | the free tier's ceiling for the function |
| Eval runs: a rate limit | waited out 30, 60, 120 s | `RATE_LIMIT_WAITS` (llm, dense) | free tiers limit requests per minute |
| Eval runs: an overloaded model | waited out 15, 30, 60 s | `OVERLOAD_WAITS` | an eval run can wait out a busy hour |
| Fetching the law | one request at a time, 2 s apart, then 30, 60, 120 s on 429 or 5xx | `MIN_INTERVAL_S`, `BACKOFF_S` | CLAUDE.md: polite fetching |
| Articles given to the model | 5 | `answer.K` | a usual size, not tuned on dev |
| The agent's requests | 3, each adding 3 articles at most | `agent.STEPS`, `agent.PER_SEARCH` | set, not tuned |
| The probe's bars | 20 s for the first request, 5 s for the rest | `probe.COLD_BAR`, `probe.BAR` | the first may wake a cold function |
| The judge's known-answer checks | 90% for each group | `judge.CHECK_PASS` | set before the first check ran (ADR 0015) |
| A regression | a loss a one-sided sign test puts under 0.05 | `compare.ALPHA` | replaced a margin of two answers (ROADMAP, Phase 10) |
| The mirror's leak scan | half or more of a test text's own six-word runs; a test id within 200 characters of its article | `snapshot.TELLING_SHARE`, `TELLING_MIN`, `NEAR` | ADR 0016; set on constructed leaks |

`Limits.per_day` defaults to 400, as the demo uses.

## Consequences

- A reader can see what the demo allows itself and why, without reading the code.
- The daily cost bound in the README is this table's 400 answers times the measured cost of one.
