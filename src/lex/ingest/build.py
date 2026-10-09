"""Joining the two sources into article versions, and checking each against the other.

The current text of every article, its place in the code, and the entry-into-force date of each
change come from the DR, the official source. Earlier versions come from the PGDL. For every
article, both sources must name the same amending diplomas, and the PGDL's current text is
compared with the DR's as a measure of how far the PGDL can be trusted for the older ones.

Where they name different diplomas, two cases have been seen. The PGDL may credit a text to the
act that republished the whole diploma rather than to the one that changed the article (the
NRAU's texts of 2012, credited to Lei n.º 79/2014): if it has as many texts as the DR lists
changes, its texts are taken in order as those changes. Or the PGDL may lack a change, such as
the Código Civil's revocation of its articles 1064.º to 1082.º in 1975, whose text it does not
show: then its most recent texts are kept as long as they match the DR's most recent changes,
one for one, and the older ones are dropped, since the text before a missing change would
otherwise be stretched over it. A rectification the PGDL folds into the text it rectifies is
not a missing change. Either way the article is logged, and in the second its history is marked
incomplete.

A version's start date is resolved in this order, and anything but the DR's note is logged:
0. a correction (codes.py), where the DR's own note is wrong, with the reason;
1. the DR's note on that article for the diploma that introduced the version, or, for the
   diploma's own first text, its entry into force;
2. read_from_diploma (codes.py), dates read by hand from a diploma's own entry-into-force
   article, for diplomas that start on different dates for different articles;
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
from lex.ingest.codes import CT as CT_CODE
from lex.ingest.codes import Code
from lex.ingest.fetch import Page
from lex.ingest.labels import diploma_id
from lex.store.models import ArticleVersion

CT_IN_FORCE = CT_CODE.in_force


@dataclass
class Report:
    articles: int = 0
    versions: int = 0
    problems: list[str] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)  # dates found by rules 2 or 3
    # Articles whose PGDL texts were credited, in order, to the DR's list of changes.
    relabelled: list[str] = field(default_factory=list)
    # Articles where the PGDL lacks a change the DR lists: only the texts after it are kept.
    gaps: list[str] = field(default_factory=list)
    incomplete_history: list[str] = field(default_factory=list)  # articles; no temporal items
    missing_current: list[str] = field(default_factory=list)  # articles with no version stored
    text_mismatches: list[str] = field(default_factory=list)
    rulings: dict[str, list[str]] = field(default_factory=dict)
    # A date read by hand from a diploma that the DR's note for the same article contradicts: the
    # note's is stored, and the build is refused until a correction (codes.py) says which holds.
    disagreements: list[str] = field(default_factory=list)
    # Articles whose effects another diploma defers or suspends, in part or whole: their
    # versions start when the DR says the change entered into force, so these are listed.
    remarks: dict[str, list[str]] = field(default_factory=dict)


def normalise(text: str) -> str:
    text = text.replace(chr(0x2013), "-")  # en dash
    text = re.sub(r"[(\[]\s*(Revogad[oa])\s*\.?\s*[)\]]\.?", r"(\1.)", text)
    return " ".join(text.split())


def _changes(ref: dr.Article, code: Code) -> list[str]:
    """Who gave the article each of its texts, oldest first, by the DR's notes, which the page
    lists newest first: the diploma itself, unless an act added the article, then each act that
    changed, rectified or revoked it."""
    authors = [] if any(note.kind == "aditado" for note in ref.notes) else [code.diploma]
    for note in reversed(ref.notes):
        if not authors or authors[-1] != note.diploma:
            authors.append(note.diploma)
    return authors


def _matching_tail(authors: list[str], changes: list[str]) -> int:
    """How many of the most recent texts the two lists credit to the same acts, one for one."""
    n = 0
    while n < min(len(authors), len(changes)) and authors[-1 - n] == changes[-1 - n]:
        n += 1
    return n


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
    code: Code = CT_CODE,
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
        if ref.remarks:
            report.remarks[number] = list(ref.remarks)
        notes = {note.diploma: note.in_force for note in ref.notes}
        chain = [old[(article_id, r.number)] for r in sorted(article.old_versions, key=_number)]
        latest = article.amended_by[-1] if article.amended_by else article.added_by
        latest_by = diploma_id(latest) if latest else code.diploma

        pgdl_diplomas = {diploma_id(label) for label in article.amended_by}
        pgdl_diplomas |= {diploma_id(v.introduced_by) for v, _ in chain}
        if article.added_by:
            pgdl_diplomas.add(diploma_id(article.added_by))
        comparable = {
            d for d in pgdl_diplomas if d != code.diploma and not d.startswith("retificacao")
        }
        on_dr = {d for d in notes if not d.startswith("retificacao")}
        # Who gave the article each of its texts, oldest first, the current one last.
        authors = [diploma_id(v.introduced_by) for v, _ in chain] + [latest_by]
        if comparable != on_dr:
            changes = _changes(ref, code)
            # A rectification the PGDL folds into the text it rectifies is not a missing change.
            folded = [c for c in changes if not c.startswith("retificacao") or c in authors]
            if len(changes) == len(authors):
                report.relabelled.append(f"{number}: {authors} on the PGDL, {changes} on the DR")
                authors = changes
            elif tail := _matching_tail(authors, folded):
                report.gaps.append(
                    f"{number}: {authors} on the PGDL, {changes} on the DR; the {tail} most"
                    " recent texts kept"
                )
                report.incomplete_history.append(number)
                chain, authors = chain[len(chain) + 1 - tail :], authors[-tail:]
            else:
                report.problems.append(
                    f"{number}: amended by {sorted(comparable)} on the PGDL, {sorted(on_dr)} on "
                    "the DR; only the current text is kept"
                )
                report.incomplete_history.append(number)
                chain, authors = [], changes[-1:]
        if ref.text and normalise(article.text) != normalise(ref.text):
            report.text_mismatches.append(number)

        # (heading, text, introduced_by, source url, fetched), oldest first. The current text is
        # the DR's; a revoked article has none there, so the PGDL's is kept.
        steps = [
            (v.heading, v.text, by, p.url, p.fetched)
            for (v, p), by in zip(chain, authors[:-1], strict=True)
        ]
        if ref.text:
            steps.append((ref.heading, ref.text, authors[-1], code.dr_url, reference_fetched))
        else:
            steps.append((article.heading, article.text, authors[-1], page.url, page.fetched))

        # A version without a start date also leaves the one before it without an end, so only
        # the versions after the last undated one are kept. The article's history is then
        # incomplete, and it is listed so no temporal item relies on it.
        dated: list[tuple[dt.date, str, str, str, str, dt.date]] = []
        for heading, text, by, source_url, fetched in steps:
            start = _start_of(by, number, notes, by_diploma, report.resolved, code, report)
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
                    diploma=code.diploma,
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
    return attach_notes(versions, reference, code), report


_NOTED_ON = re.compile(r"de (\d{4}-\d{2}-\d{2})")


def attach_notes(
    versions: list[ArticleVersion], reference: dict[str, dr.Article], code: Code
) -> list[ArticleVersion]:
    """Each of the DR's notes on an article's effects kept with the version it concerns: a
    Constitutional Court ruling with the version in force the day it was published; another
    diploma's word on the effects of a change ("Artigo 9.º, Lei n.º 90/2019 ... Entra em vigor
    com o Orçamento do Estado") with the version that diploma introduced, or, if none, the one in
    force on the note's date. Verbatim, whitespace collapsed."""
    by_article: dict[str, list[int]] = defaultdict(list)
    for n, v in enumerate(versions):
        by_article[v.article].append(n)
    notes: dict[int, list[str]] = defaultdict(list)
    for number, ref in reference.items():
        for kind, found in (("ruling", ref.rulings), ("remark", ref.remarks)):
            for note in found:
                text = " ".join(note.split())
                dated = _NOTED_ON.search(text)
                day = dt.date.fromisoformat(dated.group(1)) if dated else None
                target = None
                if kind == "remark":
                    label = text.split(", ", 1)[1].split(" - ", 1)[0] if ", " in text else ""
                    try:
                        by = diploma_id(label)
                    except ValueError:
                        by = ""
                    target = next(
                        (n for n in by_article[number] if versions[n].introduced_by == by), None
                    )
                if target is None and day is not None:
                    target = next(
                        (n for n in by_article[number] if versions[n].in_force_on(day)), None
                    )
                if target is not None:
                    notes[target].append(text)
    return [
        v.model_copy(update={"notes": notes[n]}) if n in notes else v
        for n, v in enumerate(versions)
    ]


