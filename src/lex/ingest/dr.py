"""The Diário da República's consolidated page for a diploma: the reference text, where each
article sits in it, and when each change to it entered into force (codes.py says which diploma).

The page is a single-page app, so it is rendered once with Playwright and its visible text
cached. See docs/decisions/0005-legislation-source.md.
"""

import datetime as dt
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from lex.ingest.fetch import USER_AGENT
from lex.ingest.labels import diploma_id

CT_URL = "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2009-34546475"

# Lower levels are listed after higher ones; a heading clears every level below it.
LEVELS = ("Livro", "Título", "Capítulo", "Secção", "Subsecção", "Divisão", "Subdivisão")
_LEVEL = re.compile(rf"^({'|'.join(LEVELS)}) [IVXLCDM]+(?:-[A-Z])?$")
_ARTICLE = re.compile(r"^Artigo (\d+)\.º(?:-([A-Z]+))?$")
# The journal an act was published in: the Diário do Governo until 1976, in a supplement or not,
# and Série I-A from 1976 to 2006.
_JOURNAL = (
    r"Diário d(?P<journal>[ao]) (?:República|Governo) n\.º (?P<issue>\S+),"
    r"(?: \d+\.?º Suplemento,)? Série I(?:-[AB])?"
)
# Some notes carry no entry-into-force date; those are resolved per diploma in build.py.
_NOTE = re.compile(
    r"^(?P<kind>Alterado|Aditado|Retificado|Rectificado|Revogado)\w* pelo/a (?:.*? do/a )?"
    rf"(?P<label>.+?) - {_JOURNAL} de (?P<published>\d{{4}}-\d{{2}}-\d{{2}})"
    r"(?:, em vigor a partir de (?P<in_force>\d{4}-\d{2}-\d{2}))?",
    re.I,
)
# Older pages drop the court's name, and a note on part of a ruling starts with that part's number
# ('III, Acórdão do Tribunal Constitucional n.º 299/2020 ...').
_RULING = re.compile(
    r"^(?:[IVXLCDM]+, )?Acórdão (?:do Tribunal Constitucional )?n\.º \d+/\d{2,4}\b"
)
# What another diploma's article says about this one's effects: deferred, suspended, or
# starting with other legislation ('Artigo 54.º, Lei n.º 56/2023 - Diário da República ...
# As alterações produzidas no n.º 7 do presente artigo, produzem efeitos no dia 3.2.2024.').
_REMARK = re.compile(rf"^Artigo \d+\.º(?:-[A-Z]+)?, .+? - {_JOURNAL} de")
_NOT_TEXT = ("Notas", "Ver alterações ao texto")
# Under 'Versão à data de', the page shows the latest version *published* by that date, even if
# not yet in force, and states its period in force on the line after the heading.
_DATE = r"(\d{4}-\d{2}-\d{2})"
_WINDOW = re.compile(
    rf"^\(em vigor (?:a partir de: {_DATE}|entre {_DATE} e {_DATE}|até: {_DATE})\)$"
)


@dataclass(frozen=True)
class Note:
    kind: str  # alterado, aditado, retificado, revogado
    diploma: str
    published: dt.date
    in_force: dt.date | None


@dataclass(frozen=True)
class Article:
    article: str
    heading: str
    text: str
    path: tuple[str, ...]
    notes: tuple[Note, ...]
    rulings: tuple[str, ...]  # Constitutional Court notes, verbatim
    remarks: tuple[str, ...] = ()  # other diplomas' word on its effects, verbatim
    # The period in force the page states for the version shown, first and last day, where it
    # states one (only in the 'Versão à data de' view). None at either end means open.
    window: tuple[dt.date | None, dt.date | None] | None = None


def _window(line: str) -> tuple[dt.date | None, dt.date | None] | None:
    match = _WINDOW.match(line)
    if match is None:
        return None
    since, start, end, until = (dt.date.fromisoformat(g) if g else None for g in match.groups())
    return (since or start, end or until)


def render(url: str, as_of: dt.date | None = None) -> str:
    """The page's visible text after its scripts have run. With `as_of`, the text as the page
    shows it under 'Versão à data de' for that date (a flatpickr date field, then 'Filtrar')."""
    from playwright.sync_api import sync_playwright  # only needed when fetching

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(3_000)
        if as_of is not None:
            page.evaluate(
                "d => document.querySelector('#Input_Data')._flatpickr.setDate(d, true)",
                as_of.isoformat(),
            )
            if page.input_value("#Input_Data") != as_of.isoformat():
                raise RuntimeError(f"the DR's date field did not take {as_of}")
            page.get_by_text("Filtrar", exact=True).first.click()
            page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5_000)
        text: str = page.inner_text("body")
        browser.close()
    return text


