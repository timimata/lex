# The page: from a themed demo to a professional product

What the page is for: a visitor with a question about the Código do Trabalho gets an answer that
cites the article in force on the date, opens that article, and sees how often the system is
right. A recruiter or a lawyer who lands on it should read, in ten seconds, what it is, that it is
measured, and where the code and the data are.

The current page (2026-10-02, screenshots in `docs/img/`) has a strong idea, the Diário da
República meets the azulejo, and carries it with too many devices at once. That is what makes a
page read as generated rather than designed: not a bad idea, but every idea at the same time.

## What reads as unprofessional today

Found by reading the code and screenshots of every view at 1280 px, 390 px and in the dark
scheme (`web/e2e.py --shots`, or the fixture-corpus preview used for this review).

1. **Decoration stacked on decoration.** A tile wallpaper across the whole masthead, paper grain
   on the body, a dateline ("Lisboa, sexta-feira, 2 de outubro de 2026"), a rubber stamp that
   rotates in, roman numerals on the examples, a "§" before the notice, double rules, a press
   bar. Each is a metaphor for "newspaper"; together they are a costume. A designed page keeps
   one.
2. **Three typefaces, and the monospace does the work of a label.** Newsreader, Schibsted
   Grotesk and Courier Prime. The typewriter face carries every piece of metadata (the kicker,
   the reader's meta block, the timeline, the table's dates and commits) at 12 to 13 px, where
   it is the least legible of the three and looks dated. Two faces are enough: the serif for the
   law and the headlines, the grotesque for everything else, with tabular figures for numbers.
3. **The accent means five things.** Vermilion marks the active tab, the section-label dash, the
   example numerals, the "this demo" tag, the "in force" tag, the refusal and removed text. When
   one colour marks everything, it marks nothing. One accent, one meaning: cobalt for what is
   interactive or current, vermilion only for what is removed or refused.
4. **Motion on everything.** Six keyframe animations run on load: tiles fade in, headings rise
   in three delays, the stamp bounces, list items cascade, the reader slides, diff marks ink in.
   Entrance animation is the clearest tell of a generated page. Motion should answer an action
   (an answer arriving, a request in flight), never decorate a load.
5. **The home page does not say what the project is.** Above the fold: a form and four examples.
   The proposition (answers that cite the article in force on a date, measured on a held-out
   test set) and the numbers that back it (0.76 correct, 0.94 citation precision on 88 test
   questions) sit two clicks away under Results. The right half of a 1280 px screen is empty.
6. **The answer arrives below the examples**, so after asking, the visitor scrolls past the
   example list to find it, on every question. The examples should give way to the answer.
7. **Metadata written for the developer, shown to the visitor.** The kicker says "0,3 s (pesquisa
   0,21 s, modelo 2,9 s)"; the leaderboard has a commit hash column; the footer names the system
   as "Dense (Gemini Embedding 2) + referências explícitas + Gemini 3.1 Flash-Lite + citação por
   frase". Timings and hashes belong in a details line, not in the first thing read.
8. **The reader is centred like a title page**, with a centred monospace paragraph for its meta
   and a horizontal timeline of 150 px columns that wraps dates onto two lines. The DR sets
   articles flush left. The reader also scrolls away while the answer is read: it should stay
   beside it.
9. **The disclaimer appears twice** in full (notice bar and footer) and takes three lines at the
   top of a phone screen before any content. Every surface must carry it (CLAUDE.md), which one
   compact line at the top and the full sentence in the footer satisfies.
10. **No real pages.** The tabs are buttons that change React state; `/resultados` does not
    exist, the title never changes, a link to the results cannot be shared or indexed, and the
    tabs are not links for keyboard or screen-reader users. There are no Open Graph tags, so a
    shared answer link unfurls as nothing.
11. **Nothing says who made it or where the code is.** No link to the repository, the dataset,
    the licences or the author, on a page whose purpose is partly to be shown.
