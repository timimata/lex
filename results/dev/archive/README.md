# Dev runs kept for their history

Runs from before splits were versioned (before 2026-10-01, with no `bench` key) or made on an
earlier version of dev (benchmark v2), moved here on 2026-10-08 (ROADMAP, Phase 10). The roadmap
and the ADRs cite them for what was measured then; `python -m lex.eval check-results` reads none
of them, and none is a current number. `git log --follow` gives each one's history.

Also here: the judge's runs at the provider's default temperature (`*-provider.json`), kept
when the judge moved to temperature 0 on 2026-10-08 ([ADR 0011](../../../docs/decisions/0011-answer-llm.md), amended).

`v3/`: the dev runs of benchmark v3, moved here on 2026-10-09 when the re-split made v4 (ADR 0009,
amended); `results/test/v3/` holds that version's test runs.
