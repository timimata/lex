"""Reranking: a cross-encoder reads the question with each candidate article, whole, and
reorders the base retriever's top candidates (ADR 0010)."""

import datetime as dt
from typing import Protocol

import psycopg

from lex.domain import Citation, Retriever
from lex.retrieval.dense import document
from lex.store import db

BGE_RERANKER = "BAAI/bge-reranker-v2-m3"
BGE_RERANKER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
DEPTH = 20  # candidates reranked per question; a usual default, not tuned on dev


class Scorer(Protocol):
    name: str

    def score(self, question: str, documents: list[str]) -> list[float]:
        """Relevance of each document to the question; higher is more relevant."""
        ...


class BgeReranker:
    name = f"{BGE_RERANKER}@{BGE_RERANKER_REVISION[:7]}"

    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder  # the optional `dense` extra

        self.model = CrossEncoder(
            BGE_RERANKER, revision=BGE_RERANKER_REVISION, device="cpu", max_length=1024
        )

    def score(self, question: str, documents: list[str]) -> list[float]:
        scores = self.model.predict([(question, d) for d in documents], batch_size=8)
        return [float(s) for s in scores]


class Reranked:
    def __init__(
        self, base: Retriever, scorer: Scorer, conn: psycopg.Connection, depth: int = DEPTH
    ) -> None:
        self.base = base
        self.scorer = scorer
        self.conn = conn
        self.depth = depth
        self.name = f"{base.name}+rerank"

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        candidates = self.base.search(question, as_of, max(k, self.depth))
        documents = []
        for c in candidates:
            version = db.article_at(self.conn, c.diploma, c.article, as_of)
            documents.append(document(version.heading, version.text) if version else "")
        scores = self.scorer.score(question, documents)
        order = sorted(range(len(candidates)), key=lambda i: (-scores[i], i))
        return [candidates[i] for i in order][:k]
