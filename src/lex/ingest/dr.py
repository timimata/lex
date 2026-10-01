"""The Diário da República's consolidated page for the Código do Trabalho: the reference text,
where each article sits in the code, and when each change to it entered into force.

The page is a single-page app, so it is rendered once with Playwright and its visible text
cached. See docs/decisions/0005-legislation-source.md.
"""

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path

from lex.ingest.fetch import USER_AGENT
from lex.ingest.labels import diploma_id

CT_URL = "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2009-34546475"

# Lower levels are listed after higher ones; a heading clears every level below it.
LEVELS = ("Livro", "Título", "Capítulo", "Secção", "Subsecção", "Divisão", "Subdivisão")
_LEVEL = re.compile(rf"^({'|'.join(LEVELS)}) [IVXLCDM]+(?:-[A-Z])?$")
_ARTICLE = re.compile(r"^Artigo (\d+)\.º(?:-([A-Z]+))?$")
# Some notes carry no entry-into-force date; those are resolved per diploma in build.py.
_NOTE = re.compile(
    r"^(Alterado|Aditado|Retificado|Rectificado|Revogado)\w* pelo/a (?:.*? do/a )?(.+?)"
    r" - Diário da República n\.º \S+, Série I de (\d{4}-\d{2}-\d{2})"
    r"(?:, em vigor a partir de (\d{4}-\d{2}-\d{2}))?",
    re.I,
)
_RULING = re.compile(r"^Acórdão do Tribunal Constitucional n\.º \d+/\d{4}\b")
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


def parse_code(text: str) -> dict[str, Article]:
    """Articles of the code itself, keyed '368' or '252-B'. The articles of Lei n.º 7/2009, which
    come first on the page and reuse numbers 1 to 14, are skipped."""
    lines = [line.strip() for line in text.splitlines()]
    starts = [
        i for i in range(len(lines) - 1) if lines[i : i + 2] == ["Anexo", "CÓDIGO DO TRABALHO"]
    ]
    if not starts:
        raise ValueError("the code's annex was not found on the page")

    path: dict[str, str] = {}
    articles: dict[str, Article] = {}
    i = starts[0] + 2
    while i < len(lines):
        line = lines[i]
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
        while (
            i < len(lines)
            and lines[i]
            and not (_is_boundary(lines[i]) or _NOTE.match(lines[i]) or lines[i] in _NOT_TEXT)
        ):
            body.append(lines[i])
            i += 1
        notes: list[Note] = []
        rulings: list[str] = []
        while i < len(lines) and not _is_boundary(lines[i]):
            if note := _NOTE.match(lines[i]):
                kind = note.group(1).lower().replace("rectificado", "retificado")
                notes.append(
                    Note(
                        kind=kind,
                        diploma=diploma_id(note.group(2)),
                        published=dt.date.fromisoformat(note.group(3)),
                        in_force=dt.date.fromisoformat(note.group(4)) if note.group(4) else None,
                    )
                )
            elif _RULING.match(lines[i]):
                rulings.append(" ".join(lines[i].split()))
            i += 1
        articles[number] = Article(
            article=number,
            heading=heading,
            text="\n".join(body),
            path=tuple(path.values()),
            notes=tuple(notes),
            rulings=tuple(rulings),
            window=window,
        )
    return articles
