# 0022. Comparing outside tools by hand: Lia, not TogaAI

Date: 2026-10-10
Status: accepted

## Context

Phase 7 of the roadmap lists "a hand-scored comparison with Lia and TogaAI on a small dev subset,
after checking their terms". Read on 2026-10-10:

- **Lia** is the Diário da República's assistant, launched on 2025-02-11 by the INCM with Xpand IT,
  a retrieval-augmented system on Azure OpenAI and Azure AI Search over the DR's consolidated
  legislation ([Observador](https://observador.pt/2025/02/11/inteligencia-artificial-vai-facilitar-consulta-de-leis-em-diario-da-republica/),
  [Xpand IT](https://xpand-it.com/en/resources/success-stories/lia-intelligent-ai-assistant/)).
  It needs an account on diariodarepublica.pt or its app. No terms of use for Lia were found in
  public; they are presumably shown at registration.
- **TogaAI** is a subscription platform for law firms in Portugal
  ([CodeX TechIndex](https://techindex.law.stanford.edu/companies/togaai)); its site did not open,
  and it has no free access.

Neither offers an API, and scoring a tool by a script that drives its web page would go past what
its terms are known to allow.

## Decision

- **Lia is compared; TogaAI is not**, as it cannot be used without a paid subscription. Revisit if
  TogaAI offers access for evaluation.
- **A person asks and a person scores.** Tiago registers on the DR, reads Lia's terms and records
  here whether they allow publishing a comparison, then asks Lia each question of a fixed dev
  sample by hand, adding the date for a question about an earlier day, and writes what Lia
  answered and the articles it cited into `docs/comparison/lia.jsonl`.
- **The sample is fixed by code, not chosen:** `python -m lex.eval sample --per-type 4` takes, of
  each question type, the 4 dev items whose ids hash lowest (`lex.eval.outside.sample`): 20 items.
  Dev only: no test question is sent to an outside tool.
- **Scored as any system:** `python -m lex.eval answers --from docs/comparison/lia.jsonl --name lia
  --only-answered --judge` scores citations, refusals and versions and asks the judge; then
  `python -m lex.eval label lia` takes a person's labels, the hand score. `--only-answered`
  scores only the items the file answers, is refused on test, and the run records the sample size.

## Consequences

- 20 items show where a general tool and Lex differ (citations of versions, questions about an
  earlier date), not a ranking: differences of a few items are within the noise measured on dev
  (ADR 0018).
- Nothing is published about Lia before its terms are read and allow it.