def _start_of(
    by: str,
    article: str,
    notes: dict[str, dt.date | None],
    by_diploma: dict[str, dt.date],
    resolved: list[str],
    code: Code = CT_CODE,
    report: "Report | None" = None,
) -> dt.date | None:
    """When the version of `article` introduced by `by` entered into force (rules in the module
    docstring). A hand-read date the DR's note contradicts is recorded in `report`."""
    if (by, article) in code.corrections:
        corrected, why = code.corrections[(by, article)]
        resolved.append(f"{article}: {by} dated {corrected}, corrected: {why}")
        return corrected
    read = code.read_from_diploma
    if by == code.diploma and (by, article) not in read:
        return code.in_force
    noted = notes.get(by)
    if noted is not None and by != code.diploma:
        hand = read.get((by, article))
        if hand is not None and hand != noted and report is not None:
            message = f"{article}: {by} read by hand as {hand}, the DR's note says {noted}"
            report.disagreements.append(message)
            report.problems.append(f"{message}; a correction in codes.py must say which holds")
        return noted
    if (by, article) in read:
        start: dt.date | None = read[(by, article)]
        rule = "read from the diploma's entry-into-force article"
    elif by in code.rectifies:
        start = _start_of(code.rectifies[by], article, notes, by_diploma, resolved, code, report)
        rule = f"as {code.rectifies[by]}, which it rectifies"
    else:
        start = by_diploma.get(by)
        rule = "the DR's date for it on every other article"
    if start is not None:
        resolved.append(f"{article}: {by} dated {start}, {rule}")
    return start


def _number(ref: pgdl.OldVersionRef) -> int:
    return ref.number
