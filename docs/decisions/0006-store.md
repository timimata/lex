# 0006. Postgres with pg_search and pgvector, in the ParadeDB image

Date: 2026-09-29
Status: accepted; amended 2026-10-08 (every diploma; the demo holds none of it)

## Context

The store holds article versions (ADR 0002) and, from Phase 2, the indexes searched over them:
lexical search, which should be real BM25 rather than a rough ranking, and dense vectors.
Postgres' built-in full-text search ranks with `ts_rank`, which is not BM25. pgvector covers
vectors.

The ParadeDB image is Postgres with both pg_search (BM25, built on Tantivy) and pgvector
installed. Checked on 2026-09-29 with `paradedb/paradedb:0.25.11-pg18`
(digest `sha256:a9cbdcfd8a1c...`): PostgreSQL 18.6, pg_search 0.25.11, pgvector 0.8.4.

A smoke test loaded the 601 current articles into a table with a BM25 index using the Portuguese
stemmer (`body::pdb.simple('stemmer=portuguese')`). "férias" ranked articles 237.º, 238.º and
240.º first; "despedimentos", in the plural, found articles whose text says "despedimento";
"teletrabalho" ranked 166.º, 166.º-A and 167.º first.

The corpus is small (889 versions now, a few thousand after Phase 6), so any of these runs on a
laptop. What matters more is that lexical and dense search, the date filter and the data live in
one place and can be combined in one SQL query.

## Decision

- Postgres from the ParadeDB image, pinned to `paradedb/paradedb:0.25.11-pg18`, run locally with
  `docker compose`, and as a service container in CI.
- One table, `article_versions`, mirroring `lex.store.models.ArticleVersion`. An exclusion
  constraint (btree_gist over `daterange(valid_from, valid_to)`) makes it impossible for two
  versions of the same article to overlap in time.
- Loading replaces the table's contents from `data/processed/ct/versions.jsonl` in one
  transaction, so the store is always a rebuild of the ingestion output, never edited by hand.
- The BM25 and vector indexes are added in Phase 2, with the baselines that use them.

## Consequences

- Hybrid search (BM25 + vectors + `as_of` filter) is one query, with no second system to sync.
- pg_search's query syntax has changed between versions, hence the exact pin. Upgrading is a
  deliberate change, re-run against the benchmark.
- The image is about 1.4 GB, which CI pulls on every run.
- Hosting for the public demo (Phase 4) needs a Postgres provider that offers pg_search, or the
  demo runs this same image; decided in Phase 4.

## Amendment, 2026-10-08: every diploma, and a demo without Postgres

`python -m lex.store load` replaces the table's contents with every diploma's versions
(`codes.py` lists them), not the Código do Trabalho's alone. The public demo runs no Postgres
([ADR 0014](0014-serverless-demo.md)): it holds the corpus in memory, which since 2026-10-08
refuses what this store's constraints refuse (`Corpus.check`) and fingerprints the corpus as this
store does (`lex.domain.corpus_fingerprint`). This store remains the reference system's and the
baselines'.
