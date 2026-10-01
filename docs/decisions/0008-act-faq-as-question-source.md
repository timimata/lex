# 0008. The ACT's FAQ as the main source of benchmark questions

Date: 2026-09-30
Status: accepted

## Context

After two batches, the ACT's technical notes that concern the Código do Trabalho and are current
were nearly used up, and a 2008 ACT booklet had to be discarded as older than the code itself.
Reaching 100 items needs a larger source of real questions.

The ACT's FAQ page (portal.act.gov.pt/Pages/PerguntasFrequentes.aspx) is a SharePoint app. Checked
on 2026-09-30: it reads three SharePoint lists through the REST API under `/_api/`
(`FAQs`, `TemasFAQs`, `SubTemasFAQs`), and the whole FAQ comes back in one request with
`$top=5000`. The site's robots.txt disallows `/_layouts/`, `/_vti_bin/` and `/_catalogs/`, not
`/_api/`. No terms of use were found on the site; reuse of public administrative documents is
governed by Lei n.º 26/2016 (ADR 0005).

The lists hold 1,010 question-and-answer entries in 55 themes, each with the date the ACT last
modified it: 104 in 2022, 818 in 2023, 52 in 2024, 33 in 2025, 3 in 2026. The themes with most
entries are central to the code (termination, working time, parenthood, the employment contract,
holidays, absences), and others are outside the corpus (Lei n.º 102/2009, domestic work,
temporary work agencies).

## Decision

- Read the three lists with `python -m lex.ingest act-faq`: three requests, cached under
  `data/raw/act-faq/`, answers turned into plain text in `data/processed/act_faq.jsonl`.
- Draft benchmark items from these entries, keeping the ACT's question wording where it is
  self-contained. Each item's source URL is the entry's own API URL, and its notes record the
  entry's last-modified date.
- An entry's answer is never taken as correct because the ACT wrote it: every item is checked
  against the text in force on `as_of`. An entry last modified before an amendment to the
  articles it concerns gets particular attention.
- Entries from themes outside the corpus are good `unanswerable` items when the question could
  be mistaken for one the code answers.

## Consequences

- Questions are the ones people actually ask, in the ACT's words, rather than written by
  whoever drafts the item. This is closer to the rule that questions are never invented.
- Reaching 100 items becomes a matter of review time, not of finding sources.
- Before the dataset is published (Phase 6), its licence must account for the ACT's text.