12. **Mobile is the desktop stacked.** The masthead keeps its pattern and tagline, the notice
    takes three lines, the form's button spans the width while the date field does not, and the
    reader lands far below the answer with no way back up.

Also noted, not design: the date input is native (fine; it follows the visitor's locale) and
the fonts load four files for Newsreader alone (optical size and italic, latin and latin-ext).

## What the research says (2026-10-02)

A search across the writing on what makes a page read as generated, and on the craft it lacks,
checked against this page. Sources at the end of the section.

**The fingerprint of a generated page**, as several reviewers of "AI slop" describe it: the
Inter typeface, an indigo-to-purple gradient, three rounded cards in a row with thin-line icons,
glassmorphism, one radius on everything, a dark hero with floating shapes, the hero / features /
testimonials / pricing layout, uppercase tracked "eyebrow" labels, badges and chips, entrance
animation on load, headline copy that could belong to any product ("Build the future",
"seamless", "empower", "unlock"), em dashes everywhere, and the same density in every section.
The cause is no decision: an unprompted model picks the most probable pattern. The fix is a
direction committed to and carried through, real content, and copy in the owner's voice.

**What professional typography does** (Butterick, GOV.UK, the typography guides): body text 15
to 25 px, line spacing 120 to 145 percent, lines of 45 to 90 characters, a professional face, a
type scale chosen once and kept, two weights per family used for structure (GOV.UK uses 400 and
700 only), no tracking manipulation, capitals rarely, headings not much larger than the text,
bold and italic sparingly and never together, left-aligned text, curly quotes.

**What professional data tables do**: text left, numbers right, headers aligned with their
column and set bolder, tabular figures, one subtle divider rather than heavy rules or strong
zebra stripes, rows about 40 to 48 px, no centred cells, nothing in the table without a reason.

**What professional forms do**: labels above the field, the field's width a cue to the expected
input, a textarea of two rows to start, buttons that name the action, 0 px radius and a 2 px
base on controls (GOV.UK's one cue that a control presses).

**What a credible numbers panel does**: three or four specific figures, each traceable to its
source, with a date; a number that leads somewhere is evidence, a number that sits there is a
claim.

**What accessible colour does** (WCAG 2.2): 4.5:1 for text, 3:1 for large text and for the
borders of fields and the focus ring; a visible focus indicator on every control; in the dark
scheme no pure black, no pure white, accents desaturated by 20 to 30 percent, elevation by
borders rather than shadows.

**This page, checked against that list.** Already right after stage 1: no Inter, no gradient,
no cards, no radius, no texture, no entrance animation, no hero, two faces, labels above
fields, verbs on buttons, numbers right-aligned with tabular figures, the dark scheme on
off-black with pastel accents. Found wanting and fixed the same day:

- Eighteen distinct font sizes, from 11 to 38 px, and five weights. Now a nine-step scale (12,
  13, 14, 16, 18, 20, 24, 32, 40) and 400 and 600 only.
- Uppercase tracked labels in five places (section labels, the answer's kind, tags, the
  reader's eyebrow, footer headings) and negative tracking on headings: the eyebrow-and-chip
  look. Now sentence case, no tracking anywhere, a remark in parentheses where a chip was.
- The muted text on the darker paper measured 4.42:1 and field borders 1.8:1 (light) and
  2.0:1 (dark). Now 5.3:1 and 3.7:1 and 3.7:1, computed from the tokens.
- Em dashes in the page titles; "harness" in the links. Replaced.
- The figures panel had no date. It names the run's date beside the link to the results.
- Buttons had no press cue. A 2 px base, as GOV.UK does.

Sources: [925 Studios on the tells](https://www.925studios.co/blog/ai-slop-design-tells) and
[their guide](https://www.925studios.co/blog/ai-slop-web-design-guide),
[Developers Digest, 16 patterns](https://www.developersdigest.tech/blog/ai-design-slop-and-how-to-spot-it),
[smoothui on the cause and the fix](https://smoothui.dev/blog/ai-design-slop),
[TeneX, 8 signs](https://tenex.studio/en/blog/ai-slop-ui-8-signes/),
[one developer's lessons](https://alexlavaee.me/blog/lessons-learned-designing-with-ai/),
[Butterick's key rules](https://practicaltypography.com/summary-of-key-rules.html),
[GOV.UK type scale](https://design-system.service.gov.uk/styles/type-scale/) and
[spacing](https://design-system.service.gov.uk/styles/spacing/), and
[the GDS note on its typography](https://designnotes.blog.gov.uk/2018/02/19/developing-new-typography-and-spacing-for-gov-uk-frontend/),
[Refactoring UI's rules](https://sobrief.com/books/refactoring-ui),
[UX Booth on data tables](https://uxbooth.com/articles/designing-user-friendly-data-tables/) and
[Pencil & Paper](https://www.pencilandpaper.io/articles/ux-pattern-analysis-enterprise-data-tables),
[Designlab on forms](https://designlab.com/blog/form-ui-design-best-practices) and
[Uxcel on button labels](https://uxcel.com/lessons/button-label-best-practices-673),
[WebAIM's WCAG checklist](https://webaim.org/standards/wcag/checklist) and
[the WCAG 2.2 overview](https://webaim.org/blog/wcag-2-2-overview-and-feedback/),
[dark mode practice](https://natebal.com/best-practices-for-dark-mode/),
[font loading](https://blog.openreplay.com/modern-font-loading-strategies/).

## Principles for the rework

- **One idea, carried by typography and layout.** The law as a dated document, set like the DR.
  No textures, patterns, stamps or numerals. The azulejo survives as the mark in the wordmark.
- **One typeface, the system's own, two weights, one accent, one type scale** (12, 13, 14, 16,
  18, 20, 24, 32, 40) **and one spacing scale** (4 px base; 8, 12, 16, 24, 32, 48, 64). No
  tracking, no capitals, no chips. The serif and the grotesque were dropped on 2026-10-02, at
  Tiago's choice, for the face the visitor's other pages use; nothing is downloaded.
- **No entrance animation.** Motion only for state: the loading bar, a 200 ms fade when an
  answer arrives, focus rings.
- **Content first, above the fold:** what it is, the form, the measured numbers. Every number on
  the page comes from `/api/leaderboard`, which reads `results/`; nothing is typed in.
- **Real pages**, real links, titles per page, keyboard first.
- **Mobile is designed, not derived:** a compact header, the form, then the answer; the reader
  below the answer with a link back to it.

## Stages

Each stage is a commit with before and after screenshots from `web/e2e.py --shots`, and
`npm run build` and `python web/e2e.py` green.

### Stage 1: restraint (done 2026-10-02)

Remove: the masthead tiles and mask, the paper grain, the dateline, the stamp and its animation,
the roman numerals, the "§", the press-bar and every `reveal` animation, Courier Prime. Keep:
the palette, Newsreader and Schibsted Grotesk, the double rule as the one newspaper device.
Accent discipline: vermilion for removed text, errors and refusals only.

Exit: no `@keyframes` but the loading bar and one fade; two font families in the bundle; the
tab, the section labels and the tags no longer use vermilion.

### Stage 2: structure and hierarchy (done 2026-10-02)

- One header bar: mark, wordmark, the four pages as links, the language switch. A one-line
  notice under it. The full disclaimer in the footer.
- Home as two columns at 1280 px: the question (heading, lead, form, examples) and, beside it,
  what the page is and the numbers that back it, read from the leaderboard entry of the demo's
  own system: correct answers, citation precision, the test set's size, with a link to Results.
  When the leaderboard has no entry for the demo's system, the panel shows the three
  "how it answers" lines and no numbers.
- An answer replaces the examples and the side panel; a new question replaces the answer.
- The kicker says the date and whether the answer was stored; the timings move to a details
  line under the answer.
- Footer: what Lex is, links (code, dataset, DR, PGDL), licences (MIT, CC BY 4.0), the author,
  the disclaimer, the demo's system.
- About: the same links, and how the numbers are measured, pointing at the ADRs.

Exit: at 1280 px the fold shows the heading, the form and the measured numbers; at 390 px it
shows the header, the notice and the form.

### Stage 3: the reader (done 2026-10-02)

Flush-left typesetting: eyebrow (Código do Trabalho), article number, heading, then a meta line
in the grotesque: version in force on the date, since when, which diploma. Actions as links.
The text as now, with hanging numbers. History as a vertical list at every width: date range,
diploma, "in force on this date". Sticky beside the answer on desktop, scrolling within its own
height; on a phone it follows the answer, with a "back to the answer" link.

Exit: the reader stays in view while the answer scrolls at 1280 px; the history never wraps a
date.

### Stage 4: real pages and metadata (done 2026-10-02)

`/`, `/artigos`, `/resultados`, `/sobre`, served by the API (`create_app` returns the page for
each), the nav as links that push state, the title set per page, `?q`, `?d` and `?art` kept.
Open Graph and Twitter card tags with a static description; `lang` on the document; a skip
link; focus order checked by keyboard in `e2e.py`.

Exit: `python web/e2e.py` opens each page by URL; a shared `/resultados` link opens Results.

### Stage 5: results people can read (done 2026-10-02)

- A summary line above the answers table: the demo's correct share and precision, in words,
  from its own leaderboard entry.
- ~~The run column reduced to the date, with the commit in a tooltip, and a link to the runs'
  files~~ (done with stage 2).
- Per-type results as one table per measure (types as rows, systems as columns), four tables
  instead of one per system, so the systems are compared on one line.
- The judge note stays under the table, where the number it explains is; the link to
  `results/test/` is under the retrieval table.

Exit: ~~the answers table fits 1024 px without horizontal scroll~~ (every table measures the
same scroll and client width at 1024 px); every number traces to a file in `results/`.

### Stage 6: performance and polish (done 2026-10-02)

- ~~Preload the two text faces; drop the subsets the page never uses~~ (moot: the page uses
  the system face and loads no font).
- ~~Lazy-load Results and About~~: 5.8 kB and 1.3 kB of their own, loaded on the click.
- ~~Check contrast of every token pair in both schemes with a script~~: `web/contrast.py`,
  21 pairs, both schemes, written to [docs/checks/web-contrast.md](../docs/checks/web-contrast.md);
  the lowest text pair is 5.13:1 and the lowest border 3.46:1.
- ~~Lighthouse recorded in `docs/checks/`~~:
  [docs/checks/web-lighthouse.md](../docs/checks/web-lighthouse.md). The results page's layout
  shift of 0.235 (the leaderboard arriving after its fetch moved the footer) is 0 now that the
  main area fills the first screen.

Exit: first contentful paint under 1.5 s on a throttled 4G profile. **Not met then; met in stage
7**: 2.3 s on
Lighthouse's simulated mobile profile, all of it the 84 kB (gzipped) script, most of which is
React. Meeting it would mean a smaller framework or server-rendered HTML, which this roadmap
does not plan; the number is written down and the bar stays open.

### Stage 7: a lighter page (done 2026-10-06)

Stage 6 left its bar open: 2.3 s to first paint on Lighthouse's mobile profile, all of it the
84 kB (gzipped) script, most of it React. Preact through `preact/compat` runs the same
components (hooks, `lazy`, `Suspense`) at a fraction of the size, with no rewrite.

Exit: the same `web/e2e.py` green; the script's size and Lighthouse's first contentful paint on
the home page measured before and after in `docs/checks/web-lighthouse.md`; the 1.5 s bar met or
the gap written down.

Done: Vite aliases React to `preact/compat` 10.29.8; the main script went from 85.2 to 24.7 kB
gzipped, first paint from 2.3 to 1.4 s on the home page and from 2.4 to 1.5 s on the results,
Lighthouse performance 95 to 100 and 94 to 99 ([docs/checks/web-lighthouse.md](../docs/checks/web-lighthouse.md)).

### Stage 8: what an answer took (done 2026-10-06)

The API now returns each answer's calls and tokens (`tokens`) and, for the agent (ADR 0018), the
requests it made before answering (`requests`). The details line under an answer says them
("1 chamada ao modelo, 2 340 tokens"), and an agent's requests are listed under the legal basis
("O modelo pediu: pesquisar «…»: NRAU 15-A"), so a visitor sees how the answer was made. Nothing
is shown when the API has no figure.

Exit: `web/e2e.py` checks the line on a scripted answer with tokens and requests.

Done: the details line reads "respondida em 0,2 s · 2 chamadas ao modelo, 2340 tokens" (thinking
included), and the requests list sits under the legal basis; both are checked in `web/e2e.py`.

### Stage 9: a word search that shows why (done 2026-10-06)

A word search lists headings only, so a hit whose heading does not hold the words looks
arbitrary. Each hit shows the sentence of the text that holds them, the words marked; the
diploma list filters the search, with an "all diplomas" choice, the default for words (a number
still needs a diploma, and keeps the one chosen).

Exit: a search for «renda antecipado» in the Código Civil shows art. 1076.º with the line that
holds the words, marked; choosing the NRAU hides it.

Done: `/api/search` returns each hit's line and where the words are (`excerpt`, `marks`) and
takes `diploma`; the page marks the words, offers "Todos os diplomas" (the default), and looks a
bare number up in every diploma, opening it where only one has it and listing them otherwise
("9": art. 9.º do CT and of the NRAU). Checked in `web/e2e.py`.

### Stage 10: sharing and printing (done 2026-10-06)

- An Open Graph image (1200 × 630, a real answer with its article), so a shared link unfurls
  with a picture on LinkedIn or a chat.
- A print stylesheet: an answer or an article prints as the document it is, with its date and
  the disclaimer, without the header, the nav, the form or the footer's links.
- "Copiar ligação" on the reader too: an article on a date is worth sharing.

Exit: the image is served and named in the page's head; a print preview (Playwright's PDF)
holds the article and the disclaimer and not the nav.

Done: `web/public/og.png`, taken from the live demo (the 2011 example, answered at deploy), with
`summary_large_image` and the head's title and description now naming tenancy too; a print
stylesheet that keeps the brand, the notice, the article or answer, the history's dates and the
full disclaimer; "Copiar ligação" in the reader, which copies `/artigos?art=…&dip=…&d=…`. All
three are checked in `web/e2e.py`, which writes the print to a PDF with `--shots`.

### Stage 11: accessibility checked by a tool (done 2026-10-06)

Lighthouse's accessibility score is a sample. axe-core runs inside `web/e2e.py` on every page,
in both schemes, and the run fails on any violation; an unknown path gets a page that says so
(404), not the home page.

Exit: axe reports no violations on home, an answer, Articles, Results and About, light and dark;
`/nada` answers 404 with a page.

Done: `web/e2e.py` runs axe-core 4.14.0 (pinned, a dev dependency of `web/`) against WCAG 2.2 A
and AA on nine states: home (desktop and phone), an answer with its article's changes open, a
word search, Results, About in English, and, dark, an answer with its article, Results and the
not-found page. None has a violation. Checked that it would see one: an image without text and
a button without a name, put on the page on purpose, are both reported. A path that is no page
gets the page with a 404 and "Página não encontrada"; the API's own 404s stay JSON.

## What is not planned

- A chat interface. One question, one answer, one legal basis is the product.
- Illustrations, icons sets, gradients, cards with shadows, skeleton loaders. Nothing that could
  be on any other page.
- Client-side analytics. The API's own counts are enough.
