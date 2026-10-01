"""The Phase 1 spot check: random earlier versions compared with the DR's own history.

For each version drawn, the DR's 'Versão à data de' view is opened on the version's first day
and on its last day in force. That view shows, per article, the latest version *published* by
the date, and states its period in force when it has one. So a check compares:
- the text the DR shows with the text of the store's version for that period, and
- where the DR states a period, its first and last day with the store's valid_from and valid_to.
On a version's last day the DR often shows the next version, published but not yet in force;
that checks the next version and the boundary between the two.

Earlier versions come from the PGDL, so the reference here is independent of them. What the check
shares with the build is the parser for the DR's page text.
"""

import datetime as dt
import difflib
import random
import re
from dataclasses import dataclass
from pathlib import Path

import psycopg

from lex.ingest import dr
from lex.ingest.build import normalise
from lex.store import db
from lex.store.models import ArticleVersion

DAY = dt.timedelta(days=1)


@dataclass(frozen=True)
class Check:
    article: str
    day: dt.date  # the date the DR page was set to
    stated: str  # the period the DR states for the version it shows, or "not stated"
    ours: str  # the store's version compared, as "valid_from to valid_to"
    result: str  # same, punctuation only, revoked on both, differs, dates differ, missing ...
    diff: str = ""


def _without_punctuation(text: str) -> str:
    return re.sub(r"[.,;:]", "", normalise(text))


def compare(ours: str, theirs: str) -> tuple[str, str]:
    """Result and diff of comparing two article texts, lenient only where it is safe."""
    if not theirs and re.match(r"^\(?\s*revogad", ours, re.I):
        return "revoked on both", ""
    if normalise(ours) == normalise(theirs):
        return "same", ""
    diff = "\n".join(
        difflib.unified_diff(
            ours.splitlines(), theirs.splitlines(), "store", "DR", n=0, lineterm=""
        )
    )
    if _without_punctuation(ours) == _without_punctuation(theirs):
        return "punctuation only", diff
    return "differs", diff


def _span(start: dt.date | None, end: dt.date | None) -> str:
    return f"{start or '...'} to {end or 'in force'}"


def check_one(
    conn: psycopg.Connection, diploma: str, article: str, day: dt.date, theirs: dr.Article | None
) -> Check:
    if theirs is None:
        return Check(article, day, "-", "-", "missing from the DR")
    start, last = theirs.window or (None, None)
    stated = _span(start, last) if theirs.window else "not stated"
    ours = db.article_at(conn, diploma, article, start or day)
    if ours is None:
        return Check(article, day, stated, "-", "missing from the store")
    span = _span(ours.valid_from, ours.valid_to)
    # The DR states the last day in force; the store keeps the first day out of force.
    if (start and ours.valid_from != start) or (last and ours.valid_to != last + DAY):
        return Check(article, day, stated, span, "dates differ")
    result, diff = compare(ours.text, theirs.text)
    return Check(article, day, stated, span, result, diff)


def run(
    versions: list[ArticleVersion],
    n: int,
    seed: int,
    raw_dir: Path,
    conn: psycopg.Connection,
    *,
    offline: bool = False,
) -> tuple[list[Check], int]:
    """Check n random earlier versions. Returns the checks and how many versions were drawn from."""
    older = [v for v in versions if v.valid_to is not None]
    picked = sorted(random.Random(seed).sample(older, n), key=lambda v: (v.valid_from, v.article))
    plan = [(v, d) for v in picked if v.valid_to for d in (v.valid_from, v.valid_to - DAY)]
    pages: dict[dt.date, dict[str, dr.Article]] = {}
    for day in sorted({d for _, d in plan}):
        print(f"  DR as of {day}", flush=True)
        text, _ = dr.cached_render(
            dr.CT_URL, raw_dir / f"ct_as_of_{day}.txt", as_of=day, offline=offline
        )
        pages[day] = dr.parse_code(text)
    checks = [check_one(conn, v.diploma, v.article, d, pages[d].get(v.article)) for v, d in plan]
    return checks, len(older)


def report(checks: list[Check], n: int, seed: int, drawn_from: int) -> str:
    counts: dict[str, int] = {}
    for c in checks:
        counts[c.result] = counts.get(c.result, 0) + 1
    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    rows = [f"| {c.article} | {c.day} | {c.stated} | {c.ours} | {c.result} |" for c in checks]
    notes = [
        f"### {c.article}, DR as of {c.day}: {c.result}\n\n```diff\n{c.diff}\n```"
        for c in checks
        if c.diff
    ]
    return (
        f"# Phase 1 spot check: {n} earlier article versions\n\n"
        f"Produced by `python -m lex.ingest spot-check {n} --seed {seed}`: {n} versions drawn at\n"
        f"random from the {drawn_from} earlier (no longer in force) versions in the store, each\n"
        "checked against the DR's *Versão à data de* view on its first and its last day in force.\n"
        "How the check works, and what it shares with the build, is in\n"
        "`src/lex/ingest/spot_check.py`. It is automated rather than done by hand.\n\n"
        "*DR states* is the period in force the DR gives for the version it shows (first to last\n"
        "day). *Store version* is the version it was compared with (first day in force to first\n"
        "day out of force). Texts are compared after collapsing whitespace, dashes and the ways\n"
        "of writing '(Revogado.)'.\n\n"
        f"**Result: {summary}** ({len(checks)} checks).\n\n"
        "| Article | DR as of | DR states in force | Store version | Result |\n"
        "|---|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n\n## Differences\n\n"
        + ("\n\n".join(notes) if notes else "None.")
        + "\n"
    )
