"""End-to-end check of the page in a real browser, with no model quota spent.

    python web/e2e.py [--shots DIR]

Serves the built page (web/dist) and the API with the real article corpus but a scripted answer,
then drives Chromium through what a visitor does: switch language, open a shared link, read a
cited article, compare it with its previous version, reload. Needs the `ingest` extra
(Playwright) and `npm run build` in web/. Exits non-zero at the first check that fails.
"""

import argparse
import datetime as dt
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402
from playwright.sync_api import Locator, Page, expect, sync_playwright  # noqa: E402

from lex.api.app import create_app, leaderboard  # noqa: E402
from lex.domain import Answer, Citation  # noqa: E402
from lex.store.memory import Corpus, corpus_files  # noqa: E402

PORT = 8765
URL = f"http://127.0.0.1:{PORT}/"


class Scripted:
    """Answers every question citing article 238, the one with a 2012 change to compare, after
    its one sentence, as the demo's per-sentence format does."""

    # The demo's name, so that the page finds its test run and shows its numbers.
    name = "dense-gemini-embedding-2+refs+gemini-3.1-flash-lite+agent"

    def answer(self, question: str, as_of: dt.date) -> Answer:
        time.sleep(0.2)
        return Answer(
            text=f"Resposta de teste para {as_of:%d/%m/%Y}. (art. 238.º do CT)",
            citations=[Citation(diploma="lei-7-2009", article="238")],
            # As the agent's: one search before the answer, two calls in all.
            requests=["pesquisar «majoração das férias»: CT 238"],
            tokens={
                "calls": 2,
                "prompt_tokens": 2000,
                "completion_tokens": 300,
                "thinking_tokens": 40,
            },
        )


def serve() -> None:
    # The ingested corpus, or, where it is not (CI), the committed copy of its text.
    files = corpus_files(ROOT / "data" / "processed") or [ROOT / "corpus" / "versions.jsonl.gz"]
    corpus = Corpus.load(*files)
    app = create_app(
        Scripted(),
        library=corpus.versions_of,
        find=corpus.search_words,
        changes=corpus.changes,
        leaderboard=leaderboard(ROOT / "results" / "test"),
        static=ROOT / "web" / "dist",
    )
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


AXE = ROOT / "web" / "node_modules" / "axe-core" / "axe.min.js"  # npm ci in web/
WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
violations: list[str] = []  # every page audited adds what axe found; main fails on any


def audit(page: Page, where: str) -> None:
    """axe-core on the page as it stands, against WCAG 2.2 A and AA. Evaluated by the browser's
    driver, not added as a script: the page's Content-Security-Policy refuses inline scripts, as
    it should, and the check runs with it in force."""
    if not page.evaluate("typeof axe !== 'undefined'"):
        page.evaluate(AXE.read_text(encoding="utf-8"))
    found = page.evaluate(
        "tags => axe.run(document, {runOnly: {type: 'tag', values: tags}})"
        ".then(r => r.violations.map(v => v.id + ': ' + v.nodes.length + ' ' + v.help))",
        WCAG,
    )
    violations.extend(f"{where}: {v}" for v in found)


