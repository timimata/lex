# 0002. Article versions are the unit of storage and retrieval

Date: 2026-09-29
Status: accepted

## Context

Portuguese codes change often. The Código do Trabalho has been amended many times since 2009,
including by the Agenda do Trabalho Digno (Lei n.º 13/2023). A question about a dismissal in 2021
needs the text that was in force in 2021. Lia answers from legislation currently in force only.

Chunking by character count cuts articles in half and loses which article a passage came from,
which makes exact citation impossible.

## Decision

- Store diplomas, articles and article versions. A version has its text, `valid_from`, `valid_to`
  (empty while in force), the diploma(s) that introduced it, the source URL and the fetch date.
  A revoked article is a version whose text records the revocation.
- One article version is one retrieval unit. An article too long for the embedding model is split
  by número, and each piece carries the article header: diploma, article number, epígrafe, and
  its place in the code's structure.
- Every query has an `as_of` date (default today) and sees only the versions in force on it.

## Consequences

- Temporal questions become answerable and testable, and every answer can say which version it
  used.
- Ingestion is harder: we need each article's history, not just today's text. How the DR exposes
  that history is the first task of Phase 1 (ADR 0005). If it can't be obtained reliably, this
  ADR is revisited before any `temporal` item enters the benchmark.

## Known limitation, found 2026-09-29

`valid_from` is when a text *entered into force*, which is what the DR records. A diploma can
defer when a rule *produces effects*, or keep the old rule for existing situations, in its own
transitional articles. Example: Lei n.º 23/2012 changed article 234.º (public holidays) from
2012-08-01, but its art. 10.º says the removal of four holidays "produz efeitos a partir de 1 de
janeiro de 2013". The store says 5 October 2012 was not a holiday; in practice it was.

Until this is modelled, every `temporal` benchmark item is checked against the amending
diploma's transitional and effects provisions, not just the article text, and an item whose
answer depends on such a provision says so in `notes`. Its answer is the law, not what the store
can represent (bench/README.md, rule 6), so the limitation shows up as measured failures rather
than being hidden. Modelling it (an effects date per
version, or transitional provisions as retrievable text of their own) is a decision for when
the first such items are written.
