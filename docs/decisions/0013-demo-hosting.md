# 0013. The public demo: one Docker Space on Hugging Face, without the reranker

Date: 2026-09-30
Status: superseded by [0014](0014-serverless-demo.md) for hosting and the demo's system: Hugging
Face now requires PRO for Docker Spaces

## Context

Phase 4 puts the reference system on a public URL, with a leaderboard built from `results/`.
Tiago chose Hugging Face Spaces: free, public and familiar to people hiring for AI roles. A free
Space has 2 vCPUs and 16 GB of RAM, and sleeps when nobody uses it for a while.

On this PC the reranker takes about 13 seconds a question on CPU; a 2 vCPU Space would take
longer. On dev, answers without it lose a little (Gemini, top 5: citation recall 0.91 -> 0.89,
precision 0.95 -> 0.92, 6 -> 5 of 6 unanswerable refused; commit 6d8195f).

The demo shows article texts to anyone. The Código do Direito de Autor, art. 8.º, says the texts
of laws gathered in a compilation (art. 3.º, n.º 1, c)) are not protected; only the compilation
as such can be. The demo shows articles' text, not the DR's or the PGDL's arrangement or notes.
Lei n.º 26/2016 allows reusing documents public bodies publish online (ADR 0005). The legal review
of Phase 6 is to confirm both.

## Decision

- One Docker Space runs everything: Postgres with pg_search and pgvector (the ParadeDB image the
  store already uses, ADR 0006), the API and the web page. The demo runs the measured code, not
  a copy of it.
- The demo's system is dense retrieval with the reference parser and Gemini 3.1 Flash-Lite, top
  5, without the reranker. Its dev and test numbers go on the leaderboard next to the reference
  system's, and the page says which one it runs.
- The image carries the article versions and their BGE-M3 embeddings, so the Space starts
  without fetching or embedding anything, and the model weights at their pinned revisions. It
  carries no benchmark item: the leaderboard reads the summaries in `results/test/`.
- The Gemini key is a Space secret. The API limits answers per visitor and per day, and repeats
  a cached answer for a repeated question, so the free tier's quota is the budget cap: past it,
  the demo says it is out of answers for the day instead of costing anything.
- The web page is React, built into static files the API serves, with the disclaimer on every
  view.

## Consequences

- A visitor gets the system as measured, minus one step whose cost is on the leaderboard.
- The Space's files are public, so the code is too; the repo's licence is still open (roadmap).
- A cold Space takes a minute or more to start Postgres and load the models; not measured yet.
- If the Space's CPU turns out fast enough for the reranker, it goes back in, with the
  leaderboard showing the change.
