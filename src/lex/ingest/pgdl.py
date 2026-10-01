"""Parsing the PGDL legislation base (pgdlisboa.pt), where article texts and their earlier
versions come from. See docs/decisions/0005-legislation-source.md.

Pages declare ISO-8859-1 but are Windows-1252 (0x96 is an en dash). An article page shows a
window of about ten articles around the one asked for; each article lists the diplomas that
amended it and links to each of its earlier versions. An article added after 2009 says so in a
line of its own text ("Aditado pelo seguinte diploma: ..."), which is taken out of the text.
"""

import html
import re
from dataclasses import dataclass

BASE = "https://www.pgdlisboa.pt/leis/"
CT_NID = 1047  # the Código do Trabalho


def decode(body: bytes) -> str:
    return body.decode("cp1252", errors="replace")


def window_url(article_id: str, nid: int = CT_NID) -> str:
    return (
        f"{BASE}lei_mostra_articulado.php?artigo_id={article_id}&nid={nid}"
        "&tabela=leis&pagina=1&ficha=1&so_miolo=&nversao="
    )


def old_version_url(article_id: str, number: int, nid: int = CT_NID) -> str:
    return (
        f"{BASE}lei_busca_art_velho.php?nid={nid}&artigonum={article_id}"
        f"&n_versao={number}&so_miolo="
    )


def article_number(article_id: str) -> str:
    """'1047A0368' -> '368', '1047A0252B' -> '252-B'."""
    match = re.fullmatch(r"\d+A(\d{4})([A-Z]*)", article_id)
    if match is None:
        raise ValueError(f"not a PGDL article id: {article_id!r}")
    number = str(int(match.group(1)))
    return f"{number}-{match.group(2)}" if match.group(2) else number


@dataclass(frozen=True)
class OldVersionRef:
    number: int
    introduced_by: str  # the label as the PGDL prints it


@dataclass(frozen=True)
class Article:
    article_id: str
    heading: str
    text: str
    added_by: str | None  # label of the diploma that added the article, if not the code itself
    amended_by: tuple[str, ...]  # labels, oldest first
    old_versions: tuple[OldVersionRef, ...]


@dataclass(frozen=True)
class OldVersion:
    heading: str
    text: str
    introduced_by: str


def clean(fragment: str) -> str:
    """HTML fragment -> text, one line per <br>, whitespace collapsed."""
    text = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ")
    text = text.replace("/prct.", "%")  # how the PGDL stores a percent sign
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


_ADDED = re.compile(r"^Aditado pelo seguinte diploma: (.+)$", re.M)


def _split_added(text: str) -> tuple[str, str | None]:
    """Article text without the 'Aditado pelo seguinte diploma' line, and that diploma's label."""
    added = _ADDED.search(text)
    if added is None:
        return text, None
    rest = (text[: added.start()] + text[added.end() :]).strip("\n")
    return re.sub(r"\n{2,}", "\n", rest), added.group(1)


def article_ids(page: str) -> list[str]:
    """Every article id of the diploma, in order, from the page's article selector."""
    return re.findall(r'<option value="(\d+A\d{4}[A-Z]*)"', page)


# The article asked for is highlighted, which adds attributes to both cells.
_HEADING = re.compile(
    r"class=txt_base_b_l[^>]*>.*?Artigo (\d+)\.º(?:-([A-Z]+))?\s*<br>(.*?)</td>", re.S
)
_BODY = re.compile(r"<td valign=top colspan=4 class=txt_base_n_l[^>]*>(.*?)</td>", re.S)
_LABEL = re.compile(r"([A-Z][^,<>]*?n\.º\s*\d+(?:-[A-Z])?/\d{4}), de \d{2}/\d{2}")
_OLD_REF = re.compile(r"n_versao=(\d+)&so_miolo=['\"]?\s*>\s*\d+ª versão:(?:&nbsp;|\s)*([^<]+)</a>")


def parse_window(page: str, nid: int = CT_NID) -> list[Article]:
    articles = []
    # One <table class="artigo"> per article. Only articles with a history carry their id in
    # the markup, so the id is rebuilt from the article number for all of them.
    for block in page.split('<table class="artigo"')[1:]:
        heading = _HEADING.search(block)
        if heading is None:
            continue
        body = _BODY.search(block, heading.end())
        if body is None:
            raise ValueError(f"no text for article {heading.group(1)} on a PGDL page")
        tail = block[body.end() :]
        amended = (
            tail.split("Contém as alterações", 1)[-1] if "Contém as alterações" in tail else ""
        )
        amended = amended.split("Consultar versões anteriores", 1)[0]
        text, added_by = _split_added(clean(body.group(1)))
        articles.append(
            Article(
                article_id=f"{nid}A{int(heading.group(1)):04d}{heading.group(2) or ''}",
                heading=clean(heading.group(3)),
                text=text,
                added_by=added_by,
                amended_by=tuple(" ".join(m.split()) for m in _LABEL.findall(amended)),
                old_versions=tuple(
                    OldVersionRef(int(n), clean(label)) for n, label in _OLD_REF.findall(tail)
                ),
            )
        )
    return articles


_OLD_HEADING = re.compile(r"Artigo [^<]*<br>(.*?)<div", re.S)
_OLD_BODY = re.compile(r'<div style=" margin-left:10px;[^"]*">(.*?)</div>', re.S)
_OLD_BY = re.compile(r"dada pelo seguinte diploma:.*?>([^<]+)</a>", re.S)


def parse_old_version(page: str) -> OldVersion:
    heading, body, by = _OLD_HEADING.search(page), _OLD_BODY.search(page), _OLD_BY.search(page)
    if heading is None or body is None or by is None:
        raise ValueError("unexpected markup for an old article version")
    text, _ = _split_added(clean(body.group(1)))
    return OldVersion(clean(heading.group(1)), text, clean(by.group(1)))
