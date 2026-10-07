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

92 items of benchmark v3 (2026-10-06), 22 of them on tenancy. The test split, 109 items, stays
private so that its scores keep their meaning; results on it are published on the leaderboard and in the code repository
(`results/test/`). To have a system scored on test, open an issue on the code repository.

| Type | What it tests | Dev items |
|---|---|---|
| `simple` | One fact, one or two articles | 30 |
| `composite` | Several articles combined | 20 |
| `temporal` | `as_of` in the past; the answer depends on the law in force that day | 10 |
| `explicit_reference` | The question names its article | 8 |
| `unanswerable` | Outside the corpus; the right response is to say so | 24 |

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
| `status`, `validated_by` | `draft` until a legal reviewer signs the item off |
| `notes` | Where the source is behind the law, traps, and transitional rules |

## How it was made

Questions are never invented. Each is drawn from a public page: on labour, mostly the FAQ and
guidance of the Autoridade para as Condições do Trabalho (ACT); on tenancy, the Direção-Geral da
Administração da Justiça's pages on the eviction procedure and the Diário da República's
Lexionário. Each keeps its wording where it stands on its own; sources whose terms allow only
non-commercial reuse are not used. A language model drafted each item from its source, and the same model checked it against
the article versions in force on `as_of`; where the source was behind the law (several ACT
answers predate Lei n.º 13/2023), the item follows the law and says so in `notes`. No item has
been legally validated yet; that review is planned. The split is a hash of each item's main
article, so items about the same article always share a split and a dev item never gives away a
test answer.

## Metrics, and results on test

Systems are scored on citation recall and precision (against `must_cite` and `may_cite`), on
refusals (of unanswerable questions, and wrongly of answerable ones), and on correctness, judged
by an LLM against the reference answer. The judge is checked on known-answer cases rather than
hand labels: on dev it accepted 66 of 66 reference answers and caught 48 of 48 altered ones.

On test of benchmark v3 (89 answerable, 20 unanswerable), the demo's system (Gemini Embedding 2
retrieval with an explicit-reference parser, Gemini 3.1 Flash-Lite answering a citation per
sentence with the agent's prompt): 0.76 judged correct (0.20 partial, 0.03 wrong), citation
recall 0.94, precision 0.92, 0 of 89 answerable questions wrongly refused, 18 of 20 unanswerable
ones refused. Composite questions are the hardest: 0.47 correct.
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