def check(page: Page, shots: Path | None) -> None:
    def tab(name: str) -> Locator:
        return page.get_by_role("navigation").get_by_role("link", name=name, exact=True)

    submit = page.locator(".ask form button[type=submit]")

    def shot(name: str) -> None:
        if shots:
            page.screenshot(path=str(shots / f"{name}.png"), full_page=True, animations="disabled")

    # Language: the switch changes the interface, and the choice survives a reload.
    page.goto(URL)
    page.get_by_role("button", name="EN", exact=True).click()
    expect(tab("Ask")).to_be_visible()
    expect(page.locator(".notice")).to_contain_text(re.compile("not legal advice", re.IGNORECASE))
    page.reload()
    expect(tab("Results")).to_be_visible()
    page.get_by_role("button", name="PT", exact=True).click()
    expect(tab("Resultados")).to_be_visible()
    shot("1-home")
    audit(page, "home")

    # A shared link asks its question on arrival, on its date, and the answer says how long.
    page.goto(URL + "?q=Quantos+dias+de+f%C3%A9rias%3F&d=2011-06-01&lang=pt")
    expect(page.locator(".answer-text")).to_contain_text("01/06/2011")
    expect(page.locator(".answer-details")).to_contain_text(" s")
    expect(page.locator(".answer-details")).to_contain_text("2 chamadas ao modelo, 2340 tokens")
    expect(page.locator(".requests li")).to_have_text(["pesquisar «majoração das férias»: CT 238"])
    assert "d=2011-06-01" in page.url, page.url
    expect(page.locator(".examples")).to_have_count(0)  # the answer took the examples' place

    # The article cited after the sentence opens on the 2011 version, its first: nothing to
    # compare.
    page.locator(".answer-text .marker button").first.click()
    expect(page.locator(".reader-meta")).to_contain_text("01/06/2011")
    expect(page.locator(".reader")).to_contain_text("Primeira versão")

    # The 2012 version compares with 2009's: what Lei n.º 23/2012 removed is struck through.
    page.locator(".timeline button").nth(1).click()
    page.get_by_role("button", name="Ver alterações face à versão anterior").click()
    expect(page.locator(".diff del").first).to_be_visible()
    removed = " ".join(page.locator(".diff del").all_inner_texts())
    assert "faltado" in removed or "três" in removed.lower(), removed
    shot("2-changes")
    audit(page, "an answer, its article's changes open")

    # The same question again comes from the cache, and the page says so.
    submit.click()
    expect(page.locator(".kicker")).to_contain_text("resposta guardada")

    # Articles, with no model: by number on a date, by words, and from a link. The page has a
    # path of its own, and the title follows.
    tab("Artigos").click()
    assert page.url.startswith(URL + "artigos"), page.url
    expect(page).to_have_title("Artigos · Lex")
    page.fill("#browse", "art. 238.º")
    page.locator(".browse form input[type=date]").fill("2011-06-01")
    page.locator(".browse form button[type=submit]").click()
    expect(page.locator(".browse .reader-meta")).to_contain_text("01/06/2011")
    expect(page.locator(".browse .reader")).to_contain_text("Três dias de férias")
    page.fill("#browse", "teletrabalho")
    page.locator(".browse form button[type=submit]").click()
    expect(page.locator(".hits li").first).to_be_visible()
    assert any("165" in h for h in page.locator(".hits li").all_inner_texts())
    shot("4-articles")
    audit(page, "articles, a word search")
    # A version the Constitutional Court ruled on carries the DR's note above its text.
    page.goto(URL + "?art=368&d=2013-12-01&lang=pt")
    expect(page.locator(".browse .reader-notes")).to_contain_text("602/2013")
    audit(page, "an article with a note")
    page.goto(URL + "?art=252-B&d=2025-05-01&lang=pt")
    expect(page.locator(".browse .reader-meta")).to_contain_text("01/05/2025")
    page.goto(URL + "?art=252-B&d=2024-01-01&lang=pt")
    expect(page.locator(".browse .reader")).to_contain_text("Nenhuma versão")  # not yet law

    # Tenancy: a diploma named in the query, one chosen in the list, and one in a link.
    page.fill("#browse", "NRAU 9")
    page.locator(".browse form input[type=date]").fill("2026-09-30")
    page.locator(".browse form button[type=submit]").click()
    expect(page.locator(".browse .reader-code")).to_contain_text("NRAU")
    expect(page.locator(".browse .reader")).to_contain_text("Forma da comunicação")
    assert "dip=NRAU" in page.url, page.url
    page.locator(".browse form select").select_option(label="Código Civil")
    page.fill("#browse", "1083")
    page.locator(".browse form button[type=submit]").click()
    expect(page.locator(".browse .reader")).to_contain_text("Fundamento da resolução")
    expect(page.locator(".browse .reader")).to_contain_text("Lei n.º 13/2019")
    # Words, in one diploma: each hit shows the line that holds them, the words marked.
    page.fill("#browse", "renda antecipado")
    page.locator(".browse form button[type=submit]").click()
    advance = page.locator(".hits li", has_text="art. 1076.º do CC")
    expect(advance.locator("mark")).to_have_text(["renda", "antecipado"])
    page.locator(".browse form select").select_option(label="NRAU (Lei n.º 6/2006)")
    page.locator(".browse form button[type=submit]").click()
    expect(page.locator(".hits")).not_to_contain_text("1076")
    # A bare number with every diploma: the diplomas that have it.
    page.locator(".browse form select").select_option(label="Todos os diplomas")
    page.fill("#browse", "9")
    page.locator(".browse form button[type=submit]").click()
    expect(page.locator(".hits .cite")).to_have_text(["art. 9.º do CT", "art. 9.º do NRAU"])
    page.goto(URL + "?art=1083&dip=CC&d=2012-01-01&lang=pt")
    expect(page.locator(".browse .reader-code")).to_contain_text("Código Civil")
    expect(page.locator(".browse .reader-meta")).to_contain_text("Lei n.º 6/2006")

    # The reader copies a link to the article as on that date.
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.locator(".reader-actions").get_by_role("button", name="Copiar ligação").click()
    expect(page.locator(".reader-actions")).to_contain_text("Ligação copiada")
    link = page.evaluate("navigator.clipboard.readText()")
    assert "/artigos?art=1083&dip=CC&d=2012-01-01" in link, link

    # Printed, the article keeps its text, its date and the disclaimer, without the controls.
    page.emulate_media(media="print")
    expect(page.locator(".nav")).to_be_hidden()
    expect(page.locator(".browse form")).to_be_hidden()
    expect(page.locator(".reader-meta")).to_be_visible()
    expect(page.locator(".timeline")).to_contain_text("27/06/2006")  # the history keeps its dates
    expect(page.locator(".footer-legal")).to_contain_text("não é aconselhamento jurídico")
    if shots:
        page.pdf(path=str(shots / "6-print.pdf"))
    page.emulate_media(media="screen")

    # Shared, a link unfurls with a picture of a real answer.
    assert 'property="og:image" content="https://lex-beryl.vercel.app/og.png"' in page.content()
    image = page.request.get(URL + "og.png")
    assert image.ok and image.headers["content-type"] == "image/png", image.status

    # Results and About open by their own paths, as the API serves them.
    page.goto(URL + "resultados?lang=pt")
    expect(page.locator("table").first).to_be_visible()
    page.goto(URL + "sobre?lang=en")
    expect(page.locator(".prose")).to_contain_text("Gemini embeddings")
    page.go_back()
    expect(page.locator("table").first).to_be_visible()  # the browser's back button works

    # What changed between two dates: Lei n.º 13/2019 in the Código Civil, its articles opening
    # on their changes (the late-rent fee, 50 % before, 20 % after).
    page.goto(URL + "alteracoes?dip=CC&de=2019-01-01&ate=2019-12-31&lang=pt")
    expect(page).to_have_title("Alterações · Lex")
    law = page.locator(".change-group", has_text="Lei n.º 13/2019")
    expect(law.locator(".change-law")).to_contain_text("13/02/2019")
    expect(law.locator(".hits li")).to_have_count(15)
    law.get_by_role("button", name="art. 1041.º do CC").click()
    expect(page.locator(".diff del").first).to_contain_text("50%")
    expect(page.locator(".diff ins").first).to_contain_text("20 %")
    shot("7-changes")
    audit(page, "what changed, an article's changes open")
    tab("Alterações").click()
    expect(page.locator(".change-group").first).to_be_visible()  # kept across a reload of view

    # The home page shows the demo's own numbers, once it has a judged test run.
    page.goto(URL + "?lang=pt")
    if any(r["system"] == Scripted.name for r in leaderboard(ROOT / "results" / "test")):
        expect(page.locator(".figures dt").first).to_be_visible()

    # Results and About render in both languages, and an answer survives the tabs.
    page.goto(URL + "?q=Quantos+dias+de+f%C3%A9rias%3F&d=2011-06-01&lang=pt")
    expect(page.locator(".answer-text")).to_contain_text("01/06/2011")
    tab("Resultados").click()
    expect(page.locator("table").first).to_be_visible()
    # Correct, partial and wrong, each shown, and the rule that tells them apart.
    for column in ("Respostas corretas", "Parciais", "Erradas"):
        expect(page.locator("table").first.locator("th", has_text=column)).to_be_visible()
    expect(page.locator(".note", has_text="Parcial: falta parte")).to_be_visible()
    shot("3-results")
    audit(page, "results")
    page.get_by_role("button", name="EN", exact=True).click()
    tab("About").click()
    expect(page.locator(".prose")).to_contain_text("Gemini embeddings")
    audit(page, "about, in English")
    tab("Ask").click()
    expect(page.locator(".answer")).to_be_visible()


