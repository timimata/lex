# Lex: a technical report (draft)

A draft, written as the roadmap's Phase 12 asks: every number in it links to its file in
`results/`. Its sections on the benchmark, the system and the results are written from the runs
of Phase 10's milestone (benchmark v4, 2026-10-09); the related work comes first.

## Related work

Each work below was read for what it measures and how; the differences listed are what Lex adds
or leaves out, not judgements of the works.

**Legal benchmarks for language models.** LexGLUE (Chalkidis et al., ACL 2022) gathers English
legal understanding tasks, mostly classification of court decisions and contracts, into one
evaluation. LegalBench (Guha et al., NeurIPS 2023) collects 162 tasks of legal reasoning,
designed by legal professionals, under six types of reasoning, and evaluates 20 models on them.
Both measure what a model knows or infers from text it is given; neither asks it to find the law
it needs, cite it, or answer for a date.

**Portuguese law.** LegalBench.PT (Canaverde, Pires, Ribeiro and Martins, 2025) is the first
broad benchmark of Portuguese law: questions from real law exams, turned by GPT-4o into
multiple-choice, true or false and matching items, reviewed by people with legal training, and
compared with Portuguese lawyers on a sample. Lex differs in form and aim: its questions are the
ones the public asks public bodies (the ACT, the DGAJ, the Diário da República's Lexionário), in
their own words where they stand alone, answered in free text; each is asked about a date and
must cite the articles in force that day; and a system is scored on finding them in a versioned
corpus, on citing them, on refusing what the corpus does not answer, and on its answer judged
against a reference. For Brazilian Portuguese, benchmarks of legal classification and of
question answering over legislation and case law exist; their law is not Portugal's.

**Statutory retrieval and question answering.** BSARD (Louis and Spanakis, ACL 2022) has 1,100+
questions in French from Belgian citizens, labelled by jurists with the relevant articles among
22,600+ of Belgian law, and measures retrieval; LLeQA (Louis, van Dijck and Spanakis, AAAI 2024)
extends it to 1,868 questions with long-form answers rooted in the articles, answered by a
retrieve-then-read pipeline. They are the closest designs to Lex: real questions, statutory
articles as the evidence. Lex adds the date: its corpus holds every version of each article with
the days it was in force, and its temporal items ask about the law as it stood then. COLIEE's
statute law task (Japanese civil code, bar exam questions) measures article retrieval and
entailment.

**Questions whose answer depends on when.** SituatedQA (Zhang and Choi, EMNLP 2021) shows that a
sixth of open-domain questions have answers that depend on when or where they are asked, and that
systems trained on the past answer the present worse. Lex's `as_of` is that context made explicit
for law, and `version_right` checks that a cited article is the version in force on it.

**How often legal AI is wrong.** Magesh, Surani, Dahl, Suzgun, Manning and Ho (Journal of
Empirical Legal Studies, 2025) ran the first preregistered evaluation of commercial legal research
tools built on retrieval and found Lexis+ AI and Thomson Reuters' tools hallucinating between 17%
and 33% of the time, against their providers' claims. Lex starts from the same question for
Portugal, where, as far as we found, no AI assistant for the law publishes how often it is right.

### References

- Canaverde, B., Pires, T. P., Ribeiro, L. M., Martins, A. F. T. (2025). LegalBench.PT: A
  Benchmark for Portuguese Law. arXiv:2502.16357.
- Chalkidis, I., et al. (2022). LexGLUE: A Benchmark Dataset for Legal Language Understanding in
  English. ACL 2022. https://aclanthology.org/2022.acl-long.297
- Guha, N., et al. (2023). LegalBench: A Collaboratively Built Benchmark for Measuring Legal
  Reasoning in Large Language Models. NeurIPS 2023 Datasets and Benchmarks. arXiv:2308.11462.
- Louis, A., Spanakis, G. (2022). A Statutory Article Retrieval Dataset in French. ACL 2022.
  https://aclanthology.org/2022.acl-long.468
- Louis, A., van Dijck, G., Spanakis, G. (2024). Interpretable Long-Form Legal Question Answering
  with Retrieval-Augmented Large Language Models. AAAI 2024. arXiv:2309.17050.
- Magesh, V., Surani, F., Dahl, M., Suzgun, M., Manning, C. D., Ho, D. E. (2025).
  Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools. Journal of
  Empirical Legal Studies. arXiv:2405.20362.
- Zhang, M. J. Q., Choi, E. (2021). SituatedQA: Incorporating Extra-Linguistic Contexts into QA.
  EMNLP 2021. https://aclanthology.org/2021.emnlp-main.586
- COLIEE, the Competition on Legal Information Extraction and Entailment (annual), statute law
  retrieval and entailment tasks.

## The corpus

Lex answers from three acts in every version since a starting date: the Código do Trabalho (Lei
n.º 7/2009, 889 article versions since 2009), the Novo Regime do Arrendamento Urbano (Lei n.º
6/2006, 177 since 2006) and the Código Civil's articles on leases, 1022.º to 1113.º (DL n.º
47344/66, 147): 1,213 article versions, each with the dates it was in force and the diploma that
introduced it ([corpus/index.jsonl](../corpus/index.jsonl); fingerprint `70cec90c` in every run
below). The Diário da República is the reference; the consolidated text and each article's
history come from the PGDL, checked against the DR
([ADR 0005](decisions/0005-legislation-source.md)). Where neither gives a version's start, a rule
dates it (a date read from the diploma, a rectification's), and the spot check compares every
such version, and a random sample of the rest, with the DR's history view: of 65 labour checks, 56
agree, 8 are versions made by two rectifications that the store applies from the rectified text's
date while the DR's view lists them at publication, and 1 is open (art. 127.º, 2015 to 2017,
numbered one way by the PGDL and another by the DR) ([docs/checks/](checks/)). The DR's notes on a
version's effects (deferred, suspended, ruled unconstitutional) stay with the version and reach
the model ([ADR 0002](decisions/0002-article-versions.md), amended).

