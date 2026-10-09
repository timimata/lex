# 0015. An LLM judges answers against the reference

Date: 2026-09-30
Status: accepted; amended 2026-10-01 (known-answer checks while there are no hand
labels; the judge is Gemma 4 26B A4B, as Gemini 3.8 Flash allows 20 requests a day) and
2026-10-08 (checks on today's dev only; cases for leniency)

## Context

Citation recall and precision say whether an answer rests on the right articles, not whether
what it says is right. A person asking the benchmark's question wants the second. CLAUDE.md
allows an LLM judge only next to its measured agreement with hand labels on dev.

Every benchmark item has a short reference answer, checked against the law on its date
(bench/README.md). The answer model is Gemini 3.1 Flash-Lite (ADR 0011); a model judging its own
family's writing tends to favour it. Checked on 2026-09-30, the key also serves
`gemini-3.8-flash`, the newest stable Flash, on the free tier.

## Decision

- The judge is `gemini-3.8-flash`, with the prompt in `lex/eval/judge.py`: it reads the question,
  the date, the reference answer and the system's answer, and says `correta`, `parcial` or
  `errada`. The list of sources at the end of an answer does not count.
- A refusal of an answerable question is `errada` without asking the judge.
- Hand labels (`python -m lex.eval label SYSTEM`) are made by a person on dev answers only, one per
  answer wording, with the labeller's name, in `bench/labels/dev.jsonl`. Refusals are not
  labelled: their verdict is not the judge's, and agreeing on them would inflate agreement.
- `python -m lex.eval judge SYSTEM` judges that system's dev answers and measures agreement:
  the share of equal verdicts and Cohen's kappa, over at least 20 labelled answers.
- `answers --judge` adds correctness to a run only if the judge, with the same model and prompt,
  has been measured on that system's dev answers; the result carries that agreement.

## Consequences

- Correctness becomes reportable once Tiago has labelled about 40 dev answers (half an hour).
  Until then it stays "not measured yet".
- A kappa well below the raw agreement means the judge mostly agrees by saying the common verdict;
  both are reported so a reader can see it.
- Changing the judge's model or prompt invalidates its measurement: it must be judged on dev
  again before any correctness number is reported.

## Amendment, 2026-10-01: known-answer checks while there are no hand labels

Tiago chose not to hand-label answers. Until someone does, the judge is measured on answers whose
verdict is known by construction, built by code (`lex.eval.judge.known_cases`) from the
reference answers of the 40 answerable dev items:

- the reference answer as it is: the judge must say `correta`;
- the same answer with its first quantity changed (days, hours, months, a percentage, in figures
  or in words; never an article, a law, a date or a decimal): it must not say `correta`;
- a yes-or-no reference with its first word turned over ("Não" for "Sim"): it must not say
  `correta`.

The bar was set and committed before the first check ran: at least 90% of the references judged
`correta`, and at least 90% of the altered answers judged `parcial` or `errada`.
`python -m lex.eval judge-check` writes `results/dev/judge-check.json`; `answers --judge`
reports correctness only if the judge, with the same model and prompt, passed it, and the run
records the check's counts. Hand labels, where they exist, take precedence.

What this shows: the judge accepts a right answer worded as the reference, and catches a wrong
number or a turned-over conclusion. What it does not: how the judge treats real answers, which
paraphrase, hedge, or mix right and wrong (the demo's dev answer to ct-0004, on holidays
interrupted by a death in the family, states the rule and then doubts it applies). Correctness
measured this way is always reported with that limit.

## Amendment, 2026-10-01: the judge is Gemma 4 26B A4B

The first check stopped on Gemini 3.8 Flash's free quota: 20 requests a day for that model (from
its own error, quota `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, 2026-10-01), against
68 checks and about 50 test answers. The same key serves Google's open Gemma 4 models free. The
judge is now `gemma-4-26b-a4b-it`: a different family from the answers' Gemini, which also
removes the worry above about a model favouring its own family's writing; one probe call on one
altered dev case took 9 s and found the error (`gemma-4-31b-it` took 70 s). On that API Gemma
takes neither system instructions nor a reasoning effort: the instructions open the user's
message, and its reasoning block (`<thought>...</thought>`) is skipped when the verdict is read.
The prompt and the bar are unchanged; no check had finished before the change.

## Amendment, 2026-10-08: checks on today's dev, and cases for leniency

The check of record (`results/dev/judge-check.json`) ran on benchmark v2's dev, and nothing
held it to the dev of the day: `answers --judge` compared the judge's model and prompt, never
the split. Its cases show that the judge catches a right answer made wrong in one place; none
shows that it refuses a wrong answer that still sounds right.

- A measurement of the judge (hand labels or the known-answer checks) counts only on the dev
  version it ran on, by `bench.scored`; on another, `answers --judge` refuses until the judge is
  measured again.
- Two kinds of case join the check, built by code (`lex.eval.judge.known_cases`):
  `contradicted`, the reference answer whole followed by "Contudo," and its first sentence with
  a quantity changed or its yes or no turned over, which must not be judged `correta`; and
  `other`, the reference answer of another item, halfway round the list and sharing no article
  with this one, which answers another question and must be judged `errada`.
- Together they are the `lenient` group, which must reach the same bar as the others, 90%: set
  and committed before they first ran.
