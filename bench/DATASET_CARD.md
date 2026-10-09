---
license: cc-by-4.0
language:
- pt
pretty_name: Lex
task_categories:
- question-answering
tags:
- legal
- portuguese
- labour-law
- tenancy-law
- benchmark
- retrieval-augmented-generation
size_categories:
- n<1K
configs:
- config_name: default
  data_files:
  - split: dev
    path: data/dev.jsonl
---

# Lex: questions on Portuguese labour and tenancy law, each with its date and the articles it must cite

Lex is an open benchmark for question answering over Portuguese legislation, in European
Portuguese. Each question comes with the date it is asked about (`as_of`): the right answer is
the law in force that day, so the same question can have different answers in 2011 and today.
Each also lists the articles a correct answer must cite. Some questions cannot be answered from
the corpus, and the right response to those is to say so.

The corpus is the Código do Trabalho (Lei n.º 7/2009), every article in every version since 2009,
and, on tenancy, the Código Civil's articles 1022.º to 1113.º and the NRAU (Lei n.º 6/2006), in
every version since 2006. It is not part of this dataset: the code rebuilds it from the Diário da
República and the PGDL.

- **Code, corpus builder, evaluation harness and reference system:** https://github.com/timimata/lex
- **Live demo and leaderboard:** https://lex-beryl.vercel.app

## This dataset: the dev split

Benchmark v4 (2026-10-09; v3 of 2026-10-06 less 13 test items that joined their groups in dev,
ADR 0009 amended). The test split stays private so that its scores keep their meaning;
results on it are published on the leaderboard and in the code repository (`results/test/`). To
have a system scored on test, open an issue on the code repository.

<!-- counts: written by python -m lex.bench card; edit the code, not this block -->
Dev has 105 items, 22 of them on tenancy; test has 96.

| Type | What it tests | Dev items |
|---|---|---|
| `simple` | One fact, one or two articles | 35 |
| `composite` | Several articles combined | 24 |
| `temporal` | `as_of` in the past; the answer depends on the law in force that day | 13 |
| `explicit_reference` | The question names its article | 9 |
| `unanswerable` | Outside the corpus; the right response is to say so | 24 |

Validated by a legal reviewer (`status`, `validated_by`): 0 of the 105 dev items and 0 of the 96 test items.

From the ACT's portal: 74 of the 105 dev items.
Of the dev items drawn from the ACT's FAQ, 60, 37 keep its question word for word (see Contamination).
<!-- /counts -->

## Fields

| Field | Meaning |
|---|---|
| `id` | `ct-0001` is the first Código do Trabalho item, `ar-0001` the first tenancy (arrendamento) item |
| `question` | As a person would ask it, in PT-PT |
| `as_of` | The date the question is about |
| `type` | One of the types above |
| `must_cite` | Articles without which the answer is wrong: `{"diploma": "lei-7-2009", "article": "238"}`; the Código Civil is `dl-47344-1966`, the NRAU `lei-6-2006` |
| `may_cite` | Articles a good answer may also cite without penalty |
| `answer` | A short reference answer, checked against the law in force on `as_of` |
| `source` | The public page the question came from, and the day it was read |
| `reviewed_by` | Who checked the item against its source and the law: here, the model that drafted it |
| `status`, `validated_by`, `validated_on` | `draft` until a legal reviewer signs the item off, then who and when |
| `notes` | Where the source is behind the law, traps, and transitional rules |

## How it was made

Questions are never invented. Each is drawn from a public page: on labour, mostly the FAQ and
guidance of the Autoridade para as Condições do Trabalho (ACT); on tenancy, the Direção-Geral da
Administração da Justiça's pages on the eviction procedure and the Diário da República's
Lexionário. Each keeps its wording where it stands on its own; sources whose terms allow only
non-commercial reuse are not used. A language model drafted each item from its source, and the same model checked it against
the article versions in force on `as_of`; where the source was behind the law (several ACT
answers predate Lei n.º 13/2023), the item follows the law and says so in `notes`. No item has
been legally validated yet; that review is planned. The split is a hash of each item's group,
its main article with every item linked to it, so a dev item never gives away a test answer.