## The items and the splits

Benchmark v4 has 201 items: 76 `simple`, 37 `composite`, 27 `temporal`, 17 `explicit_reference`
and 44 `unanswerable`, 105 in dev and 96 in test, 43 of them on tenancy
([bench/README.md](../bench/README.md)). Each is a question taken from a public body's page, with
its URL, the date it is asked about, the article versions a right answer must cite (and may cite),
and a reference answer. No question is invented: a model drafted each item from its page and
checked it against the law in force on its date, and every dev item names that model in
`reviewed_by` ([CLAUDE.md](../CLAUDE.md)); none has yet been signed off by a legal reviewer.

An item's split is a hash of its group, never a choice: its main article, joined with every item
that must cite it or comes from the same FAQ entry
([ADR 0009](decisions/0009-split-by-main-article.md), amended). v3 had 13 test items in a group
with dev items; v4 moved them to dev, and a test item in such a group is now a fault. Dev is
public (the mirror and the Hugging Face dataset); test is not, so its scores keep their meaning
([ADR 0016](decisions/0016-licences-and-hidden-test.md)).

## Metrics and the judge

A system is scored on citation recall and precision against `must_cite` and `may_cite`, on
refusals, and on whether each cited version is the one in force on the item's date
(`version_right`: 1.00 for every system below). Correctness is judged by an LLM, Gemma 4 26B
A4B, which reads the question, the reference answer and the system's answer and says correct,
partial or wrong; a refusal of an answerable question is wrong
([bench/README.md](../bench/README.md#metrics)). The judge has no hand labels to agree with yet;
it is measured on known-answer cases built from dev ([ADR 0015](decisions/0015-answer-judge.md)):
on v4's dev it accepted 81 of 81 reference answers, caught 57 of 57 with a number changed or a
yes turned into a no, and judged none of 132 lenient cases correct (a contradicting sentence
appended, another question's answer), 129 as expected
([results/dev/judge-check.json](../results/dev/judge-check.json)). It judges at temperature 0: on
v3's dev, three samples agreed on all 67 answers judged, against 8 of 67 at the provider's default
([ADR 0011](decisions/0011-answer-llm.md), amended). What it does with ambiguous answers is not
measured.

## Systems

Four retrievers: BM25 (pg_search, Portuguese stemmer); BGE-M3 dense retrieval; BGE-M3 reranked by
bge-reranker-v2-m3 with a parser that puts an article the question names first (the reference
system, ADRs [0007](decisions/0007-embedding-model.md), [0010](decisions/0010-reranker.md) and
[0004](decisions/0004-explicit-references-first.md)); and Gemini Embedding 2 with the same parser (the
demo, [ADR 0014](decisions/0014-serverless-demo.md)). Three answer systems give the top 5 article
versions for the date to Gemini 3.1 Flash-Lite: the demo's agent prompt, a citation per sentence
with leave to ask for more articles ([ADR 0018](decisions/0018-agent.md)); the same retrieval
with the per-sentence prompt alone; and the reference retrieval with one answer and a list of
citations. In every system a citation of an article not given is dropped, and an answer left with
none becomes a refusal.

## Results on test

On v4's test split, 96 questions (76 answerable, 20 not), each system ran once, after its dev run
on the same configuration; the answers were asked from no cache, and each answer judged three
times (the samples agreed on all of them).

| Retrieval | recall@1 | recall@5 | recall@10 | run |
|---|---|---|---|---|
| BM25 | 0.52 | 0.71 | 0.76 | [bm25](../results/test/2026-10-09T1517-bm25.json) |
| BGE-M3 | 0.56 | 0.78 | 0.81 | [dense-bge-m3](../results/test/2026-10-09T1518-dense-bge-m3.json) |
| BGE-M3, reranker, parser | 0.75 | 0.90 | 0.94 | [reference](../results/test/2026-10-09T1533-dense-bge-m3+rerank+refs.json) |
| Gemini Embedding 2, parser | 0.81 | 0.97 | 1.00 | [demo](../results/test/2026-10-09T1533-dense-gemini-embedding-2+refs.json) |

| Answers | Correct | Partial | Wrong | Composite correct | Citation recall | Precision | Answerable refused | Unanswerable refused |
|---|---|---|---|---|---|---|---|---|
| [The demo's agent](../results/test/2026-10-09T1701-dense-gemini-embedding-2+refs+gemini-3.1-flash-lite+agent.json) | 0.70 | 0.29 | 0.01 | 0.38 | 0.92 | 0.90 | 1 of 76 | 19 of 20 |
| [A citation per sentence](../results/test/2026-10-09T1832-dense-gemini-embedding-2+refs+gemini-3.1-flash-lite+claims.json) | 0.71 | 0.28 | 0.01 | 0.31 | 0.93 | 0.91 | 1 of 76 | 17 of 20 |
| [Reference retrieval](../results/test/2026-10-09T2025-dense-bge-m3+rerank+refs+gemini-3.1-flash-lite.json) | 0.75 | 0.14 | 0.11 | 0.54 | 0.88 | 0.90 | 4 of 76 | 15 of 20 |

Compared item by item with an exact sign test (`python -m lex.eval compare`), no answer system
differs from another beyond the noise: the demo and the per-sentence prompt each get right 3 and
4 answers the other gets wrong (p = 1.00), the demo and the reference system 5 and 9 (p = 0.42).
The noise is large: two runs of the demo's system on v3's dev judged 50 of 68 correct both times,
with 8 verdicts changed, 4 each way ([results/dev/archive/v3/](../results/dev/archive/v3/)). The
articles the model is given hold 0.97 of what the demo should cite (0.90 for the reference
system), so most of what is lost is lost by the answer, not by retrieval; composite questions,
which combine several articles, are where it shows. At paid prices the demo's answer costs
$0.00103781 a question, the model's thinking and the question's embedding counted; the judge's
tokens are not priced, as Gemma 4 has no paid tier.

## Limits

- **The items were drafted and reviewed by a model**, and none has been signed off by a legal
  reviewer (0 of 201). A wrong reference answer or citation would score a right system down.
- **Contamination.** 74 of the 105 dev items come from the ACT's portal, and of the 60 drawn
  from its FAQ, 37 keep the ACT's question word for word
  ([bench/DATASET_CARD.md](../bench/DATASET_CARD.md)): a model may have read them with the ACT's
  answers. Test runs send test questions and reference answers to Google's API on its free tier,
  whose terms let Google use prompts to improve its products, a risk the project accepted on
  2026-10-09 ([ADR 0016](decisions/0016-licences-and-hidden-test.md), amended); every run records
  each endpoint's tier.
- **One source dominates**, one model family answers and one judge judges; the judge is checked on
  clear errors, not on hand labels.
- **Small numbers.** 76 answerable test questions: differences of a few items are within the
  noise measured above, and per-type numbers (13 composite questions) are smaller still.
- **The corpus is three acts**, with one open dating question (art. 127.º, 2015 to 2017).
