# Lex

An open benchmark for question answering over Portuguese legislation (PT-PT), plus an open-source
reference system measured against it. The benchmark is the product; the system exists to be
measured on it. Why: [docs/decisions/0001-benchmark-first.md](docs/decisions/0001-benchmark-first.md).

The current phase and its exit criteria are in [docs/ROADMAP.md](docs/ROADMAP.md). Don't build
ahead of the current phase. Reply to Tiago in European Portuguese.

## Rules that are never broken

### Evaluation integrity
- `bench/data/test.jsonl` is read by the eval harness and nothing else. Don't open it, print it,
  quote it, or tune anything against it (prompts, chunking, k, thresholds, model choice). All
  development happens on `dev`. The same goes for `.cache/llm/test/`, the LLM cache of test
  runs, whose prompts contain test questions.
- No copy of a test item exists outside `test.jsonl`: drafts are deleted after `assign`, and
  review sheets keep test items as ids (`lex.bench.splits.split_for` tells which).
- Nobody picks an item's split. It is a hash of the item's main article, its first `must_cite`
  (or of its id if it cites nothing), so items about the same article share a split and a dev
  item never gives away a test answer ([ADR 0009](docs/decisions/0009-split-by-main-article.md)).
  New items go to `incoming.jsonl` and `python -m lex.bench assign` moves them.
- Questions are never invented, by a person or an LLM. Every item comes from a public source with
  a URL. Synthetic questions (e.g. for fine-tuning) live outside `bench/` and never enter it.
- Every item names who reviewed it in `reviewed_by`. Never write a person's name there for a
  review a model did.
- The test split is run at milestones only. Every run is saved in `results/` with commit hash,
  config, model ids, date and cost. A number that isn't in `results/` doesn't go in the README,
  the demo or the CV.
- No illustrative, estimated or rounded-up numbers anywhere. If it wasn't measured, write
  "not measured yet".
- An LLM judge's scores are reported only next to how the judge was measured on dev: its
  agreement with hand labels, or, while there are none, the known-answer checks it must pass
  first ([ADR 0015](docs/decisions/0015-answer-judge.md)).

### Legal content
- Every claim in a system answer cites an article version retrieved for that answer. No citation,
  no claim.
- When retrieval finds no support, the system says so instead of answering. For `unanswerable`
  items, refusing is the correct answer and is scored as one.
- Every answer is for a date (`as_of`, default today) and says which version of each article it
  used.
- Every user-facing surface says that consolidated texts have no legal value and that Lex is not
  legal advice.

### Data and sources
- Legislation comes from public-body sources only. The DR (diariodarepublica.pt) is the
  reference; the PGDL (pgdlisboa.pt) is where consolidated text and article history are fetched,
  checked against the DR ([ADR 0005](docs/decisions/0005-legislation-source.md)). Before any
  scraper is written, the source's terms of use and robots.txt are checked and recorded in an ADR.
- Fetching is polite: one request at a time, at least 1 s apart, a descriptive User-Agent, and
  every raw response cached under `data/raw/` so nothing is downloaded twice.
- Every article version keeps its provenance: source URL, fetch date, and the diploma(s) that
  introduced it.
- No personal data in the benchmark. A question drawn from a real case is rewritten generically.
- `data/` is not committed. Anything in it can be rebuilt by a script.

## Engineering conventions
- Python >= 3.12, src layout, package `lex`. `pyproject.toml` holds all tool config.
- ruff (lint + format), mypy strict on `src/`, pytest. All pass before a commit; CI runs them.
- Pydantic models for anything that crosses a boundary: bench items, answers, API payloads.
  Types shared across modules live in `src/lex/domain.py`.
- The eval harness talks to systems only through the `System` and `Retriever` protocols in
  `domain.py`. Baselines, the reference system and hand-scored external tools implement them.
- Imports flow one way: `ingest -> store`, `retrieval -> store`, `generation -> retrieval`,
  `api -> generation`. `bench` imports only `domain`; `eval` imports only `domain` and `bench`.
  Building concrete systems and handing them to the harness happens in `__main__` modules, and
  in `mcp_server.py` and `vercel/index.py`, which are wiring too.
- No orchestration frameworks (LangChain, LlamaIndex) in retrieval or generation; write the few
  lines. LangGraph is allowed in the agent phase only, and only if the benchmark shows it helps.
- A dependency is added when code needs it, pinned to an exact version, with a comment saying why.
- LLM calls made during eval go through a disk cache keyed on (model, prompt, params), so re-runs
  are free and reproducible. Seeds are fixed.
- Secrets live in `.env` (never committed); `.env.example` lists every variable.
- Parsers (reference parser, article splitter, version resolver) are tested against real text
  saved in `tests/fixtures/`.

## Workflow
- A phase is done when its exit criteria are met, not when its code exists.
- A decision that is hard to reverse, or that someone could reasonably ask "why?" about (store,
  embedding model, chunking, scraping approach, licence), gets an ADR in `docs/decisions/` from
  `0000-template.md`. Short is fine. Read the relevant ADRs before changing what they decided.
- Commit messages are plain English, imperative, and say what changed and what it measured, e.g.
  "Add the reranker: dev recall@5 0.72 -> 0.81". No prefixes.
- A change to retrieval, generation or prompts states its dev metric delta in the commit message.
- Code, docs and commits in English. Benchmark questions and answers in European Portuguese.

## Commands
```bash
pip install -e ".[dev,llm,api]"   # add ingest and dense for fetching and the real models
ruff check . && ruff format --check .
mypy
pytest
python -m lex.bench validate    # schema, split and duplicate checks; prints counts only
python -m lex.bench assign      # moves incoming.jsonl items to their split
python -m lex.bench snapshot    # the public mirror: every tracked file but test (ADR 0016)
cd build/public && git add -A && git commit -m "Lex: snapshot of private commit <sha>" && git push
hf upload timimata/lex build/hf . --repo-type dataset   # the dev split, after a snapshot
python -m lex.ingest ct --offline   # rebuild article versions from data/raw (no network)
python -m lex.ingest code nrau --offline   # or cc: tenancy (ADR 0017); codes.py lists them
docker compose up -d --wait         # the store; tests that need it skip without it
python -m lex.store load            # replace the store's contents with the ingestion output
python -m lex.store show 238 --as-of 2011-06-01
python -m lex.ingest spot-check 20 --offline   # versions vs the DR's history view; --code KEY
python -m lex.eval retrieval bm25   # dev by default; --split test only at milestones
python -m lex.eval answers          # the reference system on dev; needs LLM_API_KEY in .env
python -m lex.api                   # the reference system over HTTP, on 127.0.0.1:8000
python -m lex.api --demo            # the deployed demo's system (ADR 0014), no Postgres
python -m lex.eval label SYSTEM     # hand-label a system's dev answers (a person, never a model)
python -m lex.eval judge SYSTEM     # judge dev answers, measure agreement with the labels
python -m lex.eval judge-check      # or measure the judge on known-answer dev cases
python -m lex.eval check-results    # results/ adds up and test runs share a split (CI runs it)
python -m lex.eval latency URL      # time the deployed demo; spends its quota
python -m lex.eval regress          # the demo's system on dev against its committed run
python -m lex.probe URL             # the deployed demo from outside; no quota (CI, every 6 h)
python -m lex.mcp_server            # the code as MCP tools, over stdio
python web/e2e.py                   # the page in Chromium, scripted answers, no quota
python vercel/assemble.py && cd build/vercel && npx vercel deploy --prod   # deploy the demo
```
On Windows, connect to 127.0.0.1, not localhost (see `src/lex/store/db.py`).