def keyboard(page: Page) -> None:
    """The page by keyboard alone: tab to a view in the nav and open it, focus lands on the new
    view's heading; back, and focus lands on the first view's; tab to the question, ask it."""
    page.goto(URL + "?lang=pt")
    expect(page.locator(".examples")).to_be_visible()

    def tab_to(name: str) -> None:
        for _ in range(40):
            page.keyboard.press("Tab")
            if page.evaluate("document.activeElement.textContent.trim()") == name:
                return
        raise AssertionError(f"«{name}» cannot be reached by Tab")

    def focused() -> str:
        return str(
            page.evaluate(
                "document.activeElement.tagName + ' ' + document.activeElement.textContent.trim()"
            )
        )

    def on_heading() -> None:
        # Polled from here: the page's CSP refuses the eval that wait_for_function would need.
        for _ in range(100):
            if page.evaluate("document.activeElement.tagName") == "H1":
                return
            page.wait_for_timeout(50)
        raise AssertionError(f"focus is not on a heading but on {focused()}")

    tab_to("Resultados")
    page.keyboard.press("Enter")
    page.wait_for_url(URL + "resultados?lang=pt")
    on_heading()
    assert focused().startswith("H1 Resultados"), focused()
    page.go_back()
    on_heading()
    assert focused().startswith("H1 Pergunte"), focused()
    for _ in range(40):  # the question field, by Tab from the heading
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.id") == "question":
            break
    page.keyboard.type("Quantos dias de férias?")
    page.keyboard.press("Enter")
    expect(page.locator(".answer-text")).to_be_visible()


