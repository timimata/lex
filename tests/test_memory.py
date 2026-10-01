import datetime as dt
from pathlib import Path

import psycopg
import pytest

from lex.domain import Citation
from lex.retrieval.memory import DenseInMemory, Vectors, embed_corpus
from lex.store import db
from lex.store.memory import Corpus
from lex.store.models import ArticleVersion

TODAY = dt.date(2026, 9, 30)


def version(article: str, text: str, start: dt.date, end: dt.date | None) -> ArticleVersion:
    return ArticleVersion(
        diploma="lei-7-2009",
        article=article,
        heading="Epígrafe",
        path=[],
        text=text,
        valid_from=start,
        valid_to=end,
        introduced_by="lei-7-2009",
        source_url="https://example.org",
        fetched=TODAY,
    )


VERSIONS = [
    version("238", "férias com majoração", dt.date(2009, 2, 17), dt.date(2012, 8, 1)),
    version("238", "férias sem majoração", dt.date(2012, 8, 1), None),
    version("251", "faltas por falecimento", dt.date(2009, 2, 17), None),
    version("252-B", "falta por endometriose", dt.date(2025, 4, 26), None),
]


def test_the_corpus_answers_as_the_postgres_store_does(conn: psycopg.Connection) -> None:
    db.load(conn, VERSIONS)
    corpus = Corpus(list(reversed(VERSIONS)))

    for article in ["238", "251", "252-B", "999"]:
        assert corpus.versions_of("lei-7-2009", article) == db.versions_of(
            conn, "lei-7-2009", article
        )
        for day in [dt.date(2009, 2, 16), dt.date(2011, 6, 1), dt.date(2012, 8, 1), TODAY]:
            assert corpus.article_at("lei-7-2009", article, day) == db.article_at(
                conn, "lei-7-2009", article, day
            )


class Words:
    """Embeds a text as counts of four words, normalised."""

    name = "words@4"
    WORDS = ("férias", "majoração", "faltas", "falta")

    def __init__(self) -> None:
        self.calls = 0

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.calls += len(texts)
        out = []
        for text in texts:
            v = [float(text.lower().count(w)) for w in self.WORDS]
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / norm for x in v])
        return out


def test_dense_search_ranks_only_the_law_in_force(tmp_path: Path) -> None:
    corpus = Corpus(VERSIONS)
    embedder = Words()
    vectors, embedded = embed_corpus(corpus, embedder, tmp_path / "v.npz")
    dense = DenseInMemory(corpus, embedder, vectors)

    assert embedded == 4
    assert dense.name == "dense-words"
    assert dense.search("majoração", dt.date(2011, 6, 1), 1) == [
        Citation(diploma="lei-7-2009", article="238")
    ]
    assert [c.article for c in dense.search("faltas", TODAY, 3)] == ["251", "252-B", "238"]
    assert dense.search("falta", dt.date(2024, 1, 1), 3)[1].article != "252-B"  # not yet law
    assert dense.search("férias", dt.date(2008, 1, 1), 3) == []


def test_vectors_are_reused_until_a_text_changes(tmp_path: Path) -> None:
    path = tmp_path / "v.npz"
    embed_corpus(Corpus(VERSIONS), Words(), path)
    again = Words()
    _, embedded = embed_corpus(Corpus(VERSIONS), again, path)
    assert (embedded, again.calls) == (0, 0)

    changed = [*VERSIONS[:3], version("252-B", "falta alterada", dt.date(2025, 4, 26), None)]
    vectors, embedded = embed_corpus(Corpus(changed), again, path)
    assert embedded == 1
    assert Vectors.load(path).shas == vectors.shas

    with pytest.raises(ValueError):
        DenseInMemory(Corpus(VERSIONS), Words(), vectors)  # vectors of another corpus


def headed(article: str, heading: str, text: str, start: dt.date) -> ArticleVersion:
    return version(article, text, start, None).model_copy(update={"heading": heading})


def test_word_search_ignores_accents_and_weighs_headings() -> None:
    corpus = Corpus(
        [
            headed(
                "238", "Duração do período de férias", "Mínimo de 22 dias.", dt.date(2009, 2, 17)
            ),
            headed("92", "Trabalhador-estudante", "Tem férias e licenças.", dt.date(2009, 2, 17)),
            headed("252-B", "Falta por endometriose", "Até três dias.", dt.date(2025, 4, 26)),
        ]
    )
    found = [v.article for v in corpus.search_words("ferias", TODAY)]
    assert found == ["238", "92"]  # the heading's match first
    assert corpus.search_words("endometriose", dt.date(2024, 1, 1)) == []  # not yet law
    assert corpus.search_words("de da do", TODAY) == []  # nothing to go by
