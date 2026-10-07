import datetime as dt
from pathlib import Path

import psycopg
import pytest

from lex.domain import Citation
from lex.retrieval.cache import Cached, CachedEmbedder, version
from lex.store import db
from lex.store.models import ArticleVersion

TODAY = dt.date(2026, 9, 30)


def cite(article: str) -> Citation:
    return Citation(diploma="lei-7-2009", article=article)


class Counting:
    name = "counting"

    def __init__(self) -> None:
        self.calls = 0

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        self.calls += 1
        return [cite("238"), cite("237")][:k]


def test_a_repeated_query_is_answered_from_disk(tmp_path: Path) -> None:
    base = Counting()
    cached = Cached(base, tmp_path, version="v1")

    first = cached.search("Quantos dias de férias?", TODAY, 2)
    again = Cached(Counting(), tmp_path, version="v1").search("Quantos dias de férias?", TODAY, 2)

    assert first == again == [cite("238"), cite("237")]
    assert base.calls == 1
    assert cached.name == "counting"
    # Nothing a test item says is written: only hashes and citations.
    [stored] = tmp_path.rglob("*.json")
    assert "férias" not in stored.read_text(encoding="utf-8")


def test_any_change_to_the_query_or_version_misses(tmp_path: Path) -> None:
    base = Counting()
    cached = Cached(base, tmp_path, version="v1")
    cached.search("P?", TODAY, 2)
    cached.search("P?", TODAY, 1)
    cached.search("P?", dt.date(2011, 6, 1), 2)
    cached.search("Outra?", TODAY, 2)
    Cached(base, tmp_path, version="v2").search("P?", TODAY, 2)

    assert base.calls == 5
    assert (cached.hits, cached.misses) == (0, 4)


def version_row(text: str) -> ArticleVersion:
    return ArticleVersion(
        diploma="lei-7-2009",
        article="238",
        heading="Duração do período de férias",
        path=[],
        text=text,
        valid_from=dt.date(2009, 2, 17),
        valid_to=None,
        introduced_by="lei-7-2009",
        source_url="https://example.org",
        fetched=TODAY,
    )


def test_the_version_follows_the_store_contents_and_the_config(conn: psycopg.Connection) -> None:
    db.load(conn, [version_row("Mínimo de 22 dias úteis.")])
    before = version({"model": "a"}, db.fingerprint(conn))

    assert version({"model": "a"}, db.fingerprint(conn)) == before
    assert version({"model": "b"}, db.fingerprint(conn)) != before
    db.load(conn, [version_row("Mínimo de 25 dias úteis.")])
    assert version({"model": "a"}, db.fingerprint(conn)) != before


class Toy:
    name = "toy@2"
    query_format = "{}"
    document_format = "{heading}\n{text}"

    def __init__(self) -> None:
        self.seen: list[str] = []

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.seen += texts
        return [[float(len(t)), 1.0] for t in texts]


def test_a_text_is_embedded_once_and_never_written(tmp_path: Path) -> None:
    base = Toy()
    embedder = CachedEmbedder(base, tmp_path)

    assert embedder.encode(["férias", "faltas", "férias"]) == [[6.0, 1.0], [6.0, 1.0], [6.0, 1.0]]
    assert CachedEmbedder(Toy(), tmp_path).encode(["faltas"]) == [[6.0, 1.0]]
    embedder.encode(["férias", "outra"])

    assert base.seen == ["férias", "faltas", "outra"]
    assert embedder.name == "toy@2"
    assert not any("férias" in p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.json"))


class Limited(Toy):
    """Embeds `left` texts, then fails as a spent daily quota does."""

    def __init__(self, left: int) -> None:
        super().__init__()
        self.left = left

    def encode(self, texts: list[str]) -> list[list[float]]:
        if len(texts) > self.left:
            raise RuntimeError("quota")
        self.left -= len(texts)
        return super().encode(texts)


def test_a_spent_quota_keeps_the_chunks_already_embedded(tmp_path: Path) -> None:
    texts = [f"artigo {i}" for i in range(5)]
    embedder = CachedEmbedder(Limited(left=4), tmp_path)
    embedder.chunk = 2
    with pytest.raises(RuntimeError):
        embedder.encode(texts)

    tomorrow = Limited(left=10)
    CachedEmbedder(tomorrow, tmp_path).encode(texts)
    assert tomorrow.seen == ["artigo 4"]  # the first four were kept
