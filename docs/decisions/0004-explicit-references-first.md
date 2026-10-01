# 0004. Explicit article references are resolved before any search

Date: 2026-09-29
Status: accepted

## Context

People write "artigo 238.º do Código do Trabalho", "art. 238.º CT", "o n.º 2 do artigo 127.º".
Semantic search is bad at exact numbers, and keyword search can still rank a neighbouring article
or another diploma first. A reference that names its article has exactly one correct target.

## Decision

A parser finds article references in the question and resolves them straight from the store to
the version in force on `as_of`. Their text goes into the context first; search still runs for
the rest of the question. A bare article number with no diploma is resolved only while the corpus
has a single diploma, or when the question names one.

## Consequences

- `explicit_reference` items should reach near-perfect recall. When one doesn't, it is a parser bug
  with a failing test, not a tuning problem.
- The parser is tested against real phrasings kept in `tests/fixtures/`.
