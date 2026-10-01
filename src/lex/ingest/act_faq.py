"""The ACT's public FAQ (Perguntas Frequentes on portal.act.gov.pt), a source of benchmark
questions (ADR 0008).

The FAQ page is a SharePoint app that reads three lists through SharePoint's REST API; we read
the same three lists, once, cached, and turn each answer's HTML into plain text.
"""

import datetime as dt
import html
import json
import re
from dataclasses import dataclass
from typing import Any

from lex.ingest.fetch import Fetcher

LIST = "https://portal.act.gov.pt/_api/web/lists/getByTitle('{}')/items?$top=5000"
ITEM = "https://portal.act.gov.pt/_api/web/lists/getByTitle('FAQs')/items({})"
PAGE = "https://portal.act.gov.pt/Pages/PerguntasFrequentes.aspx"
ACCEPT = "application/json;odata=nometadata"


@dataclass(frozen=True)
class Faq:
    id: int
    theme: str
    subtheme: str | None
    question: str
    answer: str
    modified: dt.date  # when the ACT last changed the entry
    url: str  # the entry itself, through the API


def html_to_text(fragment: str) -> str:
    """SharePoint rich text -> plain text, one line per paragraph, list item or line break."""
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", fragment)
    text = re.sub(r"(?i)<br\s*/?>|</(?:div|p|li|ul|ol|h\d)>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ").replace("​", "")
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line and line != "-")


def parse(
    faqs: list[dict[str, Any]], themes: list[dict[str, Any]], subthemes: list[dict[str, Any]]
) -> list[Faq]:
    """Rows as the SharePoint API returns them: ids are numbers, text fields may be null."""
    theme = {t["Id"]: (t["Title"] or "").strip() for t in themes}
    subtheme = {s["Id"]: (s["Title"] or "").strip() for s in subthemes}
    parsed = []
    for row in faqs:
        question = (row.get("Pergunta") or row.get("Title") or "").strip()
        answer = html_to_text(row.get("Resposta") or "")
        if not question or not answer:
            continue
        parsed.append(
            Faq(
                id=int(row["Id"] or 0),
                theme=theme.get(row.get("TemaId"), "?"),
                subtheme=subtheme.get(row.get("SubTemaId")),
                question=" ".join(question.split()),
                answer=answer,
                modified=dt.date.fromisoformat((row["Modified"] or "")[:10]),
                url=ITEM.format(row["Id"]),
            )
        )
    return sorted(parsed, key=lambda f: f.id)


def fetch(fetcher: Fetcher) -> list[Faq]:
    lists = [
        json.loads(fetcher.get(LIST.format(name), accept=ACCEPT).body)["value"]
        for name in ("FAQs", "TemasFAQs", "SubTemasFAQs")
    ]
    return parse(*lists)
