"""Systems scored from outside (ROADMAP, Phase 12): answers written to a file, or an endpoint
with the demo's /api/answer contract. Each is a `System`, so the harness scores and judges it as
it does the reference systems.

A file holds one JSON object per line: `id`, `text`, `refused`, and `citations`, each with
`diploma`, `article` and, to be checked against the date, `valid_from`; optionally `given`, the
article versions the system read, in the same form. An endpoint is asked
POST {"question", "as_of"} and answers {"answer": {...}} with the same fields.
"""

import datetime as dt
import json
import urllib.request
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from lex.bench.schema import Item
from lex.domain import Answer, Citation, Version


def answer_from(row: Mapping[str, Any]) -> Answer:
    """An answer as a file line or an endpoint gives it."""
    cited = row.get("citations", [])
    dated = [Version.model_validate(c) for c in cited if c.get("valid_from")]
    return Answer(
        text=str(row.get("text", "")),
        refused=bool(row.get("refused", False)),
        citations=[Citation(diploma=c["diploma"], article=c["article"]) for c in cited],
        cited_versions=dated,
        given=[Version.model_validate(v) for v in row.get("given", [])],
    )


class FileSystem:
    """Answers read from a file, matched to each item by id through its question and date."""

    def __init__(self, path: Path, items: Iterable[Item], name: str | None = None) -> None:
        self.name = name or path.stem
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        by_id = {str(row["id"]): row for row in rows}
        self.answers = {
            (item.question, item.as_of): answer_from(by_id[item.id])
            for item in items
            if item.id in by_id
        }
        self.missing = [item.id for item in items if item.id not in by_id]

    def answer(self, question: str, as_of: dt.date) -> Answer:
        found = self.answers.get((question, as_of))
        if found is None:  # no answer given for it: scored as a refusal, and listed
            return Answer(text="", refused=True)
        return found


class HttpSystem:
    """An endpoint with /api/answer's contract. On test it receives the test questions, so it is
    run only for an operator who agreed not to keep them (ADR 0016, amended)."""

    def __init__(self, url: str, name: str | None = None, timeout: float = 60) -> None:
        self.url = url.rstrip("/")
        self.name = name or self.url.split("//")[-1]
        self.timeout = timeout

    def answer(self, question: str, as_of: dt.date) -> Answer:
        body = json.dumps({"question": question, "as_of": as_of.isoformat()}).encode()
        request = urllib.request.Request(
            f"{self.url}/api/answer", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            reply = json.loads(response.read())
        return answer_from(reply["answer"])
