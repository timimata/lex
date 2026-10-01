import datetime as dt
import json
from pathlib import Path

from lex.ingest import act_faq

LISTS = json.loads(
    (Path(__file__).parent / "fixtures" / "act_faq" / "lists.json").read_text("utf-8")
)


def test_faq_entries_come_out_as_plain_text_with_their_theme_and_date() -> None:
    faqs = {
        f.id: f for f in act_faq.parse(LISTS["FAQs"], LISTS["TemasFAQs"], LISTS["SubTemasFAQs"])
    }

    telework = faqs[121]
    assert (telework.theme, telework.subtheme) == ("Teletrabalho", None)
    assert telework.question == "O que é o teletrabalho?"
    assert telework.modified == dt.date(2023, 4, 30)
    assert telework.answer.splitlines()[-1] == "(artigo 165.º do Código do Trabalho)"
    assert "<" not in telework.answer
    assert telework.url.endswith("getByTitle('FAQs')/items(121)")

    fund = faqs[411]
    assert fund.subtheme == "Fundo Garantia Salarial"
    assert any(
        line.startswith("- Declaração ou cópia autenticada") for line in fund.answer.splitlines()
    )


def test_html_to_text_keeps_paragraphs_and_list_items_apart() -> None:
    fragment = (
        "<div><p>Um&#58; <strong>dois</strong></p><ul><li>três</li><li>quatro</li></ul></div>"
    )
    assert act_faq.html_to_text(fragment) == "Um: dois\n- três\n- quatro"
