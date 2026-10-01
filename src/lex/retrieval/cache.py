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

from lex.domain import Citation, Retriever
from lex.retrieval.dense import Embedder
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

    def __init__(self, base: Embedder, directory: Path) -> None:
        self.base = base
        self.name = base.name
        self.directory = directory

    def _path(self, text: str) -> Path:
        key = hashlib.sha256(f"{self.name}\n{text}".encode()).hexdigest()
        return self.directory / key[:2] / f"{key}.json"

    def encode(self, texts: list[str]) -> list[list[float]]:
        missing = [t for t in dict.fromkeys(texts) if not self._path(t).exists()]
        if missing:
            for text, vector in zip(missing, self.base.encode(missing), strict=True):
                path = self._path(text)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(vector), encoding="utf-8")
        vectors: list[list[float]] = [
            json.loads(self._path(t).read_text(encoding="utf-8")) for t in texts
        ]
        return vectors


class Cached:
    def __init__(self, base: Retriever, directory: Path, version: str) -> None:
        self.base = base
        self.directory = directory
        self.version = version
        self.name = base.name
        self.hits = 0
        self.misses = 0

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
            self.hits += 1
            cached = json.loads(path.read_text(encoding="utf-8"))
            return [Citation.model_validate(c) for c in cached["citations"]]
        self.misses += 1
        ranked = self.base.search(question, as_of, k)
        path.parent.mkdir(parents=True, exist_ok=True)
        citations = [c.model_dump() for c in ranked]
        path.write_text(json.dumps({"citations": citations}), encoding="utf-8")
        return ranked
