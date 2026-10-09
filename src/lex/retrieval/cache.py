"""A disk cache of rankings for eval runs.

The same retriever, code, store contents, question, date and k always give the same ranking, so
re-running an eval (with another answer model, say) can skip retrieval, whose reranker takes
most of a run's time on CPU. The cache keeps hashes and citations only, never question text, so
it holds no copy of a test item.
"""

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from lex import atomic
from lex.domain import Citation, Retriever
from lex.retrieval.dense import ApiEmbedder, Embedder, count_tokens
from lex.store import db

# Code whose change can change a ranking without changing a retriever's name.
CODE = [
    *sorted(Path(__file__).parent.glob("*.py")),
    *sorted(Path(db.__file__).parent.glob("*.py")),
]


def version(config: dict[str, Any], store: str) -> str:
    """What a cached ranking depends on besides the query: the retriever's configuration (model
    ids and revisions), the retrieval code and the store's contents (its fingerprint)."""
    code = hashlib.sha256(b"".join(p.read_bytes() for p in CODE)).hexdigest()
    state = {"config": config, "code": code, "store": store}
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


class CachedEmbedder:
    """An embedder whose vectors are kept on disk, keyed on model and text. On a free tier every
    text embedded counts against a daily quota (1000 a day for Gemini Embedding 2), so a re-run
    must not embed the same question twice. Keeps hashes and vectors only, never text."""

    chunk = 50  # texts embedded, then written, at a time

    def __init__(self, base: Embedder, directory: Path) -> None:
        self.base = base
        self.name = base.name
        self.query_format = base.query_format
        self.document_format = base.document_format
        self.directory = directory
        self.broken = 0  # stored vectors that no longer read, set aside and embedded again
        self.used: list[str] = []  # every text asked for, in order: what a run embedded

    def _path(self, text: str) -> Path:
        key = hashlib.sha256(f"{self.name}\n{text}".encode()).hexdigest()
        return self.directory / key[:2] / f"{key}.json"

    def _vector(self, text: str) -> list[float] | None:
        """The stored vector, or None: missing, or no longer readable (set aside, counted)."""
        path = self._path(text)
        if not path.exists():
            return None
        try:
            vector = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(vector, list):
                raise ValueError("not a vector")
        except ValueError:
            atomic.set_aside(path)
            self.broken += 1
            return None
        return vector

    def tokens(self, texts: list[str]) -> int | None:
        """The input tokens the texts cost, counted once each by the model's provider and kept
        on disk; None if any count is not to be had."""
        total = 0
        for text in texts:
            path = self.directory / "tokens" / self._path(text).name
            if path.exists():
                total += int(json.loads(path.read_text(encoding="utf-8")))
                continue
            counted = count_tokens(self.base, text) if isinstance(self.base, ApiEmbedder) else None
            if counted is None:
                return None
            atomic.write_text(path, json.dumps(counted))
            total += counted
        return total

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.used += texts
        known = {t: self._vector(t) for t in dict.fromkeys(texts)}
        missing = [t for t, v in known.items() if v is None]
        # Kept a chunk at a time: past the day's quota, what was embedded stays embedded.
        for start in range(0, len(missing), self.chunk):
            chunk = missing[start : start + self.chunk]
            for text, vector in zip(chunk, self.base.encode(chunk), strict=True):
                atomic.write_text(self._path(text), json.dumps(vector))
                known[text] = vector
        return [known[t] or [] for t in texts]


class Cached:
    def __init__(self, base: Retriever, directory: Path, version: str) -> None:
        self.base = base
        self.directory = directory
        self.version = version
        self.name = base.name
        self.hits = 0
        self.misses = 0
        self.broken = 0  # stored rankings that no longer read, set aside and searched again

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        query = {
            "version": self.version,
            "retriever": self.name,
            "question": question,
            "as_of": as_of.isoformat(),
            "k": k,
        }
        key = hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest()
        path = self.directory / key[:2] / f"{key}.json"
        if path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                found = [Citation.model_validate(c) for c in cached["citations"]]
            except (ValueError, KeyError, TypeError):  # pydantic's errors are ValueErrors
                atomic.set_aside(path)
                self.broken += 1
            else:
                self.hits += 1
                return found
        self.misses += 1
        ranked = self.base.search(question, as_of, k)
        citations = [c.model_dump() for c in ranked]
        atomic.write_text(path, json.dumps({"citations": citations}))
        return ranked
