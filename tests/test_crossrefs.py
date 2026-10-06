import datetime as dt

from lex.domain import Citation
from lex.retrieval.crossrefs import WithCrossReferences, cited_by
from lex.store.memory import Corpus
from lex.store.models import ArticleVersion

TODAY = dt.date(2026, 9, 30)


def cite(article: str) -> Citation:
    return Citation(diploma="lei-7-2009", article=article)


def version(article: str, text: str, start: dt.date = dt.date(2009, 2, 17)) -> ArticleVersion:
    return ArticleVersion(
        diploma="lei-7-2009",
        article=article,
        heading="Epígrafe",
        path=[],
        text=text,
        valid_from=start,
        valid_to=None,
        introduced_by="lei-7-2009",
        source_url="https://example.org",
        fetched=TODAY,
    )


def test_references_by_number_and_by_position() -> None:
    text = (
        "1 - Nos termos do artigo 238.º e dos artigos 250.º a 252.º, salvo no caso previsto "
        "no artigo seguinte. 2 - O artigo 10.º da Lei n.º 23/2012 não é do código. "
        "3 - Remete para o artigo 387.º."
    )
    assert cited_by(text, cite("387")) == [cite(a) for a in ["238", "250", "251", "252", "388"]]
    assert cited_by("o n.º 2 do artigo anterior", cite("199-A")) == []  # no neighbour for 199-A


def test_a_reference_to_another_diploma_of_the_corpus_is_followed_there() -> None:
    # The NRAU's art. 9.º, n.º 7, and the Código Civil's art. 1113.º, n.º 2.
    nrau_9 = Citation(diploma="lei-6-2006", article="9")
    cc_1113 = Citation(diploma="dl-47344-1966", article="1113")
    assert cited_by("nos termos do n.º 2 do artigo 1084.º do Código Civil", nrau_9) == [
        Citation(diploma="dl-47344-1966", article="1084")
    ]
    assert cited_by("É aplicável o disposto no artigo 1107.º", cc_1113) == [
        Citation(diploma="dl-47344-1966", article="1107")
    ]


class Fixed:
    name = "fixed"

    def __init__(self, ranking: list[str]) -> None:
        self.ranking = [cite(a) for a in ranking]

    def search(self, question: str, as_of: dt.date, k: int) -> list[Citation]:
        return self.ranking[:k]


CORPUS = Corpus(
    [
        version(
            "387", "Apreciação no prazo de 60 dias, salvo no caso previsto no artigo seguinte."
        ),
        version("388", "Prazo especial."),
        version("257", "Os efeitos são os do artigo 238.º e do artigo 204.º e do artigo 205.º."),
        version("238", "Férias."),
        version("204", "Banco de horas."),
        version("205", "Banco de horas grupal."),
        version("500", "Texto."),
        version("501", "Texto que cita o artigo 600.º, ainda não em vigor."),
        version("600", "Futuro.", start=dt.date(2030, 1, 1)),
    ]
)


def test_references_follow_the_article_that_makes_them() -> None:
    retriever = WithCrossReferences(Fixed(["387", "500", "257", "238"]), CORPUS.article_at)

    assert retriever.name == "fixed+xrefs"
    # 388 follows 387; 257's first two references follow it; 238 moves up, 205 is not taken.
    assert retriever.search("P?", TODAY, 10) == [
        cite("387"),
        cite("388"),
        cite("500"),
        cite("257"),
        cite("238"),
        cite("204"),
    ]
    assert retriever.search("P?", TODAY, 3) == [cite("387"), cite("388"), cite("500")]


def test_only_the_top_articles_are_followed_and_only_to_the_law_in_force() -> None:
    retriever = WithCrossReferences(Fixed(["500", "238", "204", "387"]), CORPUS.article_at, top=3)
    assert cite("388") not in retriever.search("P?", TODAY, 10)  # 387 is fourth
    assert WithCrossReferences(Fixed(["501"]), CORPUS.article_at).search("P?", TODAY, 5) == [
        cite("501")  # 600 is not yet in force
    ]
