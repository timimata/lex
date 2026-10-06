"""The diplomas the corpus holds, and what reading each from the PGDL and the DR takes.

The Código do Trabalho came first (ADRs 0003, 0005); tenancy, the Código Civil's articles on
leases and the NRAU, came in Phase 6 (ADR 0017). Everything a diploma needs beyond the shared
parsing lives here, so the rest of ingestion does not name any diploma.
"""

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field


def _number(article: str) -> int:
    return int(article.split("-")[0])


@dataclass(frozen=True)
class Code:
    key: str  # data/processed/<key>/ and data/raw/dr/<key>.txt
    diploma: str  # our id for the diploma itself
    name: str
    nid: int  # the PGDL's id for the diploma
    dr_url: str  # the DR's consolidated page
    in_force: dt.date  # when the diploma's own text entered into force: its first versions start
    # The lines on the DR page after which the diploma's text begins, and the line at which it
    # ends, if anything follows it.
    start: tuple[str, ...]
    stop: str | None = None
    # Whether amending articles quote other diplomas' articles in «...», which are not ours.
    quotes: bool = False
    keep: Callable[[str], bool] = lambda article: True  # which articles the corpus holds
    # Which diploma each rectification corrects, as the DR's list of amending acts describes it.
    rectifies: Mapping[str, str] = field(default_factory=dict)
    # (diploma, article) -> entry into force, read from a diploma's own entry-into-force article
    # where the DR gives no date, or where a diploma starts on different dates for different
    # articles.
    read_from_diploma: Mapping[tuple[str, str], dt.date] = field(default_factory=dict)
    # (diploma, article) -> (entry into force, why), where the DR's own note is wrong.
    corrections: Mapping[tuple[str, str], tuple[dt.date, str]] = field(default_factory=dict)


CT = Code(
    key="ct",
    diploma="lei-7-2009",
    name="Código do Trabalho",
    nid=1047,
    dr_url="https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2009-34546475",
    # The code's own entry into force, as the DR dates the Declaração de Rectificação n.º 21/2009.
    in_force=dt.date(2009, 2, 17),
    start=("Anexo", "CÓDIGO DO TRABALHO"),
    rectifies={
        "retificacao-21-2009": "lei-7-2009",
        "retificacao-28-2017": "lei-73-2017",
        "retificacao-13-2023": "lei-13-2023",
    },
    read_from_diploma={
        # Lei n.º 90/2019, art. 9.º, n.º 1, as rectified by Retificação n.º 48/2019: "com o
        # Orçamento do Estado posterior à sua publicação", i.e. Lei n.º 2/2020, published
        # 2020-03-31 and in force the next day (its art. 430.º).
        **{
            ("lei-90-2019", article): dt.date(2020, 4, 1)
            for article in ("35", "37-A", "40", "42", "43", "53", "65", "94")
        },
        # Lei n.º 90/2019, art. 9.º, n.º 2: "30 dias após a publicação", published 2019-09-04.
        **{("lei-90-2019", article): dt.date(2019, 10, 4) for article in ("33-A", "252-A")},
    },
)

# Tenancy (ADR 0017): the Código Civil's chapter on leases, general rules and urban leases.
CC = Code(
    key="cc",
    diploma="dl-47344-1966",
    name="Código Civil",
    nid=775,
    dr_url="https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1966-34509075",
    # Decreto-Lei n.º 47344, art. 2.º: in force from 1 June 1967.
    in_force=dt.date(1967, 6, 1),
    start=("Anexo", "CÓDIGO CIVIL"),
    keep=lambda article: 1022 <= _number(article) <= 1113,
    corrections={
        ("lei-6-2006", "1073"): (
            dt.date(2006, 6, 27),
            "the DR's note says 2007-06-27; its 61 other notes for Lei n.º 6/2006 say 2006-06-27,"
            " and the law defers no article (its art. 65.º)",
        ),
    },
)

# The NRAU itself, Lei n.º 6/2006, without its articles 2.º to 8.º, which only amend other
# diplomas (the Código Civil's are taken from the code itself).
NRAU = Code(
    key="nrau",
    diploma="lei-6-2006",
    name="NRAU",
    nid=691,
    dr_url="https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2006-34578375",
    # Art. 65.º, n.º 2: "120 dias após a sua publicação" (2006-02-27); the DR dates the law's
    # changes to the Código Civil 2006-06-27, and its other provisions start with them.
    in_force=dt.date(2006, 6, 27),
    start=(
        "A Assembleia da República decreta, nos termos da alínea c) do artigo 161.º da"
        " Constituição, o seguinte:",
    ),
    # The signatures after the last article, then an annex republishing the Código Civil's
    # chapter on leases as of 2006.
    stop="Aprovada em 21 de Dezembro de 2005.",
    quotes=True,
    keep=lambda article: not 2 <= _number(article) <= 8,
    read_from_diploma={
        # Art. 65.º, n.º 1: articles 63.º and 64.º "no dia seguinte ao da publicação".
        ("lei-6-2006", "63"): dt.date(2006, 2, 28),
        ("lei-6-2006", "64"): dt.date(2006, 2, 28),
    },
    rectifies={"retificacao-24-2006": "lei-6-2006"},
    corrections={
        ("retificacao-24-2006", "12"): (
            dt.date(2006, 6, 27),
            "the DR's note says 2006-06-28, but a rectification takes effect when the text it"
            " corrects did (Lei n.º 74/98, art. 5.º, n.º 4), and Lei n.º 6/2006 started 2006-06-27",
        ),
        **{
            ("lei-31-2012", article): (
                dt.date(2012, 11, 12),
                "the DR's note says 2012-11-10; Lei n.º 31/2012 revokes the article in its art."
                " 13.º with no date of its own, and enters into force 90 days after its"
                " publication on 2012-08-14 (art. 15.º), as the DR's 44 other notes for it say",
            )
            for article in [*(str(n) for n in range(38, 50)), "55", "56"]
        },
    },
)

CODES: dict[str, Code] = {code.key: code for code in (CT, CC, NRAU)}
