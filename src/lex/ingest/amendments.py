"""Whether a diploma of the corpus has been amended since the corpus was built.

The PGDL's page for each diploma lists every act that amended it ("Contém as seguintes
alterações"). docs/checks/<code>-amendments.txt holds that list as it was when the corpus was
last built; `python -m lex.ingest check-updates` fetches each diploma's page once and compares,
so a weekly CI job can say when the demo would start answering with outdated law. One request
per diploma per run. For the Código Civil, of which the corpus holds only the articles on
leases, a new amendment may touch none of them: the check says so, a person looks.
"""

import html
import re
import urllib.request
from pathlib import Path

from lex.ingest import pgdl
from lex.ingest.codes import Code
from lex.ingest.fetch import USER_AGENT

CHECKS = Path(__file__).resolve().parents[3] / "docs" / "checks"
# The years of acts before 2000 in two digits, and numbers that carry letters: "DL n.º 329-A/95".
_ITEM = re.compile(
    r"(Lei|Decreto-Lei|DL|Retificação|Rectificação|Declaração de Retificação|Rect\.|Portaria)"
    r"\s+n\.º\s*(\d+(?:-[A-Z]{1,2})?/(?:\d{4}|\d{2})),\s*de\s*(\d{2}/\d{2})",
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


def known_path(code: Code) -> Path:
    return CHECKS / f"{code.key}-amendments.txt"


def fetch(code: Code) -> str:
    """The diploma's own page: the article windows the corpus is built from answered "A query
    falhou!" on 2026-10-01 for the NRAU's first article, this one did not."""
    request = urllib.request.Request(pgdl.diploma_url(code.nid), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        body: bytes = response.read()
    return pgdl.decode(body)


def known(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def new_since(current: list[str], before: list[str]) -> list[str]:
    """Amendments listed now that were not listed when the corpus was built."""
    return [a for a in current if a not in before]
