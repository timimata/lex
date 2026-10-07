# The benchmark

Questions about Portuguese legislation in European Portuguese, each with the date it is asked
about and the articles a correct answer must cite. The corpus they are asked of is the Código do
Trabalho and, since 2026-10-01, tenancy: the Código Civil's articles 1022.º to 1113.º and the
NRAU ([ADR 0017](../docs/decisions/0017-tenancy.md)).

## Files

| File | What it's for |
|---|---|
| `drafts/` | Drafted items waiting for review, with a review sheet per batch. Read by nothing |
| `data/incoming.jsonl` | New items, reviewed, not yet in a split |
| `data/dev.jsonl` | Development: read it, tune on it, study the failures |
| `data/test.jsonl` | Reported numbers only. Read by the eval harness and nothing else |

`python -m lex.bench assign` moves every item from `incoming` to the split its group dictates. The
group is the item's main article (its first `must_cite`), or its id if it cites nothing, and the
split is a hash of the group: roughly half and half, nobody chooses it, it never changes, and
items about the same article always share a split
([ADR 0009](../docs/decisions/0009-split-by-main-article.md)). So put the article that answers
the question first in `must_cite`.
`python -m lex.bench validate` checks every file and prints counts, never content: the schema,
that `as_of` fits the item type, that each item sits in its group's split, no repeated questions,
and, when the corpus has been ingested, that every cited article of a diploma it holds exists
and every `must_cite` article has a version in force on `as_of`. It also names, by id, any
`unanswerable` item written for the Código do Trabalho alone that speaks of tenancy, for a
person to check that refusing is still right. CI runs it (without the corpus, which is
not committed).

## An item

One JSON object per line. Wrapped here for reading:

```json
{
  "id": "ct-0001",
  "question": "Quantos dias úteis de férias tem, no mínimo, um trabalhador por ano?",
  "as_of": "2026-09-29",
  "type": "simple",
  "must_cite": [{"diploma": "lei-7-2009", "article": "238"}],
  "may_cite": [],
  "answer": "O período anual de férias tem a duração mínima de 22 dias úteis.",
  "source": {"url": "<page the question came from>", "title": "<its title>", "retrieved": "2026-09-29"},
  "reviewed_by": "Tiago Machado",
  "status": "draft",
  "validated_by": null,
  "notes": ""
}
```

| Field | Meaning |
|---|---|
| `id` | Corpus prefix and number: `ct-0001` is the first Código do Trabalho item, `ar-0001` the first tenancy (arrendamento) item. Never reused |
| `question` | As a person would ask it, self-contained, in PT-PT |
| `as_of` | The date the question is about. The right answer is the law in force that day |
| `type` | See below |
| `must_cite` | Articles without which the answer is wrong |
| `may_cite` | Articles a good answer may also cite without penalty |
| `answer` | Short reference answer, in the source's words where possible |
| `source` | The public page the question and answer come from |
| `reviewed_by` | Who checked it against the source and the law before it entered the benchmark: a person's name, or the model that did it |
| `status`, `validated_by` | `draft` until a legal reviewer signs it off; `validated` names them |
| `notes` | Anything a reviewer should know |

A citation is `{"diploma": ..., "article": ...}`. The diploma id is type, number and year in
lowercase (`lei`, `dl`, `portaria`, ...), with the number's letter if it has one
(`dl-321-b-1990`). The Código do Trabalho is `lei-7-2009`, the law that approved it; the Código
Civil is `dl-47344-1966`, and the NRAU `lei-6-2006`. Article numbers are written as the DR prints them, without ".º": `238`, `238-A`.

## Types

| Type | What it tests |
|---|---|
| `simple` | One fact, one or two articles |
| `composite` | Several articles combined |
| `temporal` | `as_of` in the past, and the answer depends on the law in force that day |
| `explicit_reference` | Names an article: "o que diz o artigo 238.º do Código do Trabalho?" |
| `unanswerable` | Outside the corpus, or not answerable from the law. The right response is to say so |

Benchmark v3 (2026-10-06) has 201 items: 76 `simple`, 37 `composite`, 27 `temporal`, 17
`explicit_reference` and 44 `unanswerable`; 92 in dev and 109 in test. Of these, 43 are on
tenancy (`ar-`), 22 in dev and 21 in test; the rest are the 158 items of v1 (2026-10-01), on the
Código do Trabalho. v2 (2026-10-02) had the first 23 tenancy items, 181 in all. Every run records
which version of its split it used (`bench` in `results/`); v0's test runs are in
`results/test/v0/`, those on the intermediate 132-item state in `results/test/v1-132/`, v1's in
`results/test/v1/` and v2's in `results/test/v2/`.

Targets for v0 (100 items): at least 15 `temporal`, 15 `explicit_reference` and 15 `composite`,
about 10 `unanswerable`, the rest `simple`. For non-temporal items, `as_of` is the date the item
was written.

## Writing rules

1. Every item comes from a public page with a URL: the ACT's guidance, the DGAJ's pages, the
   Diário da República's Lexionário, other public bodies' legal information. A source whose terms
   allow only non-commercial reuse (gov.pt, the Portal da Habitação) is not used: the benchmark
   is CC BY 4.0. Questions are never invented, by a person or an LLM. An LLM
   may draft an item from a source it was given. Before it goes into `incoming`, the draft is
   checked against the source and the law, and `reviewed_by` names who did it. When that is the
   model that drafted it, the review is not independent; results can be reported separately for
   items a person reviewed, and legal validation (`validated_by`) is always a person.
2. The `must_cite` articles are checked against the text in force on `as_of`, not just copied
   from the source.
3. No personal data. A question drawn from a real case is rewritten generically.
4. PT-PT spelling and vocabulary, not PT-BR.
5. Once assigned, an item changes only to fix a labelling error, one commit per fix, saying why.
6. A `temporal` item's answer is what the law was on `as_of`, including the amending diplomas'
   transitional and effects provisions, even where the store cannot represent them (a rule whose
   effects started later than its text, a revoked rule that transitionally survived; ADR 0002).
   The benchmark measures the law, not the store. Such items say so in `notes`, and may cite the
   amending diploma's provision in `may_cite`.
7. After `assign`, a batch's draft file is deleted, and its review sheet keeps items assigned to
   test as ids only. A test item's content exists in `test.jsonl` and nowhere else.

## Metrics

- **recall@k**: share of `must_cite` articles among the top k retrieved, over answerable items.
- **Citation precision**: share of cited articles that are in `must_cite` or `may_cite`,
  averaged over the answers that cite something (the result says how many).
- **Citation recall**: share of `must_cite` articles the answer cites, averaged over every
  answerable item.
- Both citation metrics are computed over answerable items only. On an `unanswerable` item
  only the refusal is scored, so citing a related article while refusing costs nothing. A
  refused answer counts as citing nothing, so wrongly refusing an answerable item costs its
  citation recall.
- **Refusals**: share of `unanswerable` items refused, and share of answerable items wrongly
  refused, reported separately.
- **Answer correctness**: an LLM judge, reported only next to how it was measured on dev: its
  agreement with hand labels or, while there are none, the known-answer checks it must pass first
  (ADR 0015). Before that amendment the rule read: next to its measured agreement with hand
  labels on dev.

Everything is reported per type as well as overall.

## Licence

CC BY 4.0 ([LICENSE.md](LICENSE.md)), attributed to Lex and, item by item, to the source each
question was drawn from. The test split is not published: its results are, its items are not
([ADR 0016](../docs/decisions/0016-licences-and-hidden-test.md)).
