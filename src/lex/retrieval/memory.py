"""Dense retrieval without Postgres, for the serverless demo (ADR 0014).

Each article version's vector is kept in a file next to the corpus; a question is ranked
against the versions in force on its date by cosine similarity, ties broken by article number
as the Postgres query breaks them.
"""

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from lex.domain import Citation
from lex.retrieval.dense import Embedder, document, retriever_name
from lex.store.memory import Corpus


def _sha(heading: str, text: str, format: str) -> str:
    return hashlib.sha256(document(heading, text, format).encode()).hexdigest()


@dataclass
class Vectors:
    """One normalised vector per article version, in the corpus's order."""

    model: str
    shas: list[str]  # of the text each vector embedded
    matrix: np.ndarray  # float32, one row per version

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            np.savez_compressed(
                f, matrix=self.matrix, meta=np.array(json.dumps([self.model, self.shas]))
            )

    @classmethod
    def load(cls, path: Path) -> "Vectors":
        with np.load(path) as data:
            model, shas = json.loads(str(data["meta"]))
            return cls(model=model, shas=shas, matrix=data["matrix"].astype(np.float32))


def embed_corpus(corpus: Corpus, embedder: Embedder, path: Path) -> tuple[Vectors, int]:
    """The corpus's vectors for this embedder, from `path` where its texts are unchanged and from
    the embedder for the rest, saved back to `path`. Returns them and how many were embedded."""
    fmt = embedder.document_format
    shas = [_sha(v.heading, v.text, fmt) for v in corpus.versions]
    known: dict[str, np.ndarray] = {}
    if path.exists():
        old = Vectors.load(path)
        if old.model == embedder.name:
            known = dict(zip(old.shas, old.matrix, strict=True))
    todo = [i for i, sha in enumerate(shas) if sha not in known]
    if todo:
        docs = [document(corpus.versions[i].heading, corpus.versions[i].text, fmt) for i in todo]
        for i, vector in zip(todo, embedder.encode(docs), strict=True):
            known[shas[i]] = np.asarray(vector, dtype=np.float32)
    vectors = Vectors(embedder.name, shas, np.stack([known[sha] for sha in shas]))
    if todo:
        vectors.save(path)
    return vectors, len(todo)


class DenseInMemory:
    def __init__(self, corpus: Corpus, embedder: Embedder, vectors: Vectors) -> None:
        if vectors.model != embedder.name:
            raise ValueError(f"vectors of {vectors.model}, embedder {embedder.name}")
        fmt = embedder.document_format
        if vectors.shas != [_sha(v.heading, v.text, fmt) for v in corpus.versions]:
            raise ValueError("the vectors do not match the corpus: embed it again")
        self.corpus = corpus
        self.embedder = embedder
        norms = np.linalg.norm(vectors.matrix, axis=1, keepdims=True)
        self.matrix = vectors.matrix / np.where(norms == 0, 1, norms)
        self.name = retriever_name(embedder)

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        written = self.embedder.query_format.format(question)
        query = np.asarray(self.embedder.encode([written])[0], dtype=np.float32)
        query /= np.linalg.norm(query) or 1.0
        in_force = [i for i, v in enumerate(self.corpus.versions) if v.in_force_on(as_of)]
        if not in_force:
            return []
        similarity = self.matrix[in_force] @ query
        order = sorted(
            range(len(in_force)),
            key=lambda j: (-float(similarity[j]), self.corpus.versions[in_force[j]].article),
        )
        versions = [self.corpus.versions[in_force[j]] for j in order[:k]]
        return [Citation(diploma=v.diploma, article=v.article) for v in versions]