def cached_render(
    url: str, path: Path, *, as_of: dt.date | None = None, offline: bool = False
) -> tuple[str, dt.date]:
    meta = path.with_suffix(".json")
    if meta.exists():
        fetched = json.loads(meta.read_text(encoding="utf-8"))["fetched"]
        return path.read_text(encoding="utf-8"), dt.date.fromisoformat(fetched)
    if offline:
        raise LookupError(f"not in the raw cache: {url}")
    text, today = render(url, as_of), dt.date.today()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    record = {"url": url, "fetched": today.isoformat()}
    if as_of is not None:
        record["as_of"] = as_of.isoformat()
    meta.write_text(json.dumps(record), encoding="utf-8")
    return text, today


def _is_boundary(line: str) -> bool:
    return bool(_ARTICLE.match(line) or _LEVEL.match(line))


def _note_diploma(note: re.Match[str]) -> str:
    """Our id for the act a note names. A few old rectifications have no number and are known by
    the journal issue they are in ('Rectificação - Diário do Governo n.º 236/1975'), so their id
    says so: retificacao-dg-236-1975 (dr for the Diário da República)."""
    label = note.group("label")
    if "n.º" in label or not note.group("kind").lower().startswith(("retificado", "rectificado")):
        return diploma_id(label)
    issue = re.fullmatch(r"(\d+)/(\d{4})", note.group("issue"))
    if issue is None:
        raise ValueError(f"no number for the rectification in: {note.group(0)!r}")
    journal = "dg" if note.group("journal") == "o" else "dr"
    return f"retificacao-{journal}-{int(issue.group(1))}-{issue.group(2)}"


def _quoted(lines: list[str]) -> set[int]:
    """The lines inside «...»: an amending article quoting the articles it gives a new wording,
    whose headings must not be taken for the diploma's own."""
    quoted, depth = set(), 0
    for i, line in enumerate(lines):
        if depth > 0 or line.startswith("«"):
            quoted.add(i)
        depth = max(0, depth + line.count("«") - line.count("»"))
    return quoted


def parse_code(
    text: str,
    start: Sequence[str] = ("Anexo", "CÓDIGO DO TRABALHO"),
    stop: str | None = None,
    quotes: bool = False,
) -> dict[str, Article]:
    """Articles of the diploma, keyed '368' or '252-B', read after the `start` lines and up to the
    `stop` line. For a code, `start` is its annex, which skips the approving law's own articles
    that come first and reuse numbers 1 to 14 (Lei n.º 7/2009) or 1 to 23 (DL n.º 47344). With
    `quotes`, articles quoted in «...» by an amending article are part of its text."""
    lines = [line.strip() for line in text.splitlines()]
    n = len(start)
    starts = [i for i in range(len(lines) - n + 1) if lines[i : i + n] == list(start)]
    if not starts:
        raise ValueError(f"{list(start)} was not found on the page")
    if stop is not None:
        ends = [i for i in range(starts[0] + n, len(lines)) if lines[i] == stop]
        lines = lines[: ends[0]] if ends else lines
    quoted = _quoted(lines) if quotes else set()

    def boundary(i: int) -> bool:
        return i not in quoted and _is_boundary(lines[i])

    path: dict[str, str] = {}
    articles: dict[str, Article] = {}
    i = starts[0] + n
    while i < len(lines):
        line = lines[i]
        if i in quoted:
            i += 1
            continue
        if level := _LEVEL.match(line):
            depth = LEVELS.index(level.group(1))
            path = {k: v for k, v in path.items() if LEVELS.index(k) < depth}
            path[level.group(1)] = f"{line} - {lines[i + 1]}" if i + 1 < len(lines) else line
            i += 2
            continue
        article = _ARTICLE.match(line)
        if article is None:
            i += 1
            continue

        number = article.group(1) + (f"-{article.group(2)}" if article.group(2) else "")
        heading = lines[i + 1] if i + 1 < len(lines) else ""
        body: list[str] = []
        i += 2
        window = _window(lines[i]) if i < len(lines) else None
        if window is not None:
            i += 1
        while i < len(lines) and (
            i in quoted
            or (
                lines[i]
                and not (_is_boundary(lines[i]) or _NOTE.match(lines[i]) or lines[i] in _NOT_TEXT)
            )
        ):
            if lines[i]:
                body.append(lines[i])
            i += 1
        notes: list[Note] = []
        rulings: list[str] = []
        remarks: list[str] = []
        while i < len(lines) and not boundary(i):
            if note := _NOTE.match(lines[i]):
                in_force = note.group("in_force")
                notes.append(
                    Note(
                        kind=note.group("kind").lower().replace("rectificado", "retificado"),
                        diploma=_note_diploma(note),
                        published=dt.date.fromisoformat(note.group("published")),
                        in_force=dt.date.fromisoformat(in_force) if in_force else None,
                    )
                )
            elif _RULING.match(lines[i]):
                rulings.append(" ".join(lines[i].split()))
            elif _REMARK.match(lines[i]):
                remarks.append(" ".join(lines[i].split()))
            i += 1
        articles[number] = Article(
            article=number,
            heading=heading,
            text="\n".join(body),
            path=tuple(path.values()),
            notes=tuple(notes),
            rulings=tuple(rulings),
            remarks=tuple(remarks),
            window=window,
        )
    return articles