## Uses

Intended: measuring systems that answer questions on Portuguese labour and tenancy law from the
law itself, for a given date, with citations, and that refuse what the law they hold does not
answer; comparing such systems on dev, and on the private test split through the maintainer.
Out of scope: legal advice, or anything a person relies on instead of a lawyer or the Diário da
República; training a model on the test split's questions, which are private for that reason; and
reading a score as a measure of law beyond the corpus (the Código do Trabalho, the Código Civil's
articles on leases, the NRAU).

## Contamination

The questions come from public pages, mostly the ACT's, which may be in the training data of the
models measured: a model may have read a question and the ACT's own answer. The counts above say
how many dev items come from the ACT's portal and how many keep its FAQ's question word for word.
Three things limit what such a model gains: the reference answers follow the law where the ACT's
pages are behind it, temporal items ask about the law of an earlier date, and a system is scored
on citing the right versions, which the ACT's pages do not give. A score on these items may still
be higher than on questions no model has seen, and is read that way. Test questions and their
reference answers are also sent to Google's Gemini API on its free tier by test runs (the
judge, and the answer model where a run says so), on terms that let Google use prompts to improve
its products: every run in `results/test/` records each model's endpoint and tier. A model trained
on those prompts may score higher on test than it would on unseen questions (ADR 0016, amended
2026-10-09).

## Personal data

None, by rule (bench/README.md, rule 3): the sources are public bodies' general guidance, not
cases, and a question drawn from a real case is rewritten generically.

## Biases and limits

- One source dominates: the ACT's FAQ and guidance frame labour questions as a worker or an
  employer asks a public body, not as a lawyer or a court would.
- One model drafted every item and the same model reviewed it (`reviewed_by`); no item has been
  legally validated yet (the counts above).
- Tenancy questions come from fewer sources (the DGAJ's pages on eviction, the Lexionário), and
  the corpus holds the Código Civil's leases only, not its general rules.
- Small: tens of items per type, so differences of a few items between systems are within the
  noise two runs of one system show (ADR 0018, amended).

## Maintenance and contact

Maintained by Tiago Machado. Errors in an item, proposals of questions, and requests to score a
system on test go through the code repository's issues (CONTRIBUTING.md there says how); security
reports through its private vulnerability reporting.

## Metrics, and results on test

Systems are scored on citation recall and precision (against `must_cite` and `may_cite`), on
refusals (of unanswerable questions, and wrongly of answerable ones), and on correctness, judged
by an LLM against the reference answer. The judge is checked on known-answer cases rather than
hand labels: on v4's dev, at temperature 0, it accepted 81 of 81 reference answers, caught 57 of
57 altered ones, and judged none of 132 answers built to test leniency correct (a reference with
a contradicting sentence appended, another question's answer), 129 of them as expected.

On test of benchmark v4 (76 answerable, 20 unanswerable), answered from no cache and judged three
times, the demo's system (Gemini Embedding 2 retrieval with an explicit-reference parser, Gemini
3.1 Flash-Lite answering a citation per sentence with the agent's prompt): 0.70 judged correct
(0.29 partial, 0.01 wrong), citation recall 0.92, precision 0.90, 1 of 76 answerable questions
wrongly refused, 19 of 20 unanswerable ones refused. Composite questions are the hardest: 0.38
correct.
The full leaderboard is on the demo's Results page.

## Licence and attribution

CC BY 4.0. Attribute as: *Lex, an open benchmark for questions on Portuguese legislation, by
Tiago Machado (2026)*. Each question is drawn from a public body's page, reused under Lei n.º
26/2016 with its source named; every item's `source` carries that attribution.

```bibtex
@misc{lex2026,
  title  = {Lex: an open benchmark for question answering over Portuguese legislation},
  author = {Tiago Machado},
  year   = {2026},
  url    = {https://github.com/timimata/lex}
}
```

## Not legal advice

Consolidated texts have no legal value: only the publication in the Diário da República is
authentic. Nothing in this dataset is legal advice.
