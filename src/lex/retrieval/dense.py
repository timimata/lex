"""The dense baseline: article versions embedded whole (heading and text), ranked by cosine
distance in pgvector among the versions in force on the date asked about (ADR 0007)."""

import datetime as dt
import hashlib
import time
from typing import Protocol

import psycopg

from lex.domain import Citation

BGE_M3 = "BAAI/bge-m3"
BGE_M3_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"


class Embedder(Protocol):
    name: str  # stored with each embedding; different models or revisions never mix
    query_format: str  # how a question is written before it is embedded; "{}" as it is

    def encode(self, texts: list[str]) -> list[list[float]]:
        """One normalised vector per text."""
        ...


class BgeM3:
    name = f"{BGE_M3}@{BGE_M3_REVISION[:7]}"
    query_format = "{}"  # BGE-M3's dense vectors take no instruction

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # the optional `dense` extra

        self.model = SentenceTransformer(BGE_M3, revision=BGE_M3_REVISION, device="cpu")

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True, batch_size=8)
        return [[float(x) for x in v] for v in vectors]


GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
RATE_LIMIT_WAITS = (30, 60, 120)  # seconds; free tiers limit requests per minute
# Gemini Embedding 2 takes its task in the text, not as a parameter: Google's embeddings guide
# writes a question asked for question answering like this, and a document as "title: ... |
# text: ...". Taken from the guide, not tuned; on dev it raised recall@5 from 0.84 to 0.90
# (ROADMAP, Phase 6). The stored vectors still embed documents as `document` writes them:
# embedding the corpus again takes more texts (1,213) than the free tier allows in a day (1,000).
GEMINI_QUERY = "task: question answering | query: {}"


class ApiEmbedder:
    """An embedding model behind an OpenAI-compatible endpoint: Gemini Embedding 2 at 768
    dimensions for the serverless demo, which cannot hold BGE-M3 (ADR 0014)."""

    batch = 50  # texts per request

    def __init__(
        self,
        model: str = "gemini-embedding-2",
        dimensions: int = 768,
        base_url: str = GEMINI_OPENAI_URL,
        api_key: str = "",
        waits: tuple[int, ...] = RATE_LIMIT_WAITS,  # () for a visitor who should not wait
        timeout: float = 120,  # seconds per request
        max_retries: int = 2,  # the client's own quick retries of transient errors
        query_format: str = GEMINI_QUERY,
    ) -> None:
        from openai import OpenAI  # the optional `llm` extra

        self.waits = waits
        self.query_format = query_format
        self.model = model
        self.dimensions = dimensions
        self.name = f"{model}@{dimensions}"
        self.client = OpenAI(
            base_url=base_url, api_key=api_key or "none", timeout=timeout, max_retries=max_retries
        )

    def encode(self, texts: list[str]) -> list[list[float]]:
        from openai import RateLimitError

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch):
            chunk = texts[start : start + self.batch]
            for wait in (*self.waits, None):
                try:
                    response = self.client.embeddings.create(
                        model=self.model, input=chunk, dimensions=self.dimensions
                    )
                    break
                except RateLimitError:
                    if wait is None:
                        raise
                    time.sleep(wait)
            # In request order: Gemini's endpoint leaves `index` empty.
            if len(response.data) != len(chunk):
                raise RuntimeError(f"{len(response.data)} embeddings for {len(chunk)} texts")
            for item in response.data:
                norm = sum(x * x for x in item.embedding) ** 0.5 or 1.0
                vectors.append([x / norm for x in item.embedding])
        return vectors


def document(heading: str, text: str) -> str:
    """What gets embedded for an article version."""
    return f"{heading}\n{text}"


def _vector(values: list[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in values) + "]"


def embed_missing(conn: psycopg.Connection, embedder: Embedder, batch: int = 32) -> int:
    """Embed every article version with no embedding for this model, or whose text changed.
    Returns how many were embedded."""
    rows = conn.execute(
        """
        SELECT v.diploma, v.article, v.valid_from, v.heading, v.text, e.text_sha256
        FROM article_versions v
        LEFT JOIN article_embeddings e ON e.diploma = v.diploma AND e.article = v.article
            AND e.valid_from = v.valid_from AND e.model = %s
        ORDER BY v.id
        """,
        (embedder.name,),
    ).fetchall()
    todo = []
    for diploma, article, valid_from, heading, text, stored_sha in rows:
        doc = document(heading, text)
        sha = hashlib.sha256(doc.encode()).hexdigest()
        if sha != stored_sha:
            todo.append((diploma, article, valid_from, doc, sha))
    for start in range(0, len(todo), batch):
        chunk = todo[start : start + batch]
        vectors = embedder.encode([doc for _, _, _, doc, _ in chunk])
        with conn.transaction(), conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO article_embeddings
                    (diploma, article, valid_from, model, text_sha256, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (diploma, article, valid_from, model)
                DO UPDATE SET text_sha256 = EXCLUDED.text_sha256, embedding = EXCLUDED.embedding
                """,
                [
                    (d, a, vf, embedder.name, sha, _vector(vec))
                    for (d, a, vf, _, sha), vec in zip(chunk, vectors, strict=True)
                ],
            )
        # Inside the transaction the SELECT opened, `conn.transaction()` is only a savepoint:
        # commit each batch, or a connection closed without a commit discards them all.
        conn.commit()
        print(f"  embedded {min(start + batch, len(todo))}/{len(todo)}", flush=True)
    return len(todo)


class Dense:
    def __init__(self, conn: psycopg.Connection, embedder: Embedder) -> None:
        self.conn = conn
        self.embedder = embedder
        self.name = f"dense-{embedder.name.split('/')[-1].split('@')[0]}"

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        query = _vector(self.embedder.encode([self.embedder.query_format.format(question)])[0])
        rows = self.conn.execute(
            """
            SELECT v.diploma, v.article
            FROM article_versions v
            JOIN article_embeddings e ON e.diploma = v.diploma AND e.article = v.article
                AND e.valid_from = v.valid_from AND e.model = %(model)s
            WHERE daterange(v.valid_from, v.valid_to) @> %(as_of)s::date
            ORDER BY e.embedding <=> %(query)s::vector, v.article
            LIMIT %(k)s
            """,
            {"model": self.embedder.name, "as_of": as_of, "query": query, "k": k},
        ).fetchall()
        return [Citation(diploma=diploma, article=article) for diploma, article in rows]
