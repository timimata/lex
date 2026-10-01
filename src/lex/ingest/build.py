"""Joining the two sources into article versions, and checking each against the other.

The current text of every article, its place in the code, and the entry-into-force date of each
change come from the DR, the official source. Earlier versions come from the PGDL. For every
article, both sources must name the same amending diplomas, and the PGDL's current text is
compared with the DR's as a measure of how far the PGDL can be trusted for the older ones.

A version's start date is resolved in this order, and anything but the first is logged:
1. the DR's note on that article for the diploma that introduced the version;
2. READ_FROM_DIPLOMA, dates read by hand from a diploma's own entry-into-force article, for
   diplomas that start on different dates for different articles;
3. for a rectification, the date of the diploma it rectifies: "as declarações de retificação
   reportam os efeitos à data da entrada em vigor do texto retificado" (Lei n.º 74/98, art. 5.º,
   n.º 4);
4. the date the DR gives that diploma on every other article, if it is always the same one.
Nothing else is guessed: a version whose date can't be resolved is reported, not stored.
"""

import datetime as dt
import re
from collections import defaultdict
from dataclasses import dataclass, field

from lex.ingest import dr, pgdl
from lex.ingest.fetch import Page
from lex.ingest.labels import diploma_id
from lex.store.models import ArticleVersion

CT = "lei-7-2009"
# The code's own entry into force, as the DR dates the Declaração de Rectificação n.º 21/2009.
CT_IN_FORCE = dt.date(2009, 2, 17)
# Which diploma each rectification corrects, as the DR's list of amending acts describes them.
RECTIFIES = {
    "retificacao-21-2009": CT,
    "retificacao-28-2017": "lei-73-2017",
    "retificacao-13-2023": "lei-13-2023",
}
# (diploma, article) -> entry into force, where the DR's note on the article has no date.
READ_FROM_DIPLOMA: dict[tuple[str, str], dt.date] = {
    # Lei n.º 90/2019, art. 9.º, n.º 1, as rectified by Retificação n.º 48/2019: "com o Orçamento
    # do Estado posterior à sua publicação", i.e. Lei n.º 2/2020, published 2020-03-31 and in
    # force the next day (its art. 430.º).
    **{
        ("lei-90-2019", article): dt.date(2020, 4, 1)
        for article in ("35", "37-A", "40", "42", "43", "53", "65", "94")
    },
    # Lei n.º 90/2019, art. 9.º, n.º 2: "30 dias após a publicação", published 2019-09-04.
    **{("lei-90-2019", article): dt.date(2019, 10, 4) for article in ("33-A", "252-A")},
}


@dataclass
class Report:
    articles: int = 0
    versions: int = 0
    problems: list[str] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)  # dates found by rules 2 or 3
    incomplete_history: list[str] = field(default_factory=list)  # articles; no temporal items
    missing_current: list[str] = field(default_factory=list)  # articles with no version stored
    text_mismatches: list[str] = field(default_factory=list)
    rulings: dict[str, list[str]] = field(default_factory=dict)


def normalise(text: str) -> str:
    text = text.replace(chr(0x2013), "-")  # en dash
    text = re.sub(r"[(\[]\s*(Revogad[oa])\s*\.?\s*[)\]]\.?", r"(\1.)", text)
    return " ".join(text.split())


def _unanimous_dates(reference: dict[str, dr.Article]) -> dict[str, dt.date]:
    dates: dict[str, set[dt.date]] = defaultdict(set)
    for article in reference.values():
        for note in article.notes:
            if note.in_force is not None:
                dates[note.diploma].add(note.in_force)
    return {diploma: next(iter(d)) for diploma, d in dates.items() if len(d) == 1}


