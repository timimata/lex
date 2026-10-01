"""Whether the Código do Trabalho has been amended since the corpus was built.

The PGDL's page for the code lists every diploma that amended it ("Contém as seguintes
alterações"). docs/checks/ct-amendments.txt holds that list as it was when the corpus was last
built; `python -m lex.ingest check-updates` fetches the page once and compares, so a weekly CI
job can say when the demo would start answering with outdated law. One request per run.
"""

import html
import re
import urllib.request
from pathlib import Path

from lex.ingest import pgdl
from lex.ingest.fetch import USER_AGENT

KNOWN = Path(__file__).resolve().parents[3] / "docs" / "checks" / "ct-amendments.txt"
# The diploma's own page: the article windows the corpus is built from answered "A query
# falhou!" on 2026-10-01, this one did not.
PAGE = f"{pgdl.BASE}lei_mostra_articulado.php?nid={pgdl.CT_NID}&tabela=leis"
_ITEM = re.compile(
    r"(Lei|Decreto-Lei|DL|Retificação|Rectificação|Declaração de Retificação|Portaria)"
    r"\s+n\.º\s*(\d+(?:-[A-Z])?/\d{4}),\s*de\s*(\d{2}/\d{2})",
)


def parse(page: str) -> list[str]:
    """The amending diplomas the page lists, newest first: "Lei n.º 32/2025, de 27/03"."""
    start = page.find("Contém as seguintes alterações")
    if start < 0:
        raise ValueError("the page has no list of amendments: its layout may have changed")
    end = page.find("</table>", start)  # the list is the header table's last row
    section = html.unescape(re.sub(r"<[^>]+>", " ", page[start : end if end > 0 else None]))
    found = [f"{kind} n.º {number}, de {date}" for kind, number, date in _ITEM.findall(section)]
    return list(dict.fromkeys(found))


def fetch() -> str:
    request = urllib.request.Request(PAGE, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        body: bytes = response.read()
    return pgdl.decode(body)


def known(path: Path = KNOWN) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def new_since(current: list[str], before: list[str]) -> list[str]:
    """Amendments listed now that were not listed when the corpus was built."""
    return [a for a in current if a not in before]
