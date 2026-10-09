# Contributing to Lex

Lex is a benchmark first ([ADR 0001](docs/decisions/0001-benchmark-first.md)): the most useful
contributions are questions, corrections to items, and systems to measure. Code is welcome too.
The rules every contribution keeps are in [CLAUDE.md](CLAUDE.md) and
[bench/README.md](bench/README.md); the work under way is in [docs/ROADMAP.md](docs/ROADMAP.md).

## Report an error in an item

Open an issue with the "An item is wrong" template: the item's id, what is wrong (the answer, an
article to cite, the date), and the article and version of the law that shows it. Only dev items
are public; for a test item, say what you found without quoting it, and the maintainer will look.
A fix changes the item and nothing else, one commit per fix, saying why (bench/README.md, rule 5).

## Propose questions

Every item comes from a public page with a URL, never invented by a person or a model
(bench/README.md, "Writing rules"): the ACT's guidance, the DGAJ's pages, the Diário da
República's Lexionário, other public bodies' legal information whose terms allow reuse under
CC BY 4.0. An item names its main article first in `must_cite`, is checked against the law in
force on its `as_of`, and says in `reviewed_by` who checked it. Propose items in an issue or a
pull request that adds them to `bench/data/incoming.jsonl`; the maintainer runs
`python -m lex.bench validate` and `assign`, which decide the split. Nobody picks a split.

## Have a system scored

On dev, anyone can: answer each dev question, write the answers to a file and score it, judged
or not:

```bash
python -m lex.eval answers --from answers.jsonl --judge   # one line per dev item
```

Each line holds `id`, `text`, `refused`, and `citations`, each with `diploma`, `article` and the
`valid_from` of the version cited (bench/README.md, "Metrics"). On test, whose items stay private
([ADR 0016](docs/decisions/0016-licences-and-hidden-test.md)), open an issue with the "Score my
system on test" template. The maintainer runs your system, through an endpoint with the
`/api/answer` contract or your code, and publishes the numbers. Your endpoint receives the test
questions: say in the issue that you will neither keep nor train on them.

## Change the code

```bash
uv sync --locked --extra dev --extra llm --extra api
ruff check . && ruff format --check . && mypy && pytest
python -m lex.bench validate && python -m lex.eval check-results
```

A change to retrieval, generation or a prompt comes with a dev run, and its commit message says
what the run measured. A decision someone could ask "why?" about gets an ADR from
`docs/decisions/0000-template.md`. Code, docs and commits in English; benchmark questions and
answers in European Portuguese.

## Security

See [SECURITY.md](SECURITY.md).