def main() -> int:
    parser = argparse.ArgumentParser(prog="python web/e2e.py")
    parser.add_argument("--shots", type=Path, help="save screenshots here")
    args = parser.parse_args()
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=serve, daemon=True).start()
    time.sleep(2)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 900}, locale="pt-PT")
        try:
            check(page, args.shots)
            keyboard(browser.new_page(viewport={"width": 1100, "height": 900}, locale="pt-PT"))
            mobile = browser.new_page(viewport={"width": 390, "height": 844}, locale="en-GB")
            mobile.goto(URL)
            expect(mobile.get_by_role("navigation").get_by_role("link", name="Ask")).to_be_visible()
            audit(mobile, "home, phone, in English")
            if args.shots:
                mobile.screenshot(
                    path=str(args.shots / "4-mobile-en.png"), full_page=True, animations="disabled"
                )
            # The night edition: an answer and its article, in the dark colour scheme.
            dark = browser.new_page(
                viewport={"width": 1100, "height": 900}, locale="pt-PT", color_scheme="dark"
            )
            dark.goto(URL + "?q=Quantos+dias+de+f%C3%A9rias%3F&d=2012-09-01&lang=pt")
            dark.locator(".basis .cite").first.click()
            expect(dark.locator(".reader-meta")).to_contain_text("01/09/2012")
            audit(dark, "an answer and its article, dark")
            dark.goto(URL + "resultados?lang=pt")
            expect(dark.locator("table").first).to_be_visible()
            audit(dark, "results, dark")
            # A path that is no page: the page says so, with a 404.
            missing = dark.goto(URL + "nada")
            assert missing is not None and missing.status == 404, missing
            expect(dark.get_by_role("heading", name="Página não encontrada")).to_be_visible()
            audit(dark, "not found, dark")
            if args.shots:
                dark.goto(URL + "?q=Quantos+dias+de+f%C3%A9rias%3F&d=2012-09-01&lang=pt")
                dark.locator(".basis .cite").first.click()
                dark.screenshot(
                    path=str(args.shots / "5-dark.png"), full_page=True, animations="disabled"
                )
        finally:
            browser.close()
    if violations:
        print("accessibility (axe-core, WCAG 2.2 A and AA):", *violations, sep="\n  ")
        return 1
    print("page checks passed; axe found no WCAG 2.2 A or AA violation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
