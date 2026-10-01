"""End-to-end check of the page in a real browser, with no model quota spent.

    python web/e2e.py [--shots DIR]

Serves the built page (web/dist) and the API with the real article corpus but a scripted answer,
then drives Chromium through what a visitor does: switch language, open a shared link, read a
cited article, compare it with its previous version, reload. Needs the `ingest` extra
(Playwright) and `npm run build` in web/. Exits non-zero at the first check that fails.
"""

import argparse
import datetime as dt
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
from lex.store.memory import Corpus  # noqa: E402

PORT = 8765
URL = f"http://127.0.0.1:{PORT}/"


class Scripted:
    """Answers every question citing article 238, the one with a 2012 change to compare, after
    its one sentence, as the demo's per-sentence format does."""

    name = "scripted"

    def answer(self, question: str, as_of: dt.date) -> Answer:
        time.sleep(0.2)
        return Answer(
            text=f"Resposta de teste para {as_of:%d/%m/%Y}. (art. 238.º)",
            citations=[Citation(diploma="lei-7-2009", article="238")],
        )


def serve() -> None:
    corpus = Corpus.load(ROOT / "data" / "processed" / "ct" / "versions.jsonl")
    app = create_app(
        Scripted(),
        library=corpus.versions_of,
        find=corpus.search_words,
        leaderboard=leaderboard(ROOT / "results" / "test"),
        static=ROOT / "web" / "dist",
    )
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


def check(page: Page, shots: Path | None) -> None:
    def tab(name: str) -> Locator:
        return page.get_by_role("navigation").get_by_role("button", name=name, exact=True)

    submit = page.locator(".ask form button[type=submit]")

    def shot(name: str) -> None:
        if shots:
            page.screenshot(path=str(shots / f"{name}.png"), full_page=True, animations="disabled")

    # Language: the switch changes the interface, and the choice survives a reload.
    page.goto(URL)
    page.get_by_role("button", name="EN", exact=True).click()
    expect(tab("Ask")).to_be_visible()
    expect(page.locator(".notice")).to_contain_text("not legal advice")
    page.reload()
    expect(tab("Results")).to_be_visible()
    page.get_by_role("button", name="PT", exact=True).click()
    expect(tab("Resultados")).to_be_visible()
    shot("1-home")

    # A shared link asks its question on arrival, on its date, and the answer says how long.
    page.goto(URL + "?q=Quantos+dias+de+f%C3%A9rias%3F&d=2011-06-01&lang=pt")
    expect(page.locator(".answer-text")).to_contain_text("01/06/2011")
    expect(page.locator(".kicker")).to_contain_text(" s")
    assert "d=2011-06-01" in page.url, page.url

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

    # The same question again comes from the cache, and the page says so.
    submit.click()
    expect(page.locator(".kicker")).to_contain_text("resposta guardada")

    # Articles, with no model: by number on a date, by words, and from a link.
    tab("Artigos").click()
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
    page.goto(URL + "?art=252-B&d=2025-05-01&lang=pt")
    expect(page.locator(".browse .reader-meta")).to_contain_text("01/05/2025")
    page.goto(URL + "?art=252-B&d=2024-01-01&lang=pt")
    expect(page.locator(".browse .reader")).to_contain_text("Nenhuma versão")  # not yet law

    # Results and About render in both languages.
    page.goto(URL + "?q=Quantos+dias+de+f%C3%A9rias%3F&d=2011-06-01&lang=pt")
    expect(page.locator(".answer-text")).to_contain_text("01/06/2011")
    tab("Resultados").click()
    expect(page.locator("table").first).to_be_visible()
    shot("3-results")
    page.get_by_role("button", name="EN", exact=True).click()
    tab("About").click()
    expect(page.locator(".prose")).to_contain_text("Gemini embeddings")
    tab("Ask").click()
    expect(page.locator(".answer")).to_be_visible()  # the answer survived the tabs


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
            mobile = browser.new_page(viewport={"width": 390, "height": 844}, locale="en-GB")
            mobile.goto(URL)
            expect(
                mobile.get_by_role("navigation").get_by_role("button", name="Ask")
            ).to_be_visible()
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
            if args.shots:
                dark.screenshot(
                    path=str(args.shots / "5-dark.png"), full_page=True, animations="disabled"
                )
        finally:
            browser.close()
    print("page checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