def build(
    current: dict[str, tuple[pgdl.Article, Page]],
    old: dict[tuple[str, int], tuple[pgdl.OldVersion, Page]],
    reference: dict[str, dr.Article],
    reference_fetched: dt.date,
) -> tuple[list[ArticleVersion], Report]:
    versions: list[ArticleVersion] = []
    report = Report(articles=len(current))
    by_diploma = _unanimous_dates(reference)

    for article_id, (article, page) in current.items():
        number = pgdl.article_number(article_id)
        ref = reference.get(number)
        if ref is None:
            report.problems.append(f"{number}: not on the DR page")
            continue
        if ref.rulings:
            report.rulings[number] = list(ref.rulings)
        notes = {note.diploma: note.in_force for note in ref.notes}
        chain = [old[(article_id, r.number)] for r in sorted(article.old_versions, key=_number)]
        latest = article.amended_by[-1] if article.amended_by else article.added_by
        latest_by = diploma_id(latest) if latest else CT

        pgdl_diplomas = {diploma_id(label) for label in article.amended_by}
        pgdl_diplomas |= {diploma_id(v.introduced_by) for v, _ in chain}
        if article.added_by:
            pgdl_diplomas.add(diploma_id(article.added_by))
        comparable = {d for d in pgdl_diplomas if d != CT and not d.startswith("retificacao")}
        on_dr = {d for d in notes if not d.startswith("retificacao")}
        if comparable != on_dr:
            report.problems.append(
                f"{number}: amended by {sorted(comparable)} on the PGDL, {sorted(on_dr)} on the DR"
            )
        if ref.text and normalise(article.text) != normalise(ref.text):
            report.text_mismatches.append(number)

        # (heading, text, introduced_by, source url, fetched), oldest first. The current text is
        # the DR's; a revoked article has none there, so the PGDL's is kept.
        steps = [
            (v.heading, v.text, diploma_id(v.introduced_by), p.url, p.fetched) for v, p in chain
        ]
        if ref.text:
            steps.append((ref.heading, ref.text, latest_by, dr.CT_URL, reference_fetched))
        else:
            steps.append((article.heading, article.text, latest_by, page.url, page.fetched))

        # A version without a start date also leaves the one before it without an end, so only
        # the versions after the last undated one are kept. The article's history is then
        # incomplete, and it is listed so no temporal item relies on it.
        dated: list[tuple[dt.date, str, str, str, str, dt.date]] = []
        for heading, text, by, source_url, fetched in steps:
            start = _start_of(by, number, notes, by_diploma, report.resolved)
            if start is None:
                report.problems.append(f"{number}: no entry-into-force date for {by}")
                report.incomplete_history.append(number)
                dated = []
            else:
                dated.append((start, heading, text, by, source_url, fetched))
        if not dated:
            report.missing_current.append(number)
            continue

        starts = [d[0] for d in dated]
        if starts != sorted(starts):
            report.problems.append(f"{number}: versions out of date order {starts}")
            continue
        for n, (start, heading, text, by, source_url, fetched) in enumerate(dated):
            end = dated[n + 1][0] if n + 1 < len(dated) else None
            if end is not None and end <= start:
                continue  # replaced the day it started, e.g. by a rectification
            versions.append(
                ArticleVersion(
                    diploma=CT,
                    article=number,
                    heading=heading,
                    path=list(ref.path),
                    text=text,
                    valid_from=start,
                    valid_to=end,
                    introduced_by=by,
                    source_url=source_url,
                    fetched=fetched,
                )
            )
    report.versions = len(versions)
    return versions, report


def _start_of(
    by: str,
    article: str,
    notes: dict[str, dt.date | None],
    by_diploma: dict[str, dt.date],
    resolved: list[str],
) -> dt.date | None:
    """When the version of `article` introduced by `by` entered into force (rules in the module
    docstring)."""
    if by == CT:
        return CT_IN_FORCE
    noted = notes.get(by)
    if noted is not None:
        return noted
    if (by, article) in READ_FROM_DIPLOMA:
        start: dt.date | None = READ_FROM_DIPLOMA[(by, article)]
        rule = "read from the diploma's entry-into-force article"
    elif by in RECTIFIES:
        start = _start_of(RECTIFIES[by], article, notes, by_diploma, resolved)
        rule = f"as {RECTIFIES[by]}, which it rectifies"
    else:
        start = by_diploma.get(by)
        rule = "the DR's date for it on every other article"
    if start is not None:
        resolved.append(f"{article}: {by} dated {start}, {rule}")
    return start


def _number(ref: pgdl.OldVersionRef) -> int:
    return ref.number
